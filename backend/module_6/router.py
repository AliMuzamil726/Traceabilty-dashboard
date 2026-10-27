"""HTTP routes for Module 6 (Heap), mounted at ``/api/v1/heaps``."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core import csvsafe
from core.deps import CurrentOfficer, get_current_officer, get_db
from module_5 import public_api as deliveries
from module_6 import meta, services
from module_6.models import BALE_ACTIVE, OPEN, Heap
from module_6.repository import BaleRepository
from module_6.schemas import (
    AssignIn,
    AssignOut,
    BaleOut,
    BalesIn,
    CloseIn,
    ContributionOut,
    HeapConfigOut,
    HeapDetailOut,
    HeapListItemOut,
    MemberOut,
    OpenHeapIn,
    OpenHeapOut,
    PendingDeliveryOut,
    PermissionsOut,
    ReasonIn,
    SiteRefOut,
    SkippedOut,
    TotalsOut,
    UpdateHeapIn,
)
from module_6.services import permissions, views
from shared.repositories.officers import OfficerRepository
from shared.repositories.sites import SiteRepository
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

HEAP_KEY = Path(
    ..., max_length=36, description="Primary key or business ID, for example BWP-G1-H01"
)


def get_service(session: Session = Depends(get_db)) -> services.HeapService:
    return services.HeapService(session)


def detail(heap: Heap, officer: CurrentOfficer, service: services.HeapService) -> HeapDetailOut:
    session = service.session
    site = service.site(heap.site_id)
    members = service.members(heap)
    t = service.totals(heap)
    bales = service.bales.for_heap(heap.id)
    names = {o.id: o.full_name for o in OfficerRepository(session).list_all()}
    is_open = heap.status == OPEN
    any_bales = bool(bales)
    active = sum(1 for b in bales if b.status == BALE_ACTIVE)
    pending = []
    if is_open:
        rows = deliveries.list_delivered_unassigned(session, heap.site_id, heap.crop)
        for m in views.member_rows(session, rows):
            pending.append(
                PendingDeliveryOut(
                    id=m.delivery_id,
                    delivery_no=m.delivery_no,
                    field_code=m.field_code,
                    sawie_id=m.sawie_id,
                    farmer_name=m.farmer_name,
                    village_or_farm=m.village_or_farm,
                    delivered_at=m.delivered_at,
                    weighbridge_weight_kg=m.weighbridge_weight_kg,
                    moisture_pct=m.moisture_pct,
                )
            )
    return HeapDetailOut(
        id=heap.id,
        heap_id=heap.heap_id,
        crop=heap.crop,
        status=heap.status,
        site=SiteRefOut(
            id=site.id, code=site.code, name=site.name, type=site.type, address=site.address
        ),
        opened_at=heap.opened_at,
        opened_by_name=names.get(heap.opened_by or ""),
        closed_at=heap.closed_at,
        closed_by_name=names.get(heap.closed_by or ""),
        close_reason=heap.close_reason,
        outturn_ratio_pct=heap.outturn_ratio_pct,
        bale_unit_kg=heap.bale_unit_kg,
        shiv_pct=heap.shiv_pct,
        dust_pct=heap.dust_pct,
        note=heap.note,
        totals=TotalsOut(**vars(t)),
        deliveries=[MemberOut(**vars(m)) for m in views.member_rows(session, members)],
        contributions=[
            ContributionOut(**vars(c)) for c in views.contribution_rows(session, members)
        ],
        bales=[
            BaleOut(
                id=b.id,
                bale_serial=b.bale_serial,
                seq=b.seq,
                weight_kg=b.weight_kg,
                status=b.status,
                void_reason=b.void_reason,
                created_at=b.created_at,
                created_by=b.created_by,
                voided_at=b.voided_at,
            )
            for b in bales
        ],
        pending_deliveries=pending,
        permissions=PermissionsOut(
            can_edit_values=is_open and not any_bales,
            can_add_deliveries=is_open,
            can_remove_deliveries=is_open and active == 0,
            can_record_bales=is_open and t.can_add_bales > 0,
            can_void_bales=is_open and permissions.can_void_bale(officer),
            can_close=is_open and bool(members) and t.can_close,
            can_close_with_remainder=is_open
            and bool(members)
            and not t.can_close
            and permissions.can_close_with_remainder(officer),
        ),
    )


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


@router.get("/config", response_model=list[HeapConfigOut], summary="Defaults copied into new heaps")
def get_config(
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> list[HeapConfigOut]:
    out = []
    for crop in ("cotton", "hemp"):
        c = service.config(crop)
        out.append(
            HeapConfigOut(
                crop=crop,
                default_outturn_ratio_pct=c.default_outturn_ratio_pct,
                default_bale_unit_kg=c.default_bale_unit_kg,
                default_shiv_pct=c.default_shiv_pct,
                default_dust_pct=c.default_dust_pct,
            )
        )
    return out


@router.get("", response_model=list[HeapListItemOut], summary="Heaps (filters)")
def list_heaps(
    crop: str | None = Query(None, pattern=r"^(cotton|hemp)$"),
    site_id: str | None = Query(None, max_length=36),
    status: str | None = Query(None, pattern=r"^(open|closed)$"),
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> list[HeapListItemOut]:
    out = []
    for heap in service.heaps.filtered(crop=crop, site_id=site_id or None, status=status):
        members = service.members(heap)
        out.append(
            HeapListItemOut(
                id=heap.id,
                heap_id=heap.heap_id,
                site_id=heap.site_id,
                crop=heap.crop,
                status=heap.status,
                opened_at=heap.opened_at,
                closed_at=heap.closed_at,
                deliveries=len(members),
                input_kg=sum(
                    (views.heap_calc.D(d.weighbridge_weight_kg) for d in members),
                    views.heap_calc.D(0),
                ),
                bales_made=BaleRepository(service.session).active_count(heap.id),
            )
        )
    return out


@router.post(
    "", response_model=OpenHeapOut, status_code=201, summary="Open a heap (a batch for hemp)"
)
def open_heap(
    body: OpenHeapIn,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> OpenHeapOut:
    heap, warnings = service.open(officer, site_id=body.site_id, note=body.note)
    return OpenHeapOut(heap=detail(heap, officer, service), warnings=warnings)


@router.post("/bales/{serial}/void", response_model=BaleOut, summary="Void a bale (administrators)")
def void_bale(
    body: ReasonIn,
    serial: str = Path(..., max_length=48),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> BaleOut:
    b = service.void_bale(serial, officer, body.reason)
    return BaleOut(
        id=b.id,
        bale_serial=b.bale_serial,
        seq=b.seq,
        weight_kg=b.weight_kg,
        status=b.status,
        void_reason=b.void_reason,
        created_at=b.created_at,
        created_by=b.created_by,
        voided_at=b.voided_at,
    )


@router.get("/{key}", response_model=HeapDetailOut, summary="One heap with its calculations")
def get_heap(
    key: str = HEAP_KEY,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> HeapDetailOut:
    return detail(service.get(key), officer, service)


@router.put(
    "/{key}", response_model=HeapDetailOut, summary="Ratio, bale unit and note, while allowed"
)
def update_heap(
    body: UpdateHeapIn,
    key: str = HEAP_KEY,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> HeapDetailOut:
    return detail(
        service.update(key, officer, body.model_dump(exclude_unset=True)), officer, service
    )


@router.post("/{key}/deliveries", response_model=AssignOut, summary="Add delivered deliveries")
def add_deliveries(
    body: AssignIn,
    key: str = HEAP_KEY,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> AssignOut:
    heap, added, skipped = service.add_deliveries(key, officer, body.delivery_ids)
    return AssignOut(
        heap=detail(heap, officer, service),
        added=[d.id for d in added],
        skipped=[SkippedOut(**vars(s)) for s in skipped],
    )


@router.delete(
    "/{key}/deliveries/{delivery_id}",
    response_model=HeapDetailOut,
    summary="Remove a delivery (reason required)",
)
def remove_delivery(
    key: str = HEAP_KEY,
    delivery_id: str = Path(..., max_length=36),
    reason: str = Query("", max_length=1000),
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> HeapDetailOut:
    return detail(service.remove_delivery(key, delivery_id, officer, reason), officer, service)


@router.post(
    "/{key}/bales", response_model=HeapDetailOut, status_code=201, summary="Record N bales"
)
def create_bales(
    body: BalesIn,
    key: str = HEAP_KEY,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> HeapDetailOut:
    service.create_bales(key, officer, body.count)
    return detail(service.get(key), officer, service)


@router.post("/{key}/close", response_model=HeapDetailOut, summary="Close the heap")
def close_heap(
    body: CloseIn,
    key: str = HEAP_KEY,
    officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> HeapDetailOut:
    heap = service.close(key, officer, reason=body.reason, with_remainder=body.with_remainder)
    return detail(heap, officer, service)


@router.get(
    "/{key}/contributors", response_model=list[ContributionOut], summary="Farmer contribution"
)
def contributors(
    key: str = HEAP_KEY,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> list[ContributionOut]:
    heap = service.get(key)
    return [
        ContributionOut(**vars(c))
        for c in views.contribution_rows(service.session, service.members(heap))
    ]


@router.get(
    "/{key}/export.csv", summary="Deliveries, contributions and bales of one heap (UTF-8 with BOM)"
)
def export_csv(
    key: str = HEAP_KEY,
    _officer: CurrentOfficer = Depends(get_current_officer),
    service: services.HeapService = Depends(get_service),
) -> StreamingResponse:
    heap = service.get(key)
    session = service.session
    t = service.totals(heap)
    site = SiteRepository(session).get(heap.site_id)
    shares = {c.farmer_id: c for c in views.contribution_rows(session, service.members(heap))}
    buf = io.StringIO()
    w = csvsafe.writer(buf, lineterminator="\r\n")
    w.writerow(["Heap" if heap.crop == "cotton" else "Batch", heap.heap_id])
    w.writerow(["Site", site.name if site else ""])
    w.writerow(["Status", heap.status])
    w.writerow(["Input (kg)", t.input_kg])
    w.writerow(["Outturn (%)", t.outturn_ratio_pct])
    w.writerow(["Expected output (kg)", t.expected_output_kg])
    w.writerow(["Bales", f"{t.bales_made} of {t.max_bales}"])
    w.writerow([])
    w.writerow(
        [
            "Delivery",
            "SAWIE ID",
            "Farmer",
            "Field ID",
            "Village or farm",
            "Delivered at",
            "Field weight (kg)",
            "Weighbridge (kg)",
            "Moisture (%)",
            "Farmer share (%)",
        ]
    )
    for m in views.member_rows(session, service.members(heap)):
        share = shares.get(m.farmer_id)
        w.writerow(
            [
                m.delivery_no,
                m.sawie_id,
                m.farmer_name,
                m.field_code,
                m.village_or_farm,
                m.delivered_at.isoformat() if m.delivered_at else "",
                m.field_weight_kg,
                m.weighbridge_weight_kg,
                m.moisture_pct,
                share.pct if share else "",
            ]
        )
    w.writerow([])
    w.writerow(["Bale serial", "Weight (kg)", "Status", "Created at", "Void reason"])
    for b in service.bales.for_heap(heap.id):
        w.writerow(
            [b.bale_serial, b.weight_kg, b.status, b.created_at.isoformat(), b.void_reason or ""]
        )
    name = f"{heap.heap_id}_{datetime.now(UTC).date().isoformat()}.csv"
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
