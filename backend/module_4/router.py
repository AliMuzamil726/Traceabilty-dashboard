"""HTTP routes for Module 4 (Harvest Radar), mounted at ``/api/v1/radar``.

Every read takes the same filter parameters, so the table, map, calendar, summary and
export always describe the same set of fields.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.deps import CurrentOfficer, get_current_officer, get_db
from core.pagination import Page, PageParams, page_params
from module_2 import public_api as farms
from module_3 import public_api as fieldbooks
from module_4 import meta, services
from module_4.models import STATUS_REQUESTED, PickupRequest
from module_4.repository import PickupRequestRepository
from module_4.schemas import (
    CalendarOut,
    CancelIn,
    ClockOut,
    FacetsOut,
    FieldsPageOut,
    KpisOut,
    OptionOut,
    PickupRequestIn,
    PickupRequestOut,
    PickupResultOut,
    RadarRowOut,
    SkippedOut,
    SummaryOut,
    TotalsOut,
)
from module_4.services import config
from module_4.services.dataset import RadarRow
from module_4.services.radar import RadarView
from module_4.services.readiness import BUCKET_LABELS, REQUESTABLE
from shared.repositories.officers import OfficerRepository
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])


def this_year() -> int:
    return datetime.now(UTC).year


def radar_filters(
    crop: str = Query("cotton", pattern=r"^(cotton|hemp)$"),
    season_year: int | None = Query(None, ge=2000, le=2100),
    q: str | None = Query(None, max_length=120),
    district: str | None = Query(None, max_length=120),
    tehsil: str | None = Query(None, max_length=120),
    village: str | None = Query(None, max_length=120),
    county: str | None = Query(None, max_length=120),
    region: str | None = Query(None, max_length=120),
    field_office_id: str | None = Query(None, max_length=36),
    officer_id: str | None = Query(None, max_length=36),
    status: str | None = Query(None, max_length=32),
    pickup: str | None = Query(None, max_length=32),
    ready_from: date | None = Query(None),
    ready_to: date | None = Query(None),
    scope: str = Query("mine", pattern=r"^(mine|all)$"),
    field_ids: str | None = Query(None, max_length=20_000, description="Comma-separated"),
) -> services.RadarFilters:
    return services.RadarFilters(
        crop=crop,
        season_year=season_year or this_year(),
        q=(q or "").strip() or None,
        district=district or None,
        tehsil=tehsil or None,
        village=village or None,
        county=county or None,
        region=region or None,
        field_office_id=field_office_id or None,
        officer_id=officer_id or None,
        status=status or None,
        pickup=pickup or None,
        ready_from=ready_from,
        ready_to=ready_to,
        scope=scope,
        field_ids=tuple(i for i in field_ids.split(",") if i) if field_ids else None,
    ).validate()


def get_radar(session: Session = Depends(get_db)) -> services.RadarService:
    return services.RadarService(session)


def get_pickups(session: Session = Depends(get_db)) -> services.PickupService:
    return services.PickupService(session)


# --------------------------------------------------------------------------- mapping


def row_out(row: RadarRow, officer: CurrentOfficer) -> RadarRowOut:
    can_act = services.RadarService.can_act(row, officer)
    r = row.readiness
    return RadarRowOut(
        field_id=row.field_id,
        field_code=row.field_code,
        farmer_id=row.farmer_id,
        sawie_id=row.sawie_id,
        farmer_name=row.farmer_name,
        father_or_farm=row.father_or_farm,
        location=row.location,
        district=row.district,
        tehsil=row.tehsil,
        village=row.village,
        county=row.county,
        region=row.region,
        field_office_id=row.field_office_id,
        field_office_name=row.field_office_name,
        officer_id=row.officer_id,
        officer_name=row.officer_name,
        area_acre=row.area_acre,
        area_ha=row.area_ha,
        centroid_lat=row.centroid_lat,
        centroid_lng=row.centroid_lng,
        fieldbook_id=row.fieldbook_id,
        sowing_date=row.sowing_date,
        days_after_sowing=r.days_after_sowing,
        progress=r.progress,
        status=row.status,
        status_label=BUCKET_LABELS[row.status],
        overdue=r.overdue,
        expected_ready=r.expected_ready,
        next_milestone=r.next_milestone,
        estimated_kg=row.estimated_kg,
        estimate_is_benchmark=row.estimate_is_benchmark,
        pickup_state=row.pickup_state,
        request_id=row.request_id,
        request_no=row.request_no,
        can_act=can_act,
        can_request=can_act and row.status in REQUESTABLE and not row.has_open_request,
    )


def _summary(session: Session, f: services.RadarFilters, view: RadarView) -> dict[str, object]:
    clock = fieldbooks.get_crop_clocks(session)[f.crop]
    k = view.kpis
    return {
        "crop": f.crop,
        "season_year": f.season_year,
        "area_unit": view.area_unit,
        "buckets": view.buckets,
        "kpis": KpisOut(
            ready_now=TotalsOut(**vars(k.ready_now)),
            approaching_soon=TotalsOut(**vars(k.approaching_soon)),
            pickup_requested=TotalsOut(**vars(k.pickup_requested)),
            overdue=TotalsOut(**vars(k.overdue)),
            approaching_window_days=config.APPROACHING_WINDOW_DAYS,
        ),
        "clock": ClockOut(
            approach_day=clock.approach_day,
            ready_day=clock.ready_day,
            window_end_day=clock.window_end_day,
        ),
        "generated_at": view.generated_at,
        "total_fields": sum(view.buckets.values()),
    }


def request_out(
    request: PickupRequest,
    officer: CurrentOfficer,
    *,
    farmers: dict[str, farms.FarmerDTO] | None = None,
    officer_names: dict[str, str] | None = None,
) -> PickupRequestOut:
    farmer = (farmers or {}).get(request.farmer_id)
    may_act = officer.sees_all or (farmer is not None and farmer.registered_by == officer.id)
    return PickupRequestOut(
        id=request.id,
        request_no=request.request_no,
        field_id=request.field_id,
        field_code=request.field_code,
        farmer_id=request.farmer_id,
        farmer_name=farmer.name if farmer else None,
        sawie_id=farmer.sawie_id if farmer else None,
        crop=request.crop,
        season_year=request.season_year,
        status=request.status,
        estimated_quantity_kg=request.estimated_quantity_kg,
        quantity_is_estimate=request.quantity_is_estimate,
        preferred_date=request.preferred_date,
        note=request.note,
        requested_by=request.requested_by,
        requested_by_name=(officer_names or {}).get(request.requested_by or ""),
        requested_at=request.requested_at,
        cancelled_by=request.cancelled_by,
        cancelled_at=request.cancelled_at,
        cancel_reason=request.cancel_reason,
        delivery_id=request.delivery_id,
        updated_at=request.updated_at,
        can_cancel=may_act and request.status == STATUS_REQUESTED,
    )


def _names(session: Session) -> dict[str, str]:
    return {o.id: o.full_name for o in OfficerRepository(session).list_all()}


# --------------------------------------------------------------------------- routes


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


@router.get("/fields", response_model=FieldsPageOut, summary="Radar rows with buckets and KPIs")
def list_fields(
    sort: str | None = Query(None, max_length=32),
    params: PageParams = Depends(page_params),
    f: services.RadarFilters = Depends(radar_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    radar: services.RadarService = Depends(get_radar),
) -> FieldsPageOut:
    view = radar.view(f, officer)
    rows = radar.sort(view.rows, sort)
    page = rows[params.offset : params.offset + params.page_size]
    facets = view.facets
    return FieldsPageOut(
        **_summary(radar.session, f, view),  # type: ignore[arg-type]
        items=[row_out(r, officer) for r in page],
        total=len(rows),
        page=params.page,
        page_size=params.page_size,
        facets=FacetsOut(
            districts=facets["districts"],
            tehsils=facets["tehsils"],
            villages=facets["villages"],
            counties=facets["counties"],
            regions=facets["regions"],
            offices=[OptionOut(value=v, label=label) for v, label in facets["offices"]],
            officers=[OptionOut(value=v, label=label) for v, label in facets["officers"]],
        ),
        is_admin=officer.sees_all,
    )


@router.get("/summary", response_model=SummaryOut, summary="Bucket counts and KPI totals")
def summary(
    f: services.RadarFilters = Depends(radar_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    radar: services.RadarService = Depends(get_radar),
) -> SummaryOut:
    return SummaryOut(**_summary(radar.session, f, radar.view(f, officer)))  # type: ignore[arg-type]


@router.get("/map", summary="GeoJSON FeatureCollection of the filtered fields, with status")
def map_features(
    f: services.RadarFilters = Depends(radar_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    radar: services.RadarService = Depends(get_radar),
) -> dict[str, object]:
    return radar.map_features(f, officer)


@router.get("/calendar", response_model=CalendarOut, summary="Expected-ready dates by day")
def calendar(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    f: services.RadarFilters = Depends(radar_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    radar: services.RadarService = Depends(get_radar),
) -> CalendarOut:
    return CalendarOut.model_validate(radar.calendar(f, officer, month))


@router.get("/export.csv", summary="The filtered rows as CSV (UTF-8 with BOM)")
def export_csv(
    sort: str | None = Query(None, max_length=32),
    f: services.RadarFilters = Depends(radar_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    radar: services.RadarService = Depends(get_radar),
) -> StreamingResponse:
    # Build the whole file before streaming, so the request's session is not needed
    # after the response starts.
    lines = list(radar.csv_rows(f, officer, sort))
    filename = f"radar_{f.crop}_{datetime.now(UTC).date().isoformat()}.csv"
    return StreamingResponse(
        iter(lines),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/pickup-requests",
    response_model=PickupResultOut,
    status_code=201,
    summary="Request pickup for several fields; ineligible fields are skipped with a reason",
)
def create_pickup_requests(
    body: PickupRequestIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    pickups: services.PickupService = Depends(get_pickups),
) -> PickupResultOut:
    created, skipped = pickups.request(
        officer,
        crop=body.crop,
        season_year=body.season_year,
        field_ids=body.field_ids,
        preferred_date=body.preferred_date,
        note=body.note,
    )
    session = pickups.session
    farmers = farms.get_farmers(session, [r.farmer_id for r in created])
    names = _names(session)
    return PickupResultOut(
        created=[request_out(r, officer, farmers=farmers, officer_names=names) for r in created],
        skipped=[SkippedOut(**vars(s)) for s in skipped],
    )


@router.get("/pickup-requests", response_model=Page[PickupRequestOut], summary="Pickup requests")
def list_pickup_requests(
    status: str | None = Query(None, pattern=r"^(requested|scheduled|fulfilled|cancelled)$"),
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    season_year: int | None = Query(None, ge=2000, le=2100),
    scope: str = Query("mine", pattern=r"^(mine|all)$"),
    params: PageParams = Depends(page_params),
    officer: CurrentOfficer = Depends(get_current_officer),
    session: Session = Depends(get_db),
) -> Page[PickupRequestOut]:
    farmer_ids = None
    if not officer.sees_all and scope == "mine":
        farmer_ids = [f.id for f in farms.list_farmers_for_officer(session, officer.id)]
    result = PickupRequestRepository(session).search(
        params, status=status, crop=crop, season_year=season_year, farmer_ids=farmer_ids
    )
    farmers = farms.get_farmers(session, list({r.farmer_id for r in result.rows}))
    names = _names(session)
    return Page[PickupRequestOut](
        items=[request_out(r, officer, farmers=farmers, officer_names=names) for r in result.rows],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "/pickup-requests/{request_id}/cancel",
    response_model=PickupRequestOut,
    summary="Cancel a request that is still waiting (a reason is required)",
)
def cancel_pickup_request(
    body: CancelIn,
    request_id: str = Path(..., max_length=36),
    officer: CurrentOfficer = Depends(get_current_officer),
    pickups: services.PickupService = Depends(get_pickups),
) -> PickupRequestOut:
    request = pickups.cancel(request_id, officer, body.reason)
    session = pickups.session
    return request_out(
        request,
        officer,
        farmers=farms.get_farmers(session, [request.farmer_id]),
        officer_names=_names(session),
    )
