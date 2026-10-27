from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import repository
from core.errors import NotFoundError
from shared.repositories.master_lists import MasterListRepository
from shared.schemas import MasterKeysOut, MasterListOut, MasterOptionOut

router = APIRouter(prefix="/api/v1/master", tags=["master"])

get_repo = repository(MasterListRepository)


@router.get("", response_model=MasterKeysOut, summary="Available list keys")
def list_keys(repo: MasterListRepository = Depends(get_repo)) -> MasterKeysOut:
    return MasterKeysOut(keys=repo.list_keys())


@router.get("/{list_key}", response_model=MasterListOut, summary="Options of one dropdown list")
def get_list(
    list_key: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$"),
    country: str | None = Query(None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2"),
    crop: str | None = Query(None, min_length=1, max_length=32),
    repo: MasterListRepository = Depends(get_repo),
) -> MasterListOut:
    """Rows scoped to ``country``/``crop`` plus global rows (scope NULL), ordered for display."""
    if not repo.key_exists(list_key):
        raise NotFoundError(
            f"Master list '{list_key}' does not exist.",
            code="master_list_not_found",
            details={"list_key": list_key},
        )
    rows = repo.options(list_key, country=country, crop=crop)
    return MasterListOut(
        list_key=list_key,
        country=country.upper() if country else None,
        crop=crop.lower() if crop else None,
        items=[MasterOptionOut.model_validate(r) for r in rows],
    )
