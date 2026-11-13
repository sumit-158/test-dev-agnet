"""API-01: the filtered, sorted and paged transfer candidate list (v2/F-03)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.constants import PAGE_SIZE_DEFAULT, SORT_DEFAULT, SORT_DIR_DEFAULT
from backend.models import CandidatePage, MaterialDetail
from backend.services.transfer_candidate_service import get_material_detail, list_candidates

router = APIRouter(prefix="/api/transfer-candidates", tags=["transfer-candidates"])


@router.get("")
def get_transfer_candidates(
    request: Request,
    short_plant: list[str] = Query(default=[]),  # noqa: B008 - FastAPI Query default
    country: list[str] = Query(default=[]),  # noqa: B008 - FastAPI Query default
    criticality: list[str] = Query(default=[]),  # noqa: B008 - FastAPI Query default
    product_family: list[str] = Query(default=[]),  # noqa: B008 - FastAPI Query default
    sort_by: str = Query(default=SORT_DEFAULT),
    sort_dir: str = Query(default=SORT_DIR_DEFAULT),
    limit: int = Query(default=PAGE_SIZE_DEFAULT),
    offset: int = Query(default=0),
) -> CandidatePage:
    """Return one page of transfer candidates for the filters."""
    repo = request.app.state.repository
    return list_candidates(
        repo, short_plant, country, criticality, product_family, sort_by, sort_dir, limit, offset
    )


@router.get("/{material}/{short_plant}", response_model=MaterialDetail)
def get_transfer_candidate_detail(
    request: Request, material: str, short_plant: str
) -> MaterialDetail:
    """API-02: one shortage with every plant holding stock for it."""
    return get_material_detail(request.app.state.repository, material, short_plant)
