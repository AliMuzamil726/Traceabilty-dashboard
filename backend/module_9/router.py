"""HTTP routes for Module 9 (Gate Reception), mounted at ``/api/v1/gate``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from core.deps import CurrentOfficer, get_current_officer, get_db
from module_9 import meta, services
from module_9.models import PENDING, GateEntry
from module_9.schemas import (
    GateAccept,
    GateAcceptOut,
    GateEntryCreate,
    GateEntryOut,
    GateEntryPageOut,
    GateReject,
    GateSummaryOut,
    InboundLoadOut,
)
from shared.repositories.sites import SiteRepository
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

ENTRY_ID = Path(..., max_length=36, description="Gate entry primary key")
SITE_ID = Query(..., max_length=36, description="The ginner or processor site")
CROP = Query(None, pattern=r"^(cotton|hemp)$")


def get_service(session: Session = Depends(get_db)) -> services.GateService:
    return services.GateService(session)


def entry_out(entry: GateEntry, service: services.GateService) -> GateEntryOut:
    site = SiteRepository(service.session).get(entry.site_id)
    pending = entry.status == PENDING
    reference = service.reference(entry)
    return GateEntryOut(
        id=entry.id,
        delivery_id=entry.delivery_id,
        delivery_no=entry.delivery_no,
        site_id=entry.site_id,
        site_code=site.code if site else None,
        site_name=site.name if site else None,
        crop=entry.crop,
        status=entry.status,
        arrived_at=entry.arrived_at,
        vehicle_no=entry.vehicle_no,
        driver_name=entry.driver_name,
        gross_weight_kg=entry.gross_weight_kg,
        tare_weight_kg=entry.tare_weight_kg,
        net_weight_kg=entry.net_weight_kg,
        moisture_pct=entry.moisture_pct,
        accepted_at=entry.accepted_at,
        rejected_at=entry.rejected_at,
        rejection_reason=entry.rejection_reason,
        note=entry.note,
        can_accept=pending,
        can_reject=pending,
        field_weight_kg=reference.field_weight_kg if reference else None,
        estimated_quantity_kg=reference.estimated_quantity_kg if reference else None,
        variance_warn_pct=reference.variance_warn_pct if reference else None,
        variance_flag_pct=reference.variance_flag_pct if reference else None,
        moisture_warn_pct=reference.moisture_warn_pct if reference else None,
    )


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return ModuleMetaOut(
        number=meta.NUMBER,
        name=meta.NAME,
        route_prefix=meta.ROUTE_PREFIX,
        api_prefix=meta.API_PREFIX,
        status=meta.STATUS,
        build_order=meta.BUILD_ORDER,
        purpose=meta.PURPOSE,
    )


@router.get("/summary", response_model=GateSummaryOut, summary="Gate figures for one site")
def summary(
    site_id: str = SITE_ID,
    crop: str | None = CROP,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateSummaryOut:
    s = service.summary(site_id, crop)
    return GateSummaryOut(
        inbound=s.inbound,
        pending=s.pending,
        accepted_today=s.accepted_today,
        rejected_today=s.rejected_today,
        net_kg_today=s.net_kg_today,
    )


@router.get(
    "/inbound",
    response_model=list[InboundLoadOut],
    summary="In-transit loads due at the site, not at the gate yet",
)
def inbound(
    site_id: str = SITE_ID,
    crop: str | None = CROP,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> list[InboundLoadOut]:
    return [
        InboundLoadOut(
            delivery_id=row.delivery_id,
            delivery_no=row.delivery_no,
            field_code=row.field_code,
            farmer_id=row.farmer_id,
            farmer_name=row.farmer_name,
            sawie_id=row.sawie_id,
            crop=row.crop,
            site_id=row.site_id,
            vehicle_no=row.vehicle_no,
            driver_name=row.driver_name,
            dispatched_at=row.dispatched_at,
            estimated_quantity_kg=row.estimated_quantity_kg,
            field_weight_kg=row.field_weight_kg,
        )
        for row in service.inbound(site_id, crop)
    ]


@router.get("/entries", response_model=GateEntryPageOut, summary="Gate entries (filters)")
def list_entries(
    site_id: str = SITE_ID,
    status: str | None = Query(None, pattern=r"^(pending|accepted|rejected|decided)$"),
    crop: str | None = CROP,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateEntryPageOut:
    rows, total = service.entries(
        site_id, status=status, crop=crop, limit=limit, offset=offset
    )
    return GateEntryPageOut(
        items=[entry_out(entry, service) for entry in rows], total=total
    )


@router.post(
    "/entries",
    response_model=GateEntryOut,
    status_code=201,
    summary="Record that a delivery has arrived at the gate",
)
def create_entry(
    body: GateEntryCreate,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateEntryOut:
    return entry_out(service.create(officer, body.delivery_id, body.note), service)


@router.get("/entries/{entry_id}", response_model=GateEntryOut, summary="One gate entry")
def get_entry(
    entry_id: str = ENTRY_ID,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateEntryOut:
    return entry_out(service.get(entry_id), service)


@router.post(
    "/entries/{entry_id}/accept",
    response_model=GateAcceptOut,
    summary="Weighbridge reading and moisture: the load is received",
)
def accept_entry(
    body: GateAccept,
    entry_id: str = ENTRY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateAcceptOut:
    entry, warnings = service.accept(
        entry_id,
        officer,
        gross_weight_kg=body.gross_weight_kg,
        tare_weight_kg=body.tare_weight_kg,
        moisture_pct=body.moisture_pct,
        note=body.note,
    )
    return GateAcceptOut(entry=entry_out(entry, service), warnings=warnings)


@router.post(
    "/entries/{entry_id}/reject",
    response_model=GateEntryOut,
    summary="Refuse the load: the delivery is cancelled with the reason",
)
def reject_entry(
    body: GateReject,
    entry_id: str = ENTRY_ID,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.GateService = Depends(get_service),
) -> GateEntryOut:
    return entry_out(service.reject(entry_id, officer, body.rejection_reason), service)
