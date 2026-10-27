"""HTTP routes for Module 3 (Fieldbook), mounted at ``/api/v1/fieldbook``.

Writes accept an optional ``X-Fieldbook-Version`` header carrying the ``version`` the
client last saw. When present and stale the write is refused with 409
``fieldbook_stale``; the web app always sends it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Header, Path, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.config import Settings
from core.deps import CurrentOfficer, get_current_officer, get_db, get_settings_dep
from core.errors import NotFoundError
from core.pagination import Page, PageParams, page_params
from module_3 import meta, services
from module_3.schemas import (
    BookListItemOut,
    BookOut,
    EntryIn,
    FarmerOptionOut,
    FieldSelectorOut,
    NotApplicableIn,
    OfficerOptionOut,
    OpenBookIn,
    SaveResultOut,
    TimelineOut,
)
from module_3.services import formschema as fs
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

VERSION_HEADER = "X-Fieldbook-Version"
STEP_KEY = Path(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")


def get_service(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> services.FieldbookService:
    return services.FieldbookService(session, settings=settings)


def get_selectors(session: Session = Depends(get_db)) -> services.SelectorService:
    return services.SelectorService(session)


def version_header(
    x_fieldbook_version: int | None = Header(default=None, alias=VERSION_HEADER),
) -> int | None:
    return x_fieldbook_version


def this_year() -> int:
    return datetime.now(UTC).year


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


# ------------------------------------------------------------------- schemas


@router.get("/schemas/{crop}", summary="The form definition for one crop programme")
def get_schema(
    crop: str = Path(..., pattern=r"^[a-z]+$"),
    _officer: CurrentOfficer = Depends(get_current_officer),
) -> dict[str, Any]:
    """Served exactly as stored: the frontend renders from it and the server validates
    with it, so the two cannot drift."""
    return fs.load_definition(crop)


# ----------------------------------------------------------------- selectors


@router.get(
    "/selectors/officers",
    response_model=list[OfficerOptionOut],
    summary="Officers the acting officer may choose",
)
def selector_officers(
    officer: CurrentOfficer = Depends(get_current_officer),
    selectors: services.SelectorService = Depends(get_selectors),
) -> list[OfficerOptionOut]:
    return selectors.officers_for(officer)


@router.get(
    "/selectors/farmers",
    response_model=list[FarmerOptionOut],
    summary="Farmers registered by one officer",
)
def selector_farmers(
    officer_id: str = Query(..., max_length=36),
    q: str | None = Query(None, max_length=120),
    season_year: int | None = Query(None, ge=2000, le=2100),
    officer: CurrentOfficer = Depends(get_current_officer),
    selectors: services.SelectorService = Depends(get_selectors),
) -> list[FarmerOptionOut]:
    return selectors.farmers(officer, officer_id, q=q, season_year=season_year or this_year())


@router.get(
    "/selectors/fields",
    response_model=FieldSelectorOut,
    summary="A farmer's fields with their fieldbook status",
)
def selector_fields(
    farmer_id: str = Query(..., max_length=36),
    season_year: int | None = Query(None, ge=2000, le=2100),
    officer: CurrentOfficer = Depends(get_current_officer),
    selectors: services.SelectorService = Depends(get_selectors),
) -> FieldSelectorOut:
    return selectors.fields(officer, farmer_id, season_year or this_year())


# --------------------------------------------------------------------- books


@router.get("/books", response_model=Page[BookListItemOut], summary="Fieldbooks")
def list_books(
    season_year: int | None = Query(None, ge=2000, le=2100),
    status: str | None = Query(None, pattern=r"^(draft|submitted)$"),
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    farmer_id: str | None = Query(None, max_length=36),
    params: PageParams = Depends(page_params),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> Page[BookListItemOut]:
    return service.list_books(
        params, officer, season_year=season_year, status=status, crop=crop, farmer_id=farmer_id
    )


@router.post(
    "/books",
    response_model=BookOut,
    status_code=201,
    summary="Open a fieldbook (creates the draft, or returns the existing one)",
)
def open_book(
    payload: OpenBookIn,
    response: Response,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    book, created = service.open(payload.field_id, payload.season_year, officer, crop=payload.crop)
    if not created:
        response.status_code = 200
    return book


@router.get("/books/{book_id}", response_model=BookOut, summary="One fieldbook")
def get_book(
    book_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    return service.get(book_id, officer)


@router.delete("/books/{book_id}", status_code=204, summary="Delete a draft fieldbook")
def delete_book(
    book_id: str = Path(..., max_length=36),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> Response:
    service.delete_book(book_id, officer, version=version)
    return Response(status_code=204)


@router.put(
    "/books/{book_id}/steps/{step_key}",
    response_model=SaveResultOut,
    summary="Save a single-entry step",
)
def save_step(
    payload: EntryIn,
    book_id: str = Path(..., max_length=36),
    step_key: str = STEP_KEY,
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> SaveResultOut:
    return service.save_single(book_id, step_key, payload, officer, version=version)


@router.post(
    "/books/{book_id}/steps/{step_key}/entries",
    response_model=SaveResultOut,
    status_code=201,
    summary="Add an entry to a repeatable step",
)
def add_entry(
    payload: EntryIn,
    book_id: str = Path(..., max_length=36),
    step_key: str = STEP_KEY,
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> SaveResultOut:
    return service.save_entry(book_id, step_key, payload, officer, version=version)


@router.put(
    "/books/{book_id}/steps/{step_key}/entries/{index}",
    response_model=SaveResultOut,
    summary="Replace one entry of a repeatable step",
)
def update_entry(
    payload: EntryIn,
    book_id: str = Path(..., max_length=36),
    step_key: str = STEP_KEY,
    index: int = Path(..., ge=0, le=10_000),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> SaveResultOut:
    return service.save_entry(book_id, step_key, payload, officer, version=version, index=index)


@router.delete(
    "/books/{book_id}/steps/{step_key}/entries/{index}",
    response_model=BookOut,
    summary="Delete one entry of a repeatable step",
)
def delete_entry(
    book_id: str = Path(..., max_length=36),
    step_key: str = STEP_KEY,
    index: int = Path(..., ge=0, le=10_000),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    return service.delete_entry(book_id, step_key, index, officer, version=version)


@router.post(
    "/books/{book_id}/steps/{step_key}/not-applicable",
    response_model=BookOut,
    summary="Mark a step as nothing to record (or undo it)",
)
def not_applicable(
    payload: NotApplicableIn,
    book_id: str = Path(..., max_length=36),
    step_key: str = STEP_KEY,
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    return service.set_not_applicable(
        book_id, step_key, payload.not_applicable, officer, version=version, crop=payload.crop
    )


@router.post(
    "/books/{book_id}/photos",
    response_model=BookOut,
    status_code=201,
    summary="Upload photos (JPEG, PNG or WebP, 8 MB each, 8 per fieldbook)",
)
async def add_photos(
    book_id: str = Path(..., max_length=36),
    files: list[UploadFile] = File(...),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    from module_3.services.photos import MAX_BYTES, PayloadTooLargeError

    payload: list[tuple[str, bytes]] = []
    for upload in files:
        # Read one byte past the limit so an oversize file is caught without holding it all.
        content = await upload.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise PayloadTooLargeError(
                f"{upload.filename} is larger than 8 MB.", details={"name": upload.filename}
            )
        payload.append((upload.filename or "photo", content))
    return service.add_photos(book_id, payload, officer, version=version)


@router.delete(
    "/books/{book_id}/photos/{photo_id}", response_model=BookOut, summary="Remove a photo"
)
def delete_photo(
    book_id: str = Path(..., max_length=36),
    photo_id: str = Path(..., max_length=36),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    return service.delete_photo(book_id, photo_id, officer, version=version)


@router.get(
    "/books/{book_id}/photos/{photo_id}",
    summary="A photo or its thumbnail",
    response_class=FileResponse,
)
def get_photo(
    book_id: str = Path(..., max_length=36),
    photo_id: str = Path(..., max_length=36),
    size: str | None = Query(None, pattern=r"^thumb$"),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> FileResponse:
    """Served through the officer dependency, so it is ready for real authentication."""
    path, mime = service.photo_file(book_id, photo_id, officer, thumb=size == "thumb")
    if not path.is_file():
        raise NotFoundError("The photo file is missing.", code="photo_not_found")
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})


@router.post(
    "/books/{book_id}/submit",
    response_model=BookOut,
    summary="Submit and permanently lock the fieldbook",
)
def submit_book(
    book_id: str = Path(..., max_length=36),
    version: int | None = Depends(version_header),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> BookOut:
    return service.submit(book_id, officer, version=version)


@router.get(
    "/books/{book_id}/timeline",
    response_model=TimelineOut,
    summary="Activity log of every saved entry",
)
def get_timeline(
    book_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldbookService = Depends(get_service),
) -> TimelineOut:
    return service.timeline(book_id, officer)
