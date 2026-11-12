"""The only SQL of the app: parameterised reads of the gold view T-01 (v2/F-02)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from backend.config import Settings
from backend.constants import (
    CRITICALITY_NONE,
    CRITICALITY_VALUES,
    ERROR_UNAVAILABLE,
    SORT_COLUMNS,
    SORT_DIRECTIONS,
)
from backend.models import (
    CandidateFilters,
    CandidatePage,
    CandidateRow,
    FilterOptions,
    Freshness,
    HoldingPlant,
    MaterialDetail,
    PlantOption,
)

logger = logging.getLogger(__name__)

COLUMNS = (
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
)
SELECT_COLUMNS = ", ".join(COLUMNS)


class DataUnavailableError(RuntimeError):
    """Raised when the warehouse or connector fails; message is ERROR_UNAVAILABLE."""


def _in_predicate(column: str, prefix: str, values: list[str], params: dict[str, str]) -> str:
    """`column IN (:prefix0, …)` with the values added to params."""
    names = []
    for index, value in enumerate(values):
        name = f"{prefix}{index}"
        params[name] = value
        names.append(f":{name}")
    return f"{column} IN ({', '.join(names)})"


def _build_where(filters: CandidateFilters) -> tuple[str, dict[str, str]]:
    """WHERE clause and named parameters for the filters; ("", {}) when no filter is set."""
    params: dict[str, str] = {}
    predicates: list[str] = []
    if filters.short_plants:
        predicates.append(_in_predicate("short_plant", "sp", filters.short_plants, params))
    if filters.countries:
        predicates.append(_in_predicate("short_plant_country", "co", filters.countries, params))
    if filters.criticalities:
        values = [v for v in filters.criticalities if v != CRITICALITY_NONE]
        has_none = CRITICALITY_NONE in filters.criticalities
        if values and has_none:
            in_sql = _in_predicate("criticality", "cr", values, params)
            predicates.append(f"({in_sql} OR criticality IS NULL)")
        elif values:
            predicates.append(_in_predicate("criticality", "cr", values, params))
        else:
            predicates.append("criticality IS NULL")
    if filters.product_families:
        predicates.append(_in_predicate("product_family", "pf", filters.product_families, params))
    if not predicates:
        return "", {}
    return "WHERE " + " AND ".join(predicates), params


def _to_candidate_row(d: dict[str, Any]) -> CandidateRow:
    """Map one T-01 row dict to a CandidateRow (Decimal quantities to float)."""
    return CandidateRow(
        **{
            **d,
            "shortage_qty": float(d["shortage_qty"]),
            "stock_qty": float(d["stock_qty"]),
            "movable_qty": float(d["movable_qty"]),
            "weeks_late": int(d["weeks_late"]),
        }
    )


class TransferCandidateRepository:
    """Reads T-01 through a databricks.sql connection factory; contains no business logic."""

    def __init__(self, settings: Settings, connection_factory: Callable[[], Any]) -> None:
        self._view = settings.view_full_name
        self._connection_factory = connection_factory

    def _run(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute one statement on a new connection and return the rows as dicts."""
        try:
            conn = self._connection_factory()
            with conn.cursor() as cur:
                cur.execute(sql, parameters=params or None)
                rows = [r.asDict() for r in cur.fetchall()]
            conn.close()
        except ValueError:
            raise
        except Exception as exc:
            raise DataUnavailableError(ERROR_UNAVAILABLE) from exc
        return rows

    def fetch_candidates(
        self, filters: CandidateFilters, sort_by: str, sort_dir: str, limit: int, offset: int
    ) -> CandidatePage:
        """Rows + total for the filters. Raises ValueError when sort_by or sort_dir is not
        whitelisted."""
        if sort_by not in SORT_COLUMNS:
            raise ValueError(f"sort_by must be one of {', '.join(SORT_COLUMNS)}")
        if sort_dir not in SORT_DIRECTIONS:
            raise ValueError("sort_dir must be asc or desc")
        where, where_params = _build_where(filters)
        rows_sql = (
            f"SELECT {SELECT_COLUMNS}\n"
            f"FROM {self._view}\n"
            f"{where}\n"
            f"ORDER BY {sort_by} {sort_dir}, material ASC, stock_plant ASC\n"
            "LIMIT :limit OFFSET :offset"
        )
        rows = self._run(rows_sql, {**where_params, "limit": limit, "offset": offset})
        count_sql = f"SELECT COUNT(*) AS total FROM {self._view} {where}"
        count_rows = self._run(count_sql, dict(where_params))
        total = int(count_rows[0]["total"]) if count_rows else 0
        freshness = self.fetch_freshness()
        return CandidatePage(
            items=[_to_candidate_row(d) for d in rows],
            total=total,
            mrp_snapshot_date=freshness.mrp_snapshot_date,
            inventory_month=freshness.inventory_month,
            limit=limit,
            offset=offset,
        )

    def fetch_material_detail(self, material: str, short_plant: str) -> MaterialDetail | None:
        """All holding plants of one shortage, movable_qty desc; None when no row exists."""
        sql = (
            f"SELECT {SELECT_COLUMNS}\n"
            f"FROM {self._view}\n"
            "WHERE material = :material AND short_plant = :short_plant\n"
            "ORDER BY movable_qty DESC, stock_plant ASC"
        )
        rows = self._run(sql, {"material": material, "short_plant": short_plant})
        if not rows:
            return None
        first = _to_candidate_row(rows[0])
        holding_plants = [
            HoldingPlant(
                stock_plant=row.stock_plant,
                stock_plant_name=row.stock_plant_name,
                stock_plant_country=row.stock_plant_country,
                stock_qty=row.stock_qty,
                movable_qty=row.movable_qty,
            )
            for row in (_to_candidate_row(d) for d in rows)
        ]
        return MaterialDetail(
            material=first.material,
            material_description=first.material_description,
            material_type=first.material_type,
            product_family=first.product_family,
            criticality=first.criticality,
            short_plant=first.short_plant,
            short_plant_name=first.short_plant_name,
            short_plant_country=first.short_plant_country,
            shortage_qty=first.shortage_qty,
            weeks_late=first.weeks_late,
            unit_of_measure=first.unit_of_measure,
            mrp_snapshot_date=first.mrp_snapshot_date,
            inventory_month=first.inventory_month,
            holding_plants=holding_plants,
        )

    def fetch_filter_options(self) -> FilterOptions:
        """Distinct plants, countries, criticalities, families and the freshness."""
        plants = self._run(
            "SELECT DISTINCT short_plant AS code, short_plant_name AS name, "
            "short_plant_country AS country\n"
            f"FROM {self._view} ORDER BY code ASC",
            {},
        )
        countries = self._run(
            f"SELECT DISTINCT short_plant_country AS country FROM {self._view}\n"
            "WHERE short_plant_country IS NOT NULL ORDER BY country ASC",
            {},
        )
        criticalities = self._run(
            f"SELECT DISTINCT COALESCE(criticality, '{CRITICALITY_NONE}') AS criticality "
            f"FROM {self._view} ORDER BY criticality ASC",
            {},
        )
        families = self._run(
            f"SELECT DISTINCT product_family FROM {self._view}\n"
            "WHERE product_family IS NOT NULL ORDER BY product_family ASC",
            {},
        )
        freshness = self.fetch_freshness()
        present = {d["criticality"] for d in criticalities}
        return FilterOptions(
            short_plants=[PlantOption(**d) for d in plants],
            countries=[d["country"] for d in countries],
            criticalities=[v for v in CRITICALITY_VALUES if v in present],
            product_families=[d["product_family"] for d in families],
            mrp_snapshot_date=freshness.mrp_snapshot_date,
            inventory_month=freshness.inventory_month,
        )

    def fetch_freshness(self) -> Freshness:
        """MAX(mrp_snapshot_date), MAX(inventory_month) of the view."""
        rows = self._run(
            "SELECT MAX(mrp_snapshot_date) AS mrp_snapshot_date, "
            f"MAX(inventory_month) AS inventory_month FROM {self._view}",
            {},
        )
        if not rows:
            return Freshness(mrp_snapshot_date=None, inventory_month=None)
        return Freshness(
            mrp_snapshot_date=rows[0]["mrp_snapshot_date"],
            inventory_month=rows[0]["inventory_month"],
        )
