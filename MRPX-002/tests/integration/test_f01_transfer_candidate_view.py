"""SQL assertions on the T-01 materialized view (v1/F-01 §8), run against a dev workspace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

pytestmark = pytest.mark.integration

VIEW = "sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair"
GOLDEN_SNAPSHOT = date(2026, 8, 30)
GOLDEN_MONTH = "202608"
FORBIDDEN_COLUMNS = (
    "TOTAL_VALUE",
    "STANDARD_PRICE",
    "MFG_COST_PRICE",
    "CREATED_BY",
    "CHANGED_BY",
    "REGION",
)
EXPECTED_COLUMNS = [
    "material",
    "material_description",
    "material_type",
    "product_family",
    "criticality",
    "short_plant",
    "short_plant_name",
    "short_plant_country",
    "stock_plant",
    "stock_plant_name",
    "stock_plant_country",
    "shortage_qty",
    "stock_qty",
    "movable_qty",
    "weeks_late",
    "unit_of_measure",
    "mrp_snapshot_date",
    "inventory_month",
    "ETL_LOADDATE",
    "SOURCE_SNAPSHOT_DATE",
]


def _fetchall(connection: Any, sql: str) -> list[dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(sql)
        return [row.asDict() for row in cur.fetchall()]


def _scalar(connection: Any, sql: str) -> Any:
    with connection.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    assert row is not None
    return row[0]


def test_f01_ac1_rows_and_no_null_keys(integration_connection: Any) -> None:
    """AC-F01-1: the view has rows and no null grain keys (proves skill §7 not-null keys)."""
    rows = _fetchall(
        integration_connection,
        "SELECT COUNT(*) AS n, SUM(CASE WHEN material IS NULL OR short_plant IS NULL "
        f"OR stock_plant IS NULL THEN 1 ELSE 0 END) AS null_keys FROM {VIEW}",
    )

    assert rows[0]["n"] >= 1
    assert rows[0]["null_keys"] == 0


def test_f01_ac2_grain_unique(integration_connection: Any) -> None:
    """AC-F01-2: (material, short_plant, stock_plant) is unique and movable_qty is the LEAST.

    Proves the grain and the movable quantity rule.
    """
    rows = _fetchall(
        integration_connection,
        "SELECT COUNT(*) AS n, "
        f"COUNT(DISTINCT CONCAT(material, '|', short_plant, '|', stock_plant)) AS d FROM {VIEW}",
    )
    violations = _scalar(
        integration_connection,
        f"SELECT COUNT(*) FROM {VIEW} WHERE short_plant = stock_plant OR movable_qty <= 0 "
        "OR movable_qty > shortage_qty OR movable_qty > stock_qty",
    )

    assert rows[0]["n"] == rows[0]["d"]
    assert violations == 0


def test_f01_ac3_golden_example(
    integration_connection: Any, golden_row: dict[str, object]
) -> None:
    """AC-F01-3: the golden example row is returned exactly.

    Proves PRD §6, BR-02, BR-05, BR-06, BR-03.
    """
    snapshot = _scalar(integration_connection, f"SELECT MAX(mrp_snapshot_date) FROM {VIEW}")
    if snapshot != GOLDEN_SNAPSHOT:
        pytest.skip("snapshot moved on")

    rows = _fetchall(
        integration_connection,
        f"SELECT {', '.join(EXPECTED_COLUMNS)} FROM {VIEW} "
        "WHERE material = '1236-561-01' AND short_plant = '3300' AND stock_plant = '1000'",
    )
    max_movable = _scalar(integration_connection, f"SELECT MAX(movable_qty) FROM {VIEW}")

    assert len(rows) == 1
    assert {key: rows[0][key] for key in golden_row} == golden_row
    assert max_movable == Decimal("336233.000")


def test_f01_ac4_column_list(integration_connection: Any) -> None:
    """AC-F01-4: the view exposes exactly the 20 columns in order (proves BR-09, BR-04)."""
    rows = _fetchall(integration_connection, f"DESCRIBE {VIEW}")

    columns: list[str] = []
    for row in rows:
        name = (row["col_name"] or "").strip()
        if not name or name.startswith("#"):
            break
        columns.append(name)

    assert columns == EXPECTED_COLUMNS
    assert not set(FORBIDDEN_COLUMNS) & {name.upper() for name in columns}
