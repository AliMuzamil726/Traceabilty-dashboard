"""HTTP routes for Module 5 (Deliveries), mounted at ``/api/v1/deliveries``."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from core.deps import CurrentOfficer, get_current_officer, get_db
from core.errors import ForbiddenError, NotFoundError
from core.pagination import PageParams, page_params
from module_5 import meta, services
from module_5.models import Delivery
from module_5.schemas import (
    CancelIn,
    CorrectIn,
    DeliveryDetailOut,
    DeliveryOut,
    DeliveryPageOut,
    DispatchIn,
    HistoryOut,
    InboxItemOut,
    ReceiveIn,
    ScheduleIn,
    ScheduleResultOut,
    SiteRefOut,
    SkippedOut,
    StatsOut,
    ThresholdsOut,
    TransitionOut,
    UpdateIn,
)
from module_5.services.queries import Context
from module_5.services.slip import render_slip, weight_text
from module_5.services.weights import maunds
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

DELIVERY_ID = Path(..., max_length=36)


def get_service(session: Session = Depends(get_db)) -> services.DeliveryService:
    return services.DeliveryService(session)


def get_queries(session: Session = Depends(get_db)) -> services.DeliveryQueries:
    return services.DeliveryQueries(session)


def delivery_filters(
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    status: str | None = Query(None, pattern=r"^(scheduled|in_transit|delivered|cancelled)$"),
    site_id: str | None = Query(None, max_length=36),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    officer_id: str | None = Query(None, max_length=36),
    district: str | None = Query(None, max_length=120),
    county: str | None = Query(None, max_length=120),
    q: str | None = Query(None, max_length=120),
    scope: str = Query("mine", pattern=r"^(mine|all)$"),
) -> services.DeliveryFilters:
    return services.DeliveryFilters(
        crop=crop,
        status=status,
        site_id=site_id or None,
        date_from=date_from,
        date_to=date_to,
        officer_id=officer_id or None,
        district=district or None,
        county=county or None,
        q=(q or "").strip() or None,
        scope=scope,
    )


# --------------------------------------------------------------------------- mapping


def delivery_out(d: Delivery, ctx: Context, officer: CurrentOfficer) -> DeliveryOut:
    src = ctx.sources.get(d.field_id)
    site = ctx.sites.get(d.site_id)
    owner = src.registered_by if src else None
    return DeliveryOut(
        id=d.id,
        delivery_no=d.delivery_no,
        pickup_request_id=d.pickup_request_id,
        farmer_id=d.farmer_id,
        field_id=d.field_id,
        field_code=d.field_code,
        sawie_id=src.sawie_id if src else None,
        farmer_name=src.farmer_name if src else None,
        father_or_farm=(src.father_name if d.crop == "cotton" else src.farm_name) if src else None,
        location=ctx.location(d.field_id),
        district=src.district if src else None,
        county=src.county if src else None,
        officer_name=ctx.officers.get(owner or ""),
        crop=d.crop,
        season_year=d.season_year,
        status=d.status,
        site=SiteRefOut(
            id=site.id, code=site.code, name=site.name, type=site.type, country=site.country
        )
        if site
        else None,
        heap_id=d.heap_id,
        scheduled_date=d.scheduled_date,
        driver_name=d.driver_name,
        driver_phone=d.driver_phone,
        vehicle_no=d.vehicle_no,
        dispatched_at=d.dispatched_at,
        delivered_at=d.delivered_at,
        estimated_quantity_kg=d.estimated_quantity_kg,
        field_weight_kg=d.field_weight_kg,
        weighbridge_weight_kg=d.weighbridge_weight_kg,
        weighbridge_maunds=maunds(d.weighbridge_weight_kg) if d.crop == "cotton" else None,
        moisture_pct=d.moisture_pct,
        variance_kg=d.variance_kg,
        variance_pct=d.variance_pct,
        variance_level=d.variance_level,
        note=d.note,
        cancel_reason=d.cancel_reason,
        created_at=d.created_at,
        updated_at=d.updated_at,
        can_act=officer.sees_all or owner == officer.id,
    )


def detail_out(
    d: Delivery,
    officer: CurrentOfficer,
    queries: services.DeliveryQueries,
    service: services.DeliveryService,
) -> DeliveryDetailOut:
    ctx = queries.context()
    cfg = service.config(d.crop)
    return DeliveryDetailOut(
        **delivery_out(d, ctx, officer).model_dump(),
        history=[
            HistoryOut(
                from_status=h.from_status,
                to_status=h.to_status,
                officer_id=h.officer_id,
                officer_name=ctx.officers.get(h.officer_id or ""),
                at=h.at,
                note=h.note,
            )
            for h in queries.history(d.id)
        ],
        thresholds=ThresholdsOut(
            variance_warn_pct=cfg.variance_warn_pct,
            variance_flag_pct=cfg.variance_flag_pct,
            moisture_warn_pct=cfg.moisture_warn_pct,
        ),
    )


# --------------------------------------------------------------------------- routes


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


@router.get(
    "/inbox",
    response_model=list[InboxItemOut],
    summary="Radar pickup requests waiting to be scheduled",
)
def inbox(
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    scope: str = Query("mine", pattern=r"^(mine|all)$"),
    officer: CurrentOfficer = Depends(get_current_officer),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> list[InboxItemOut]:
    rows, _ = queries.inbox(officer, crop=crop, scope=scope)
    out = []
    for row in rows:
        req, src = row["request"], row["source"]
        out.append(
            InboxItemOut(
                request_id=req.id,
                request_no=req.request_no,
                field_id=req.field_id,
                field_code=req.field_code,
                farmer_id=req.farmer_id,
                sawie_id=src.sawie_id if src else None,
                farmer_name=src.farmer_name if src else None,
                location=row["location"],
                officer_name=row["officer_name"],
                crop=req.crop,
                season_year=req.season_year,
                estimated_quantity_kg=req.estimated_quantity_kg,
                quantity_is_estimate=req.quantity_is_estimate,
                preferred_date=req.preferred_date,
                note=req.note,
                requested_at=req.requested_at,
                can_schedule=row["can_schedule"],
            )
        )
    return out


@router.post(
    "/schedule",
    response_model=ScheduleResultOut,
    status_code=201,
    summary="Schedule one delivery per request",
)
def schedule(
    body: ScheduleIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> ScheduleResultOut:
    created, skipped = service.schedule(
        officer,
        request_ids=body.request_ids,
        site_id=body.site_id,
        scheduled_date=body.scheduled_date,
        driver_name=body.driver_name,
        driver_phone=body.driver_phone,
        vehicle_no=body.vehicle_no,
        note=body.note,
    )
    ctx = queries.context()
    return ScheduleResultOut(
        created=[delivery_out(d, ctx, officer) for d in created],
        skipped=[SkippedOut(**vars(s)) for s in skipped],
    )


@router.get("/stats", response_model=StatsOut, summary="KPI figures")
def stats(
    f: services.DeliveryFilters = Depends(delivery_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> StatsOut:
    return StatsOut(**queries.stats(f, officer))


@router.get("/export.csv", summary="Filtered deliveries as CSV (UTF-8 with BOM)")
def export_csv(
    f: services.DeliveryFilters = Depends(delivery_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> StreamingResponse:
    lines = list(queries.csv_lines(f, officer))
    name = f"deliveries_{datetime.now(UTC).date().isoformat()}.csv"
    return StreamingResponse(
        iter(lines),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("", response_model=DeliveryPageOut, summary="Deliveries (filters, pagination)")
def list_deliveries(
    params: PageParams = Depends(page_params),
    f: services.DeliveryFilters = Depends(delivery_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> DeliveryPageOut:
    rows, ctx = queries.list(f, officer)
    # Status chips count every status for the other filters.
    every, _ = queries.list(services.DeliveryFilters(**{**f.__dict__, "status": None}), officer)
    page = rows[params.offset : params.offset + params.page_size]
    return DeliveryPageOut(
        items=[delivery_out(d, ctx, officer) for d in page],
        total=len(rows),
        page=params.page,
        page_size=params.page_size,
        status_counts=queries.status_counts(every),
    )


def _readable(
    delivery_id: str, officer: CurrentOfficer, service: services.DeliveryService
) -> Delivery:
    """Any officer may read a delivery (as on the radar's All farmers view); acting is checked
    by the service."""
    del officer
    d = service.repo.get(delivery_id)
    if d is None:
        raise NotFoundError("That delivery does not exist.", code="delivery_not_found")
    return d


@router.get(
    "/{delivery_id}", response_model=DeliveryDetailOut, summary="One delivery with its history"
)
def get_delivery(
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> DeliveryDetailOut:
    return detail_out(_readable(delivery_id, officer, service), officer, queries, service)


@router.put(
    "/{delivery_id}",
    response_model=DeliveryDetailOut,
    summary="Edit transport details while scheduled",
)
def update_delivery(
    body: UpdateIn,
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> DeliveryDetailOut:
    d = service.update(delivery_id, officer, body.model_dump(exclude_unset=True))
    return detail_out(d, officer, queries, service)


@router.post(
    "/{delivery_id}/dispatch", response_model=TransitionOut, summary="Scheduled to in transit"
)
def dispatch(
    body: DispatchIn,
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> TransitionOut:
    d = service.dispatch(delivery_id, officer, field_weight_kg=body.field_weight_kg, note=body.note)
    return TransitionOut(delivery=detail_out(d, officer, queries, service), warnings=[])


@router.post(
    "/{delivery_id}/receive",
    response_model=TransitionOut,
    summary="In transit to delivered, at the gate",
)
def receive(
    body: ReceiveIn,
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> TransitionOut:
    d, warnings = service.receive(
        delivery_id,
        officer,
        weighbridge_weight_kg=body.weighbridge_weight_kg,
        moisture_pct=body.moisture_pct,
        note=body.note,
    )
    return TransitionOut(delivery=detail_out(d, officer, queries, service), warnings=warnings)


@router.post(
    "/{delivery_id}/cancel", response_model=DeliveryDetailOut, summary="Cancel with a reason"
)
def cancel(
    body: CancelIn,
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> DeliveryDetailOut:
    return detail_out(service.cancel(delivery_id, officer, body.reason), officer, queries, service)


@router.post(
    "/{delivery_id}/correct",
    response_model=TransitionOut,
    summary="Administrator correction of a delivered delivery",
)
def correct(
    body: CorrectIn,
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> TransitionOut:
    if not officer.sees_all:
        raise ForbiddenError(
            "Only an administrator can correct a delivered delivery.", code="delivery_admin_only"
        )
    d, warnings = service.correct(
        delivery_id,
        officer,
        reason=body.reason,
        weighbridge_weight_kg=body.weighbridge_weight_kg,
        moisture_pct=body.moisture_pct,
        field_weight_kg=body.field_weight_kg,
    )
    return TransitionOut(delivery=detail_out(d, officer, queries, service), warnings=warnings)


@router.get(
    "/{delivery_id}/slip.pdf", summary="One-page delivery slip with a QR of the delivery number"
)
def slip(
    delivery_id: str = DELIVERY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.DeliveryService = Depends(get_service),
    queries: services.DeliveryQueries = Depends(get_queries),
) -> Response:
    d = _readable(delivery_id, officer, service)
    out = delivery_out(d, queries.context(), officer)
    place = "Ginner" if d.crop == "cotton" else "Processor"
    rows = [
        ("Farmer", f"{out.farmer_name or '-'} (SAWIE {out.sawie_id or '-'})"),
        ("Field", f"{d.field_code}, {out.location}"),
        (place, f"{out.site.name}, {out.site.code}" if out.site else "-"),
        ("Scheduled date", d.scheduled_date.isoformat()),
        ("Driver", f"{d.driver_name}, {d.driver_phone}"),
        ("Vehicle", d.vehicle_no),
        ("Estimated quantity", weight_text(d.estimated_quantity_kg, d.crop)),
        ("Status", d.status.replace("_", " ").capitalize()),
    ]
    pdf = render_slip(rows, delivery_no=d.delivery_no, title=f"Delivery slip, {d.crop}")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="slip_{d.delivery_no}.pdf"'},
    )
