"""Pydantic request and response models of the API (v2/F-02)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class CandidateFilters(BaseModel):
    """Filters of the transfer candidate list; empty lists mean no filter."""

    model_config = ConfigDict(extra="forbid")

    short_plants: list[str] = []
    countries: list[str] = []
    criticalities: list[str] = []  # values among A, B, C, NONE
    product_families: list[str] = []


class CandidateRow(BaseModel):
    """One T-01 row: a material short in one plant with stock in another plant."""

    model_config = ConfigDict(extra="forbid")

    material: str
    material_description: str | None
    material_type: str | None
    product_family: str | None
    criticality: str | None
    short_plant: str
    short_plant_name: str
    short_plant_country: str | None
    stock_plant: str
    stock_plant_name: str
    stock_plant_country: str | None
    shortage_qty: float
    stock_qty: float
    movable_qty: float
    weeks_late: int
    unit_of_measure: str | None
    mrp_snapshot_date: date
    inventory_month: str


class CandidatePage(BaseModel):
    """Body of API-01: one page of candidates, the total and the data freshness."""

    model_config = ConfigDict(extra="forbid")

    items: list[CandidateRow]
    total: int
    mrp_snapshot_date: date | None
    inventory_month: str | None
    limit: int
    offset: int


class HoldingPlant(BaseModel):
    """A plant holding stock of a short material."""

    model_config = ConfigDict(extra="forbid")

    stock_plant: str
    stock_plant_name: str
    stock_plant_country: str | None
    stock_qty: float
    movable_qty: float


class MaterialDetail(BaseModel):
    """Body of API-02: one shortage with all its holding plants."""

    model_config = ConfigDict(extra="forbid")

    material: str
    material_description: str | None
    material_type: str | None
    product_family: str | None
    criticality: str | None
    short_plant: str
    short_plant_name: str
    short_plant_country: str | None
    shortage_qty: float
    weeks_late: int
    unit_of_measure: str | None
    mrp_snapshot_date: date
    inventory_month: str
    holding_plants: list[HoldingPlant]


class PlantOption(BaseModel):
    """A short plant offered as a filter value."""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    country: str | None


class FilterOptions(BaseModel):
    """Body of API-03: the distinct filter values present in the view."""

    model_config = ConfigDict(extra="forbid")

    short_plants: list[PlantOption]
    countries: list[str]
    criticalities: list[str]  # subset of A, B, C, NONE present in the view
    product_families: list[str]
    mrp_snapshot_date: date | None
    inventory_month: str | None


class Freshness(BaseModel):
    """Latest MRP snapshot date and inventory month of the view."""

    model_config = ConfigDict(extra="forbid")

    mrp_snapshot_date: date | None
    inventory_month: str | None


class HealthResponse(BaseModel):
    """Body of API-04."""

    model_config = ConfigDict(extra="forbid")

    status: str
    catalog: str
    schema_gold: str
