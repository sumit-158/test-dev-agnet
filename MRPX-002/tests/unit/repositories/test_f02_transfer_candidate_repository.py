"""Unit tests of the T-01 repository and response models (v2/F-02)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest


def _record_cursors(fake_connection: Any) -> list[Any]:
    """Wrap fake_connection.cursor so every opened cursor is kept in order."""
    cursors: list[Any] = []
    original = fake_connection.cursor

    def cursor() -> Any:
        cur = original()
        cursors.append(cur)
        return cur

    fake_connection.cursor = cursor
    return cursors


def test_f02_ac1_candidates_where_and_params(
    settings: Any, fake_connection: Any, sample_rows: list[dict[str, object]]
) -> None:
    """AC-F02-1: filters build numbered IN parameters and the NONE criticality OR branch."""
    from backend.models import CandidateFilters
    from backend.repositories.transfer_candidate_repository import TransferCandidateRepository

    fake_connection.queued_results = [
        sample_rows,
        [{"total": 3}],
        [{"mrp_snapshot_date": date(2026, 8, 30), "inventory_month": "202608"}],
    ]
    cursors = _record_cursors(fake_connection)
    repo = TransferCandidateRepository(settings, lambda: fake_connection)

    page = repo.fetch_candidates(
        CandidateFilters(short_plants=["3300"], criticalities=["A", "NONE"]),
        "movable_qty",
        "desc",
        50,
        0,
    )

    assert len(page.items) == 3
    assert page.items[0].material == "1236-561-01"
    assert page.items[0].movable_qty == 336233.0
    assert page.total == 3
    assert page.mrp_snapshot_date == date(2026, 8, 30)
    assert page.inventory_month == "202608"
    assert page.limit == 50
    assert page.offset == 0
    first_sql, first_params = cursors[0].calls[0]
    assert "short_plant IN (:sp0)" in first_sql
    assert "(criticality IN (:cr0) OR criticality IS NULL)" in first_sql
    assert first_params == {"sp0": "3300", "cr0": "A", "limit": 50, "offset": 0}


def test_f02_ac2_material_detail_golden(
    settings: Any, fake_connection: Any, golden_row: dict[str, object]
) -> None:
    """AC-F02-2: the golden row gives one holding plant with UNKNOWN PLANT and NULL country."""
    from backend.models import HoldingPlant
    from backend.repositories.transfer_candidate_repository import TransferCandidateRepository

    fake_connection.queued_results = [[golden_row]]
    repo = TransferCandidateRepository(settings, lambda: fake_connection)

    detail = repo.fetch_material_detail("1236-561-01", "3300")

    assert detail is not None
    assert detail.material == "1236-561-01"
    assert detail.short_plant == "3300"
    assert detail.shortage_qty == 336233.0
    assert detail.weeks_late == 9
    assert detail.holding_plants == [
        HoldingPlant(
            stock_plant="1000",
            stock_plant_name="UNKNOWN PLANT",
            stock_plant_country=None,
            stock_qty=356500.0,
            movable_qty=336233.0,
        )
    ]
    _, params = fake_connection.last_cursor.calls[0]
    assert params == {"material": "1236-561-01", "short_plant": "3300"}


def test_f02_ac3_material_detail_not_found(settings: Any, fake_connection: Any) -> None:
    """AC-F02-3: no row for the shortage gives None."""
    from backend.repositories.transfer_candidate_repository import TransferCandidateRepository

    fake_connection.queued_results = [[]]
    repo = TransferCandidateRepository(settings, lambda: fake_connection)

    assert repo.fetch_material_detail("0000-000-00", "3300") is None


def test_f02_ac4_errors(settings: Any, fake_connection: Any) -> None:
    """AC-F02-4: connector failure maps to DataUnavailableError; bad sort raises before SQL."""
    from backend.constants import ERROR_UNAVAILABLE
    from backend.models import CandidateFilters
    from backend.repositories.transfer_candidate_repository import (
        DataUnavailableError,
        TransferCandidateRepository,
    )

    def failing_factory() -> Any:
        raise Exception("socket closed")

    with pytest.raises(DataUnavailableError) as excinfo:
        TransferCandidateRepository(settings, failing_factory).fetch_freshness()
    assert str(excinfo.value) == ERROR_UNAVAILABLE
    assert excinfo.value.__cause__ is not None

    cursors = _record_cursors(fake_connection)
    repo = TransferCandidateRepository(settings, lambda: fake_connection)
    with pytest.raises(ValueError):
        repo.fetch_candidates(CandidateFilters(), "material_description", "desc", 50, 0)
    assert all(cur.calls == [] for cur in cursors)
    assert fake_connection.last_cursor is None
