from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import repository
from core.errors import NotFoundError
from shared.repositories.sites import SiteRepository
from shared.schemas import SiteOut

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])

get_repo = repository(SiteRepository)


@router.get("", response_model=list[SiteOut], summary="Delivery sites (ginners and processors)")
def list_sites(
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    repo: SiteRepository = Depends(get_repo),
) -> list[SiteOut]:
    return [SiteOut.model_validate(s) for s in repo.list_filtered(crop=crop)]


@router.get("/{site_id}", response_model=SiteOut, summary="One site")
def get_site(site_id: str, repo: SiteRepository = Depends(get_repo)) -> SiteOut:
    site = repo.get(site_id)
    if site is None:
        raise NotFoundError("Site not found.", code="site_not_found")
    return SiteOut.model_validate(site)
