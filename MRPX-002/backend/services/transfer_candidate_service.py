"""Input validation and use cases of the transfer candidate routes (v2/F-03)."""

from __future__ import annotations

import logging
import re

from backend.constants import (
    COUNTRY_PATTERN,
    CRITICALITY_VALUES,
    MATERIAL_PATTERN,
    PAGE_SIZE_MAX,
    PLANT_CODE_PATTERN,
    PRODUCT_FAMILY_PATTERN,
    SORT_COLUMNS,
    SORT_DIRECTIONS,
)
from backend.models import CandidateFilters, CandidatePage, FilterOptions, MaterialDetail
from backend.repositories.transfer_candidate_repository import TransferCandidateRepository

logger = logging.getLogger(__name__)


class NotFoundError(LookupError):
    """Raised when no T-01 row exists for the material and short plant."""


def _validate_codes(
    values: list[str], pattern: str, field: str, *, uppercase: bool = True
) -> list[str]:
    """Strip (and, unless uppercase is False, upper-case) each value; raise
    ValueError(f"{field} must match {pattern}") on mismatch."""
    codes = []
    for value in values:
        code = value.strip()
        if uppercase:
            code = code.upper()
        if not re.fullmatch(pattern, code):
            raise ValueError(f"{field} must match {pattern}")
        codes.append(code)
    return codes


def _validate_criticalities(values: list[str]) -> list[str]:
    """Upper-case each value; raise ValueError when one is not in CRITICALITY_VALUES."""
    criticalities = []
    for value in values:
        criticality = value.strip().upper()
        if criticality not in CRITICALITY_VALUES:
            raise ValueError(f"criticality must be one of {', '.join(CRITICALITY_VALUES)}")
        criticalities.append(criticality)
    return criticalities


def list_candidates(
    repo: TransferCandidateRepository,
    short_plant: list[str],
    country: list[str],
    criticality: list[str],
    product_family: list[str],
    sort_by: str,
    sort_dir: str,
    limit: int,
    offset: int,
) -> CandidatePage:
    """Validate inputs and return the page. Raises ValueError with the messages in §6 step 2."""
    filters = CandidateFilters(
        short_plants=_validate_codes(short_plant, PLANT_CODE_PATTERN, "short_plant"),
        countries=_validate_codes(country, COUNTRY_PATTERN, "country"),
        criticalities=_validate_criticalities(criticality),
        product_families=_validate_codes(product_family, PRODUCT_FAMILY_PATTERN, "product_family"),
    )
    if sort_by not in SORT_COLUMNS:
        raise ValueError(f"sort_by must be one of {', '.join(SORT_COLUMNS)}")
    if sort_dir not in SORT_DIRECTIONS:
        raise ValueError("sort_dir must be asc or desc")
    if not 1 <= limit <= PAGE_SIZE_MAX:
        raise ValueError(f"limit must be between 1 and {PAGE_SIZE_MAX}")
    if offset < 0:
        raise ValueError("offset must be 0 or more")
    return repo.fetch_candidates(filters, sort_by, sort_dir, limit, offset)


def get_filter_options(repo: TransferCandidateRepository) -> FilterOptions:
    """Return the filter options and freshness."""
    return repo.fetch_filter_options()


def get_material_detail(
    repo: TransferCandidateRepository, material: str, short_plant: str
) -> MaterialDetail:
    """Validate codes, fetch the detail. Raises NotFoundError(f"Material {material} is not short
    in plant {short_plant} in the current MRP result.")."""
    material = _validate_codes([material], MATERIAL_PATTERN, "material", uppercase=False)[0]
    short_plant = _validate_codes([short_plant], PLANT_CODE_PATTERN, "short_plant")[0]
    detail = repo.fetch_material_detail(material, short_plant)
    if detail is None:
        raise NotFoundError(
            f"Material {material} is not short in plant {short_plant} in the current MRP result."
        )
    return detail
