"""The real app in-process against the real SQL warehouse (v2/F-08 §8)."""

from __future__ import annotations

import os
import time
from typing import Any

import pytest

pytestmark = pytest.mark.integration

GOLDEN_PLANT = "3300"
GOLDEN_MATERIAL = "1236-561-01"
GOLDEN_TOTAL = 6256
GOLDEN_SNAPSHOT = "2026-08-30"
MAX_SECONDS = 2.0
TIMED_CALLS = 5

GOLDEN_PAGE_URL = f"/api/transfer-candidates?short_plant={GOLDEN_PLANT}&limit=50"


@pytest.fixture(scope="module")
def warehouse_client() -> Any:
    """TestClient on create_app with real settings; skips when the integration env is missing."""
    host = os.environ.get("DATABRICKS_HOST")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not warehouse_id or not token:
        pytest.skip("integration environment not set")

    from fastapi.testclient import TestClient

    from backend.config import load_settings, make_connection_factory
    from backend.main import create_app

    # The SDK Config in make_connection_factory picks up DATABRICKS_TOKEN from the environment.
    settings = load_settings(
        {
            "CATALOG": "sandbox_others",
            "SCHEMA_GOLD": "gold",
            "VIEW_TRANSFER_CANDIDATES": "agg_mrpx_transfer_candidate_plant_pair",
            "DATABRICKS_HOST": host,
            "DATABRICKS_WAREHOUSE_ID": warehouse_id,
        }
    )
    return TestClient(create_app(settings, make_connection_factory(settings)))


@pytest.fixture(scope="module")
def filters_body(warehouse_client: Any) -> dict[str, Any]:
    """Body of GET /api/filters, fetched once per module."""
    response = warehouse_client.get("/api/filters")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _skip_unless_golden_snapshot(filters_body: dict[str, Any]) -> None:
    if filters_body.get("mrp_snapshot_date") != GOLDEN_SNAPSHOT:
        pytest.skip("snapshot moved on")


def test_f08_ac1_health_and_filters(warehouse_client: Any) -> None:
    # Health first, so a missing grant shows as a filters failure after health has passed.
    health = warehouse_client.get("/api/health")
    assert health.status_code == 200, health.text
    filters = warehouse_client.get("/api/filters")
    assert filters.status_code == 200, filters.text
    codes = [plant["code"] for plant in filters.json()["short_plants"]]
    assert GOLDEN_PLANT in codes


def test_f08_ac2_golden_plant_page(warehouse_client: Any, filters_body: dict[str, Any]) -> None:
    _skip_unless_golden_snapshot(filters_body)
    response = warehouse_client.get(GOLDEN_PAGE_URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == GOLDEN_TOTAL
    first = body["items"][0]
    assert first["material"] == GOLDEN_MATERIAL
    assert first["stock_plant"] == "1000"
    assert first["movable_qty"] == 336233.0
    assert body["mrp_snapshot_date"] == GOLDEN_SNAPSHOT
    assert body["inventory_month"] == "202608"


def test_f08_ac3_latency_under_two_seconds(warehouse_client: Any) -> None:
    warm_up = warehouse_client.get(GOLDEN_PAGE_URL)
    assert warm_up.status_code == 200, warm_up.text
    durations: list[float] = []
    for _ in range(TIMED_CALLS):
        start = time.perf_counter()
        response = warehouse_client.get(GOLDEN_PAGE_URL)
        durations.append(time.perf_counter() - start)
        assert response.status_code == 200, response.text
    assert all(seconds < MAX_SECONDS for seconds in durations), durations


def test_f08_ac4_golden_detail(warehouse_client: Any, filters_body: dict[str, Any]) -> None:
    _skip_unless_golden_snapshot(filters_body)
    response = warehouse_client.get(f"/api/transfer-candidates/{GOLDEN_MATERIAL}/{GOLDEN_PLANT}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [plant["stock_plant"] for plant in body["holding_plants"]] == ["1000"]
    assert body["shortage_qty"] == 336233.0
