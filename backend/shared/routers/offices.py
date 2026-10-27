from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import repository
from core.errors import NotFoundError
from core.pagination import Page, PageParams, page_params
from shared.repositories.offices import FieldOfficeRepository
from shared.schemas import FieldOfficeOut

router = APIRouter(prefix="/api/v1/offices", tags=["offices"])

get_repo = repository(FieldOfficeRepository)


@router.get("", response_model=Page[FieldOfficeOut], summary="List field offices")
def list_offices(
    params: PageParams = Depends(page_params),
    country: str | None = Query(None, min_length=2, max_length=2),
    repo: FieldOfficeRepository = Depends(get_repo),
) -> Page[FieldOfficeOut]:
    result = repo.search(params, country=country)
    return Page[FieldOfficeOut](
        items=[FieldOfficeOut.model_validate(o) for o in result.rows],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{office_id}", response_model=FieldOfficeOut, summary="One field office")
def get_office(office_id: str, repo: FieldOfficeRepository = Depends(get_repo)) -> FieldOfficeOut:
    office = repo.get(office_id)
    if office is None:
        raise NotFoundError("Field office not found.", code="field_office_not_found")
    return FieldOfficeOut.model_validate(office)
