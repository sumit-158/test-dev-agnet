"""Shared pytest fixtures for MRPX-002 (TSD §12)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Any

import pytest


class FakeRow:
    """Stand-in for a databricks.sql Row."""

    def __init__(self, data: dict[str, object]) -> None:
        self._data = dict(data)

    def asDict(self) -> dict[str, object]:  # noqa: N802 - mirrors databricks.sql Row.asDict
        """Return the row as a dict (mirrors databricks.sql Row.asDict)."""
        return dict(self._data)

    def __getitem__(self, key: int | str) -> object:
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FakeRow):
            return NotImplemented
        return self._data == other._data

    def __repr__(self) -> str:
        return f"FakeRow({self._data!r})"


class FakeCursor:
    """Cursor that records every execute call and returns the connection's queued results."""

    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self.calls: list[tuple[str, dict[str, object] | None]] = []
        self.rows: list[dict[str, object]] = []
        self._executed = False
        self.closed = False

    def execute(self, sql: str, parameters: dict[str, object] | None = None) -> None:
        """Record (sql, parameters) and load the next queued result."""
        self.calls.append((sql, parameters))
        if not self._connection.queued_results:
            raise IndexError("no queued result for query")
        self.rows = self._connection.queued_results.pop(0)
        self._executed = True

    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """DB-API column descriptions of the current result, or None when there is none."""
        if not self._executed or not self.rows:
            return None
        return [(name, None, None, None, None, None, None) for name in self.rows[0]]

    def fetchall(self) -> list[FakeRow]:
        return [FakeRow(row) for row in self.rows]

    def fetchone(self) -> FakeRow | None:
        return FakeRow(self.rows[0]) if self.rows else None

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class FakeConnection:
    """Connection whose cursors return queued_results in order."""

    def __init__(self) -> None:
        self.queued_results: list[list[dict[str, object]]] = []
        self.last_cursor: FakeCursor | None = None
        self.closed = False

    def cursor(self) -> FakeCursor:
        self.last_cursor = FakeCursor(self)
        return self.last_cursor

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def golden_row() -> dict[str, object]:
    """The PRD §6 golden example as one T-01 row (values in TSD §12)."""
    return {
        "material": "1236-561-01",
        "material_description": "EMI GASKET / SPIRAL / SSN-053W",
        "material_type": "HALB",
        "product_family": "PE",
        "criticality": "A",
        "short_plant": "3300",
        "short_plant_name": "ASM Korea Ltd.",
        "short_plant_country": "KR",
        "stock_plant": "1000",
        "stock_plant_name": "UNKNOWN PLANT",
        "stock_plant_country": None,
        "shortage_qty": Decimal("336233.000"),
        "stock_qty": Decimal("356500.000"),
        "movable_qty": Decimal("336233.000"),
        "weeks_late": 9,
        "unit_of_measure": "MM",
        "mrp_snapshot_date": date(2026, 8, 30),
        "inventory_month": "202608",
    }


@pytest.fixture
def sample_rows(golden_row: dict[str, object]) -> list[dict[str, object]]:
    """Three T-01 rows: golden_row, row B (1226-807-01), row C (1232-405-01) exactly as TSD §12."""
    row_b: dict[str, object] = {
        "material": "1226-807-01",
        "material_description": "EMI GASKET / SPIRAL / SSN-036W",
        "material_type": "HALB",
        "product_family": "CP",
        "criticality": "C",
        "short_plant": "3300",
        "short_plant_name": "ASM Korea Ltd.",
        "short_plant_country": "KR",
        "stock_plant": "3320",
        "stock_plant_name": "ASM Korea Ltd.",
        "stock_plant_country": "KR",
        "shortage_qty": Decimal("2035876.000"),
        "stock_qty": Decimal("60000.000"),
        "movable_qty": Decimal("60000.000"),
        "weeks_late": 13,
        "unit_of_measure": "MM",
        "mrp_snapshot_date": date(2026, 8, 30),
        "inventory_month": "202608",
    }
    row_c: dict[str, object] = {
        "material": "1232-405-01",
        "material_description": "EMI GASKET / SPIRAL / SSN-028W",
        "material_type": "HALB",
        "product_family": "CP",
        "criticality": "A",
        "short_plant": "3300",
        "short_plant_name": "ASM Korea Ltd.",
        "short_plant_country": "KR",
        "stock_plant": "3320",
        "stock_plant_name": "ASM Korea Ltd.",
        "stock_plant_country": "KR",
        "shortage_qty": Decimal("55730.000"),
        "stock_qty": Decimal("60000.000"),
        "movable_qty": Decimal("55730.000"),
        "weeks_late": 12,
        "unit_of_measure": "MM",
        "mrp_snapshot_date": date(2026, 8, 30),
        "inventory_month": "202608",
    }
    return [dict(golden_row), row_b, row_c]


@pytest.fixture
def fake_connection() -> FakeConnection:
    """Connection whose cursors return queued_results in order and record every call."""
    return FakeConnection()


@pytest.fixture
def settings() -> Any:
    """Backend settings of TSD §12; skipped until the backend package exists."""
    try:
        from backend.config import Settings
    except ImportError:
        pytest.skip("backend not built yet")
    return Settings(
        catalog="sandbox_others",
        schema_gold="gold",
        view_transfer_candidates="agg_mrpx_transfer_candidate_plant_pair",
        databricks_host="https://example.cloud.databricks.com",
        databricks_warehouse_id="abc123",
    )


@pytest.fixture
def client(settings: Any, fake_connection: FakeConnection) -> Any:
    """FastAPI TestClient wired to fake_connection; skipped until the backend package exists."""
    try:
        from fastapi.testclient import TestClient

        from backend.main import create_app
    except ImportError:
        pytest.skip("backend not built yet")
    return TestClient(create_app(settings, connection_factory=lambda: fake_connection))


@pytest.fixture
def integration_connection() -> Iterator[Any]:
    """Real databricks.sql connection from DATABRICKS_HOST, DATABRICKS_WAREHOUSE_ID,
    DATABRICKS_TOKEN; skips when missing."""
    host = os.environ.get("DATABRICKS_HOST")
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host or not warehouse_id or not token:
        pytest.skip("integration environment not set")

    from databricks import sql

    host_without_scheme = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    connection = sql.connect(
        server_hostname=host_without_scheme,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        access_token=token,
    )
    try:
        yield connection
    finally:
        connection.close()
