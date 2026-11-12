"""Unit tests of the backend app factory, settings and health route (v2/F-01)."""

from __future__ import annotations

from typing import Any

import pytest

ENV = {
    "CATALOG": "sandbox_others",
    "SCHEMA_GOLD": "gold",
    "VIEW_TRANSFER_CANDIDATES": "agg_mrpx_transfer_candidate_plant_pair",
    "DATABRICKS_HOST": "https://example.cloud.databricks.com",
    "DATABRICKS_WAREHOUSE_ID": "abc123",
}


def test_f01_ac1_settings_full_name() -> None:
    """AC-F01-1: the five environment keys give the three-part view name."""
    from backend.config import load_settings

    settings = load_settings(ENV)

    assert settings.view_full_name == "sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"


def test_f01_ac2_missing_key_fails_fast() -> None:
    """AC-F01-2: a missing SCHEMA_GOLD raises RuntimeError naming the key."""
    from backend.config import load_settings

    with pytest.raises(RuntimeError, match="SCHEMA_GOLD"):
        load_settings({"CATALOG": "sandbox_others"})


def test_f01_ac3_health(client: Any) -> None:
    """AC-F01-3: GET /api/health returns status, catalog and schema."""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "catalog": "sandbox_others", "schema_gold": "gold"}


def test_f01_ac4_unknown_api_path_404(client: Any) -> None:
    """AC-F01-4: an unknown API path returns the JSON 404, not index.html."""
    response = client.get("/api/nothing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
