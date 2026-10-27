"""Public API of Module 6 (Heap).

The ONLY file other modules may import from this module. Functions take a ``Session``
and return frozen DTOs. ``heap_id`` here is the business ID (for example BWP-G1-H01).
Lineage is built only from the public APIs of Modules 2, 3 and 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from module_5 import public_api as deliveries
from module_6.config_api import (
    get_config,
    update_config,
)
from module_6.models import BALE_ACTIVE, CLOSED, OPEN, Bale, Heap
from module_6.repository import BaleRepository, HeapRepository
from module_6.services import heap_calc, views
from module_6.services.heaps import HeapService


@dataclass(frozen=True)
class HeapDTO:
    id: str
    heap_id: str
    site_id: str
    crop: str
    kind: str  # heap (cotton) or batch (hemp)
    status: str  # open, closed
    opened_at: datetime
    closed_at: datetime | None
    outturn_ratio_pct: float
    bale_unit_kg: float
    shiv_pct: float | None
    dust_pct: float | None


@dataclass(frozen=True)
class HeapTotalsDTO:
    heap_id: str
    input_kg: Decimal
    expected_output_kg: Decimal
    max_bales: int
    bales_made: int
    bales_weight_kg: Decimal
    remaining_input_kg: Decimal
    remaining_output_kg: Decimal
    can_close: bool
    expected_shiv_kg: Decimal | None
    expected_dust_kg: Decimal | None


@dataclass(frozen=True)
class BaleDTO:
    id: str
    bale_serial: str
    heap_id: str
    seq: int
    weight_kg: float
    status: str  # active, voided
    created_at: datetime
    voided_at: datetime | None
    void_reason: str | None


@dataclass(frozen=True)
class LineageFieldDTO:
    field_id: str
    field_code: str
    fieldbook_id: str | None
    sowing_date: date | None
    delivery_nos: tuple[str, ...]
    kg: Decimal


@dataclass(frozen=True)
class LineageFarmerDTO:
    farmer_id: str
    sawie_id: int | None
    farmer_name: str | None
    kg: Decimal
    pct: Decimal
    fields: tuple[LineageFieldDTO, ...]


@dataclass(frozen=True)
class HeapLineageDTO:
    heap_id: str
    site_id: str
    crop: str
    input_kg: Decimal
    farmers: tuple[LineageFarmerDTO, ...]


@dataclass(frozen=True)
class SiteInventoryDTO:
    site_id: str
    open_heaps: int
    closed_heaps: int
    pending_deliveries: int
    pending_kg: Decimal
    input_kg: Decimal
    active_bales: int
    bales_weight_kg: Decimal


@dataclass(frozen=True)
class HeapActivityDTO:
    """One heap or batch with its utilisation and when anything last happened to it.

    Added for Module 1 (Dashboard, D-096). ``last_activity_at`` is the latest of the
    opening, the last delivery assigned to it and the last bale made, which is what the
    dashboard's idle-heap alert ages (D-099). Figures come from the same
    :mod:`module_6.services.heap_calc` formulas the Heap screen shows.
    """

    heap_pk: str
    heap_id: str
    site_id: str
    crop: str
    kind: str
    status: str
    opened_at: datetime
    closed_at: datetime | None
    last_activity_at: datetime
    deliveries: int
    input_kg: Decimal
    expected_output_kg: Decimal
    max_bales: int
    bales_made: int
    bales_weight_kg: Decimal
    remaining_input_kg: Decimal


@dataclass(frozen=True)
class ProgrammeHeapSummaryDTO:
    """Heap totals across a crop programme. Added for Module 1 (D-096)."""

    heaps: int
    open_heaps: int
    closed_heaps: int
    input_kg: Decimal
    expected_output_kg: Decimal
    bales_made: int
    bales_weight_kg: Decimal
    max_bales: int


@dataclass(frozen=True)
class HeapQuery:
    crop: str | None = None
    site_id: str | None = None
    status: str | None = None


def _dto(h: Heap) -> HeapDTO:
    return HeapDTO(
        id=h.id,
        heap_id=h.heap_id,
        site_id=h.site_id,
        crop=h.crop,
        kind="heap" if h.crop == "cotton" else "batch",
        status=h.status,
        opened_at=h.opened_at,
        closed_at=h.closed_at,
        outturn_ratio_pct=h.outturn_ratio_pct,
        bale_unit_kg=h.bale_unit_kg,
        shiv_pct=h.shiv_pct,
        dust_pct=h.dust_pct,
    )


def _bale(b: Bale, heap_id: str) -> BaleDTO:
    return BaleDTO(
        id=b.id,
        bale_serial=b.bale_serial,
        heap_id=heap_id,
        seq=b.seq,
        weight_kg=b.weight_kg,
        status=b.status,
        created_at=b.created_at,
        voided_at=b.voided_at,
        void_reason=b.void_reason,
    )


def get_heap(session: Session, heap_id: str) -> HeapDTO | None:
    heap = HeapRepository(session).resolve(heap_id)
    return _dto(heap) if heap is not None else None


def list_heaps(session: Session, query: HeapQuery | None = None) -> list[HeapDTO]:
    q = query or HeapQuery()
    return [
        _dto(h)
        for h in HeapRepository(session).filtered(crop=q.crop, site_id=q.site_id, status=q.status)
    ]


def list_open_heaps(session: Session, site_id: str) -> list[HeapDTO]:
    return [_dto(h) for h in HeapRepository(session).open_at(site_id)]


def get_heap_totals(session: Session, heap_id: str) -> HeapTotalsDTO | None:
    service = HeapService(session)
    heap = service.heaps.resolve(heap_id)
    if heap is None:
        return None
    t = service.totals(heap)
    return HeapTotalsDTO(
        heap_id=heap.heap_id,
        input_kg=t.input_kg,
        expected_output_kg=t.expected_output_kg,
        max_bales=t.max_bales,
        bales_made=t.bales_made,
        bales_weight_kg=t.bales_weight_kg,
        remaining_input_kg=t.remaining_input_kg,
        remaining_output_kg=t.remaining_output_kg,
        can_close=t.can_close,
        expected_shiv_kg=t.expected_shiv_kg,
        expected_dust_kg=t.expected_dust_kg,
    )


def list_bales(session: Session, heap_id: str, *, include_voided: bool = False) -> list[BaleDTO]:
    heap = HeapRepository(session).resolve(heap_id)
    if heap is None:
        return []
    rows = BaleRepository(session).for_heap(heap.id)
    return [_bale(b, heap.heap_id) for b in rows if include_voided or b.status == BALE_ACTIVE]


def get_bale(session: Session, serial: str) -> BaleDTO | None:
    bale = BaleRepository(session).by_serial(serial)
    if bale is None:
        return None
    heap = HeapRepository(session).get(bale.heap_pk)
    return _bale(bale, heap.heap_id if heap else "")


def get_heap_lineage(session: Session, heap_id: str) -> HeapLineageDTO | None:
    """Deliveries to farmers to fields, with each farmer's share of the heap input."""
    heap = HeapRepository(session).resolve(heap_id)
    if heap is None:
        return None
    farmers = views.lineage(session, heap)
    return HeapLineageDTO(
        heap_id=heap.heap_id,
        site_id=heap.site_id,
        crop=heap.crop,
        input_kg=heap_calc.kg(sum((f.kg for f in farmers), Decimal(0))),
        farmers=tuple(
            LineageFarmerDTO(
                farmer_id=f.farmer_id,
                sawie_id=f.sawie_id,
                farmer_name=f.farmer_name,
                kg=f.kg,
                pct=f.pct,
                fields=tuple(
                    LineageFieldDTO(
                        field_id=x.field_id,
                        field_code=x.field_code,
                        fieldbook_id=x.fieldbook_id,
                        sowing_date=x.sowing_date,
                        delivery_nos=tuple(x.delivery_nos),
                        kg=x.kg,
                    )
                    for x in f.fields
                ),
            )
            for f in farmers
        ),
    )


# --------------------------------------------------------------------- aggregates
# Added for Module 1 (Dashboard, D-096). Four queries for every heap at once, however
# many there are: the heaps, their bales, their deliveries and nothing per heap.


def list_heap_activity(
    session: Session, *, crop: str | None = None, site_id: str | None = None
) -> list[HeapActivityDTO]:
    """Every heap with its utilisation and last activity, newest opening first."""
    heaps_ = HeapRepository(session).filtered(crop=crop, site_id=site_id)
    bales = BaleRepository(session).active_totals_by_heap()
    delivered = deliveries.delivered_totals_by_heap(session, crop=crop)
    out: list[HeapActivityDTO] = []
    for heap in heaps_:
        bale_count, bale_kg, last_bale = bales.get(heap.id, (0, 0.0, None))
        count, kg_in, last_delivery = delivered.get(heap.heap_id, (0, 0.0, None))
        t = heap_calc.totals(
            crop=heap.crop,
            weighbridge_kg=[kg_in],
            outturn_ratio_pct=heap.outturn_ratio_pct,
            bale_unit_kg=heap.bale_unit_kg,
            # Every bale of a heap weighs its bale unit, so the unit repeated per bale
            # is the same list the Heap screen computes with.
            active_bale_weights=[heap.bale_unit_kg] * bale_count,
        )
        touched = [heap.opened_at, *(d for d in (last_bale, last_delivery) if d is not None)]
        out.append(
            HeapActivityDTO(
                heap_pk=heap.id,
                heap_id=heap.heap_id,
                site_id=heap.site_id,
                crop=heap.crop,
                kind="heap" if heap.crop == "cotton" else "batch",
                status=heap.status,
                opened_at=heap.opened_at,
                closed_at=heap.closed_at,
                last_activity_at=max(touched),
                deliveries=count,
                input_kg=heap_calc.kg(heap_calc.D(kg_in)),
                expected_output_kg=t.expected_output_kg,
                max_bales=t.max_bales,
                bales_made=bale_count,
                bales_weight_kg=heap_calc.kg(heap_calc.D(bale_kg)),
                remaining_input_kg=t.remaining_input_kg,
            )
        )
    return out


def list_heap_ids(
    session: Session, *, crop: str | None = None, site_id: str | None = None
) -> list[str]:
    """The business IDs of the heaps and batches in scope. One query, one column."""
    return HeapRepository(session).business_ids(crop=crop, site_id=site_id)


def get_programme_heap_summary(
    session: Session, *, crop: str | None = None, site_id: str | None = None
) -> ProgrammeHeapSummaryDTO:
    """Heap counts and quantities across a crop programme, from the same figures."""
    rows = list_heap_activity(session, crop=crop, site_id=site_id)
    return ProgrammeHeapSummaryDTO(
        heaps=len(rows),
        open_heaps=sum(1 for r in rows if r.status == OPEN),
        closed_heaps=sum(1 for r in rows if r.status == CLOSED),
        input_kg=heap_calc.kg(sum((r.input_kg for r in rows), Decimal(0))),
        expected_output_kg=heap_calc.kg(sum((r.expected_output_kg for r in rows), Decimal(0))),
        bales_made=sum(r.bales_made for r in rows),
        bales_weight_kg=heap_calc.kg(sum((r.bales_weight_kg for r in rows), Decimal(0))),
        max_bales=sum(r.max_bales for r in rows),
    )


def count_bales(
    session: Session,
    *,
    crop: str | None = None,
    site_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> int:
    """Active bales, optionally only those made inside a time range. One query."""
    return BaleRepository(session).count_active(
        crop=crop, site_id=site_id, since=since, until=until
    )


def get_site_inventory_summary(session: Session, site_id: str) -> SiteInventoryDTO:
    service = HeapService(session)
    heaps = service.heaps.filtered(site_id=site_id)
    pending = []
    for crop in {h.crop for h in heaps} or {"cotton", "hemp"}:
        pending += deliveries.list_delivered_unassigned(session, site_id, crop)
    input_kg = Decimal(0)
    active = 0
    weight = Decimal(0)
    for heap in heaps:
        t = service.totals(heap)
        input_kg += t.input_kg
        active += t.bales_made
        weight += t.bales_weight_kg
    return SiteInventoryDTO(
        site_id=site_id,
        open_heaps=sum(1 for h in heaps if h.status == OPEN),
        closed_heaps=sum(1 for h in heaps if h.status == CLOSED),
        pending_deliveries=len(pending),
        pending_kg=heap_calc.kg(
            sum((heap_calc.D(d.weighbridge_weight_kg) for d in pending), Decimal(0))
        ),
        input_kg=heap_calc.kg(input_kg),
        active_bales=active,
        bales_weight_kg=heap_calc.kg(weight),
    )


__all__ = [
    "BaleDTO",
    "HeapActivityDTO",
    "HeapDTO",
    "HeapLineageDTO",
    "HeapQuery",
    "HeapTotalsDTO",
    "LineageFarmerDTO",
    "LineageFieldDTO",
    "ProgrammeHeapSummaryDTO",
    "SiteInventoryDTO",
    "count_bales",
    "get_bale",
    "get_config",
    "get_heap",
    "get_heap_lineage",
    "get_heap_totals",
    "get_programme_heap_summary",
    "get_site_inventory_summary",
    "list_bales",
    "list_heap_activity",
    "list_heap_ids",
    "list_heaps",
    "list_open_heaps",
    "update_config",
]
