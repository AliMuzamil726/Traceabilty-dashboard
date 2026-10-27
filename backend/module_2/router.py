"""HTTP routes for Module 2 (Register Farmer), mounted at ``/api/v1/register``.

Routes parse input, call a service and shape the response. They never touch the
session directly and never contain a rule: everything is in
:mod:`module_2.services`, so the same behaviour applies however it is reached.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.orm import Session

from core.config import Settings
from core.deps import CurrentOfficer, get_current_officer, get_db, get_settings_dep
from core.errors import AppError
from core.pagination import Page, PageParams, page_params
from module_2 import meta, services
from module_2.schemas import (
    FarmerFieldsOut,
    FarmerIn,
    FarmerListItemOut,
    FarmerLookupOut,
    FarmerOut,
    FarmerProfileOut,
    FarmerSavedOut,
    FieldOut,
    FieldUpdateIn,
    GeometryIn,
    GeometryValidationOut,
    LocationListOut,
    LocationOptionOut,
    MapFieldsOut,
    PostcodeOut,
    ValidateGeometryIn,
)
from module_2.services.fields import MAP_FEATURE_LIMIT
from module_2.services.permissions import require_may_act
from module_2.services.ratelimit import lookup_limiter
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])


def get_farmer_service(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> services.FarmerService:
    return services.FarmerService(session, settings=settings)


def get_field_service(session: Session = Depends(get_db)) -> services.FieldService:
    return services.FieldService(session)


def get_location_service(session: Session = Depends(get_db)) -> services.LocationService:
    return services.LocationService(session)


def get_postcode_service(session: Session = Depends(get_db)) -> services.PostcodeService:
    return services.PostcodeService(session)


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


# ------------------------------------------------------------------------- farmers


@router.get("/farmers", response_model=Page[FarmerListItemOut], summary="Search farmers")
def list_farmers(
    q: str | None = Query(None, max_length=120, description="SAWIE ID, name, ID number or phone"),
    crop: str | None = Query(None, max_length=16),
    field_office_id: str | None = Query(None, max_length=36),
    registered_by: str | None = Query(None, max_length=36),
    params: PageParams = Depends(page_params),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> Page[FarmerListItemOut]:
    """Officers see the farmers they registered; administrators see every farmer."""
    return service.search(
        params,
        officer,
        q=q,
        crop=crop,
        field_office_id=field_office_id,
        registered_by=registered_by,
    )


@router.get(
    "/farmers/lookup",
    response_model=FarmerLookupOut,
    summary="Is this ID number already registered?",
)
def lookup_farmer(
    request: Request,
    id_number: str = Query(..., min_length=1, max_length=64),
    crop: str = Query(..., max_length=16),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> FarmerLookupOut:
    """Returns the SAWIE ID and personal data of an existing farmer, or a preview ID.

    Crop data is never returned: the officer enters this season's values. Rate limited
    per officer and client address so the endpoint cannot be used to test ID numbers.
    """
    client = request.client.host if request.client else "unknown"
    allowed, retry_after = lookup_limiter.check(f"{officer.id}:{client}")
    if not allowed:
        raise RateLimitedError(
            "Too many lookups. Wait a moment and try again.",
            details={"retry_after_seconds": retry_after},
        )
    return service.lookup_for_officer(id_number, crop, officer)


@router.post(
    "/farmers",
    response_model=FarmerSavedOut,
    status_code=201,
    summary="Register a farmer (or update an existing one and add this season)",
)
def create_farmer(
    payload: FarmerIn,
    response: Response,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> FarmerSavedOut:
    result = service.save(payload, officer)
    if not result.created:
        response.status_code = 200
    return result


@router.get("/farmers/{farmer_id}", response_model=FarmerOut, summary="One farmer")
def get_farmer(
    farmer_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> FarmerOut:
    return service.to_out(service.require_farmer(farmer_id), officer)


@router.put("/farmers/{farmer_id}", response_model=FarmerSavedOut, summary="Update a farmer")
def update_farmer(
    payload: FarmerIn,
    farmer_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> FarmerSavedOut:
    return service.update(farmer_id, payload, officer)


@router.get(
    "/farmers/{farmer_id}/profile",
    response_model=FarmerProfileOut,
    summary="Farmer, season profiles, fields and completeness",
)
def get_farmer_profile(
    farmer_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FarmerService = Depends(get_farmer_service),
) -> FarmerProfileOut:
    return service.profile(farmer_id, officer)


# -------------------------------------------------------------------------- fields


@router.get(
    "/farmers/{farmer_id}/fields",
    response_model=FarmerFieldsOut,
    summary="This farmer's mapped fields",
)
def list_farmer_fields(
    farmer_id: str = Path(..., max_length=36),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> FarmerFieldsOut:
    farmer = service.require_farmer(farmer_id)
    fields = service.list_for_farmer(farmer.id)
    return FarmerFieldsOut(
        items=[service.to_out(f) for f in fields],
        total=len(fields),
        next_field_id_preview=service.next_field_id_preview(farmer.sawie_id),
    )


@router.post(
    "/farmers/{farmer_id}/fields",
    response_model=FieldOut,
    status_code=201,
    summary="Save a mapped field",
)
def create_field(
    payload: GeometryIn,
    farmer_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> FieldOut:
    require_may_act(service.require_farmer(farmer_id), officer)
    field = service.create(
        farmer_id,
        payload.geometry,
        pin_lat=payload.pin_lat,
        pin_lng=payload.pin_lng,
        officer_id=officer.id,
    )
    return service.to_out(field)


@router.post(
    "/fields/validate-geometry",
    response_model=GeometryValidationOut,
    summary="Live geometry and overlap check while drawing",
)
def validate_geometry(
    payload: ValidateGeometryIn,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> GeometryValidationOut:
    """Always answers 200. ``valid`` tells the map whether Save may be enabled."""
    return service.validate_geometry(
        payload.geometry,
        payload.farmer_id,
        pin_lat=payload.pin_lat,
        pin_lng=payload.pin_lng,
        exclude_field_id=payload.exclude_field_id,
    )


@router.get("/fields/map", response_model=MapFieldsOut, summary="Every field, for the map layer")
def map_fields(
    bbox: str | None = Query(
        None, description="min_lng,min_lat,max_lng,max_lat; omit for everything"
    ),
    zoom: int | None = Query(None, ge=0, le=22),
    crop: str | None = Query(None, max_length=16),
    limit: int = Query(MAP_FEATURE_LIMIT, ge=1, le=MAP_FEATURE_LIMIT),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> MapFieldsOut:
    return service.map_fields(_parse_bbox(bbox), zoom=zoom, crop=crop, limit=limit)


@router.put("/fields/{field_id}", response_model=FieldOut, summary="Reshape or re-pin a field")
def update_field(
    payload: FieldUpdateIn,
    field_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> FieldOut:
    require_may_act(service.require_farmer(service.require_field(field_id).farmer_id), officer)
    field = service.update(
        field_id,
        geojson=payload.geometry,
        pin_lat=payload.pin_lat,
        pin_lng=payload.pin_lng,
        officer_id=officer.id,
    )
    return service.to_out(field)


@router.get("/fields/{field_id}", response_model=FieldOut, summary="One field")
def get_field(
    field_id: str = Path(..., max_length=36),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> FieldOut:
    return service.to_out(service.require_field(field_id))


@router.delete("/fields/{field_id}", status_code=204, summary="Remove a field (soft delete)")
def delete_field(
    field_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.FieldService = Depends(get_field_service),
) -> Response:
    require_may_act(service.require_farmer(service.require_field(field_id).farmer_id), officer)
    service.delete(field_id, officer_id=officer.id)
    return Response(status_code=204)


# ----------------------------------------------------------------------- locations


@router.get("/locations/provinces", response_model=LocationListOut, summary="Provinces")
def list_provinces(
    country: str = Query("PK", min_length=2, max_length=2),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.LocationService = Depends(get_location_service),
) -> LocationListOut:
    return LocationListOut(
        items=[LocationOptionOut(**vars(o)) for o in service.provinces(country.upper())]
    )


@router.get("/locations/districts", response_model=LocationListOut, summary="Districts")
def list_districts(
    province: str = Query(..., min_length=1, max_length=64, description="Province code"),
    country: str = Query("PK", min_length=2, max_length=2),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.LocationService = Depends(get_location_service),
) -> LocationListOut:
    return LocationListOut(
        items=[LocationOptionOut(**vars(o)) for o in service.districts(country.upper(), province)]
    )


@router.get("/locations/tehsils", response_model=LocationListOut, summary="Tehsils of a district")
def list_tehsils(
    district: str = Query(..., min_length=1, max_length=64, description="District code"),
    country: str = Query("PK", min_length=2, max_length=2),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.LocationService = Depends(get_location_service),
) -> LocationListOut:
    """Districts without a seeded tehsil list return an empty list and ``allow_manual``."""
    items = [LocationOptionOut(**vars(o)) for o in service.tehsils(country.upper(), district)]
    return LocationListOut(items=items, allow_manual=True)


@router.get(
    "/locations/villages/suggest",
    response_model=list[str],
    summary="Villages already entered in a tehsil",
)
def suggest_villages(
    tehsil: str = Query(..., min_length=1, max_length=120, description="Tehsil name"),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(10, ge=1, le=50),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.LocationService = Depends(get_location_service),
) -> list[str]:
    return service.village_suggestions(tehsil, q, limit=limit)


@router.get(
    "/uk/postcode/{postcode}", response_model=PostcodeOut, summary="County and region of a postcode"
)
def lookup_postcode(
    postcode: str = Path(..., min_length=3, max_length=12),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.PostcodeService = Depends(get_postcode_service),
) -> PostcodeOut:
    """Cache, then postcodes.io, then the bundled postcode-area table."""
    found = service.lookup(postcode)
    service.session.commit()  # persist a newly cached answer
    return PostcodeOut(
        postcode=found.postcode,
        county=found.county,
        region=found.region,
        source=found.source,
        resolved=found.resolved,
        editable=found.editable,
    )


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    """``"60.1,29.9,60.5,30.2"`` -> a tuple, or ``None`` when absent."""
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        raise AppError(
            "bbox must be four numbers: min_lng,min_lat,max_lng,max_lat.",
            code="bad_request",
        )
    try:
        min_lng, min_lat, max_lng, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise AppError("bbox values must be numbers.", code="bad_request") from exc
    if min_lng > max_lng or min_lat > max_lat:
        raise AppError("bbox minimum values must not exceed the maximums.", code="bad_request")
    return (min_lng, min_lat, max_lng, max_lat)
