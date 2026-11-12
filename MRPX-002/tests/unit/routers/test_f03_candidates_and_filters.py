"""Tests of v2/F-03: candidate list (API-01) and filter options (API-03) routes."""

from __future__ import annotations

from datetime import date
from typing import Any


def test_f03_ac1_list_ok(
    client: Any, fake_connection: Any, sample_rows: list[dict[str, object]]
) -> None:
    fake_connection.queued_results = [
        sample_rows,
        [{"total": 3}],
        [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}],
    ]

    response = client.get(
        "/api/transfer-candidates?short_plant=3300&criticality=A&criticality=NONE"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["items"][0]["material"] == "1236-561-01"
    assert body["mrp_snapshot_date"] == "2026-08-30"
    assert body["inventory_month"] == "202608"
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_f03_ac2_validation_422(client: Any) -> None:
    response = client.get("/api/transfer-candidates?limit=500")
    assert response.status_code == 422
    assert response.json() == {"detail": "limit must be between 1 and 200"}

    response = client.get("/api/transfer-candidates?criticality=X")
    assert response.status_code == 422
    assert response.json() == {"detail": "criticality must be one of A, B, C, NONE"}


def test_f03_ac3_filters_ok(client: Any, fake_connection: Any) -> None:
    fake_connection.queued_results = [
        [{"code": "3300", "name": "ASM Korea Ltd.", "country": "KR"}],
        [{"country": "KR"}],
        [{"criticality": "A"}, {"criticality": "C"}, {"criticality": "NONE"}],
        [{"product_family": "CP"}, {"product_family": "PE"}],
        [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}],
    ]

    response = client.get("/api/filters")

    assert response.status_code == 200
    body = response.json()
    assert body["short_plants"] == [{"code": "3300", "name": "ASM Korea Ltd.", "country": "KR"}]
    assert body["countries"] == ["KR"]
    assert body["criticalities"] == ["A", "C", "NONE"]
    assert body["product_families"] == ["CP", "PE"]
    assert body["mrp_snapshot_date"] == "2026-08-30"


def test_f03_ac4_warehouse_down_503(client: Any, fake_connection: Any) -> None:
    def broken_cursor() -> Any:
        raise Exception("socket closed")

    fake_connection.cursor = broken_cursor

    response = client.get("/api/filters")

    assert response.status_code == 503
    assert response.json() == {"detail": "The transfer candidates could not be loaded. Try again."}
