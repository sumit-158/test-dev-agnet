"""Tests of v2/F-04: material detail route (API-02)."""

from __future__ import annotations

from typing import Any


def test_f04_ac1_detail_golden(
    client: Any, fake_connection: Any, golden_row: dict[str, object]
) -> None:
    fake_connection.queued_results = [[golden_row]]

    response = client.get("/api/transfer-candidates/1236-561-01/3300")

    assert response.status_code == 200
    body = response.json()
    assert body["material"] == "1236-561-01"
    assert body["shortage_qty"] == 336233.0
    assert body["weeks_late"] == 9
    assert body["holding_plants"][0] == {
        "stock_plant": "1000",
        "stock_plant_name": "UNKNOWN PLANT",
        "stock_plant_country": None,
        "stock_qty": 356500.0,
        "movable_qty": 336233.0,
    }
    _, params = fake_connection.last_cursor.calls[0]
    assert params == {"material": "1236-561-01", "short_plant": "3300"}


def test_f04_ac2_detail_not_found(client: Any, fake_connection: Any) -> None:
    fake_connection.queued_results = [[]]

    response = client.get("/api/transfer-candidates/0000-000-00/3300")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Material 0000-000-00 is not short in plant 3300 in the current MRP result."
    }


def test_f04_ac3_detail_invalid_material(client: Any) -> None:
    response = client.get("/api/transfer-candidates/1236%20561/3300")

    assert response.status_code == 422
    assert response.json() == {"detail": "material must match ^[A-Za-z0-9._/-]{1,40}$"}
