"""API-03: the filter options and data freshness (v2/F-03)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models import FilterOptions
from backend.services.transfer_candidate_service import get_filter_options

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("")
def get_filters(request: Request) -> FilterOptions:
    """Return the distinct filter values present in the view and the freshness."""
    repo = request.app.state.repository
    return get_filter_options(repo)
