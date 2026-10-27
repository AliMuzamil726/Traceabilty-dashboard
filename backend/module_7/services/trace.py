"""Assemble a heap's chain from the public APIs of Modules 2, 3, 5 and 6.

``facts`` gathers everything once; ``public_payload`` copies across only what may be shown
to anyone (an allow-list, never a filter of a full record); ``internal_trace`` adds the
personal and location detail staff need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from module_2 import public_api as farms
from module_3 import public_api as fieldbooks
from module_5 import public_api as deliveries
from module_6 import public_api as heaps
from module_7.services import verification
from shared.repositories.officers import OfficerRepository
from shared.repositories.sites import SiteRepository

PROGRAMMES = {"cotton": ("Pakistan cotton", "Pakistan"), "hemp": ("UK hemp", "United Kingdom")}


@dataclass
class HeapFacts:
    heap: heaps.HeapDTO
    totals: heaps.HeapTotalsDTO
    site: Any
    deliveries: list[deliveries.DeliveryDTO]
    sources: dict[str, farms.FieldSourceDTO]
    books: dict[tuple[str, int], fieldbooks.FieldbookSummaryDTO | None]
    lineage: heaps.HeapLineageDTO
    bales: list[heaps.BaleDTO] = field(default_factory=list)


def _day(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _span(values: list[datetime | date | None]) -> tuple[date | None, date | None]:
    days = sorted(d for d in (_day(v) for v in values) if d is not None)
    return (days[0], days[-1]) if days else (None, None)


def facts(session: Session, heap_id: str, *, with_geometry: bool = False) -> HeapFacts | None:
    heap = heaps.get_heap(session, heap_id)
    if heap is None:
        return None
    totals = heaps.get_heap_totals(session, heap.heap_id)
    lineage = heaps.get_heap_lineage(session, heap.heap_id)
    assert totals is not None
    assert lineage is not None
    members = deliveries.list_by_heap(session, heap.heap_id)
    field_ids = {d.field_id for d in members}
    sources = {
        s.id: s
        for s in farms.list_field_sources(session, crop=heap.crop, include_geometry=with_geometry)
        if s.id in field_ids
    }
    pairs = sorted({(d.field_id, d.season_year) for d in members})
    books = {p: fieldbooks.get_fieldbook_summary(session, p[0], p[1]) for p in pairs}
    return HeapFacts(
        heap=heap,
        totals=totals,
        site=SiteRepository(session).get(heap.site_id),
        deliveries=members,
        sources=sources,
        books=books,
        lineage=lineage,
        bales=heaps.list_bales(session, heap.heap_id),
    )


def checks(f: HeapFacts) -> list[verification.Check]:
    return verification.checks(
        fieldbook_statuses=[b.status if b else None for b in f.books.values()],
        deliveries=[(d.status, d.weighbridge_weight_kg) for d in f.deliveries],
        heap_status=f.heap.status,
        bales_weight_kg=f.totals.bales_weight_kg,
        expected_output_kg=f.totals.expected_output_kg,
    )


def _timeline(f: HeapFacts, bale: heaps.BaleDTO | None) -> list[dict[str, Any]]:
    farmers = {s.farmer_id: s.farmer_registered_at for s in f.sources.values()}
    submitted = [b for b in f.books.values() if b and b.status == "submitted"]
    ready = [b.ready_for_pickup_at for b in f.books.values() if b and b.ready_for_pickup_at]
    bales = [bale] if bale else f.bales

    def item(key: str, label: str, count: int | None, dates: list[Any]) -> dict[str, Any]:
        start, end = _span(dates)
        return {
            "key": key,
            "label": label,
            "count": count,
            "date_from": start,
            "date_to": end,
            "done": bool(count) or bool(start),
        }

    return [
        item(
            "farmers",
            "Farmers registered",
            len({d.farmer_id for d in f.deliveries}),
            list(farmers.values()),
        ),
        item(
            "fields",
            "Fields mapped",
            len({d.field_id for d in f.deliveries}),
            [s.field_mapped_at for s in f.sources.values()],
        ),
        item(
            "fieldbooks",
            "Fieldbooks submitted",
            len(submitted),
            [b.submitted_at for b in submitted],
        ),
        item("harvest", "Harvest", len(ready), ready),
        item("delivery", "Delivery", len(f.deliveries), [d.delivered_at for d in f.deliveries]),
        item(
            "processing",
            "Heap processing" if f.heap.crop == "cotton" else "Batch processing",
            None,
            [f.heap.opened_at, f.heap.closed_at],
        ),
        item(
            "bale",
            "Bale produced" if bale else "Bales produced",
            len(bales),
            [b.created_at for b in bales],
        ),
    ]


def public_payload(f: HeapFacts, bale: heaps.BaleDTO | None) -> dict[str, Any]:
    """The only data anyone can see by scanning. Built from an allow-list of fields."""
    crop = f.heap.crop
    programme, country = PROGRAMMES[crop]
    regions = sorted(
        {(s.district if crop == "cotton" else s.county) or "" for s in f.sources.values()} - {""}
    )
    start, end = _span([d.delivered_at for d in f.deliveries])
    kind = "Heap" if crop == "cotton" else "Batch"
    product = ("Cotton lint" if crop == "cotton" else "Hemp fibre") + (
        " bale" if bale else f" {kind.lower()}"
    )
    return {
        "product": product,
        "crop": crop,
        "bale_serial": bale.bale_serial if bale else None,
        "weight_kg": bale.weight_kg if bale else None,
        "lot_kind": kind,
        "lot_id": f.heap.heap_id,
        "season_year": max((d.season_year for d in f.deliveries), default=None),
        "site": {
            "type": "Ginner" if crop == "cotton" else "Processor",
            "name": f.site.name if f.site else None,
            "region": f.site.region if f.site else None,
        },
        "processing": {"opened": _day(f.heap.opened_at), "closed": _day(f.heap.closed_at)},
        "programme": programme,
        "country": country,
        "farms": len({d.farmer_id for d in f.deliveries}),
        "fields": len({d.field_id for d in f.deliveries}),
        "region_level": "District" if crop == "cotton" else "County",
        "regions": regions,
        "harvest_window": {"from": start, "to": end},
        "timeline": _timeline(f, bale),
        "checks": [
            {"key": c.key, "label": c.label, "passed": c.passed, "detail": c.detail}
            for c in checks(f)
        ],
    }


def _decimal(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def internal_trace(
    session: Session, f: HeapFacts, bale: heaps.BaleDTO | None, *, officer_id: str
) -> dict[str, Any]:
    """The full chain for staff: bale, heap, deliveries, farmers, fields, fieldbooks."""
    officers = {o.id: o.full_name for o in OfficerRepository(session).list_all()}
    shares = {fa.farmer_id: fa for fa in f.lineage.farmers}
    farmers_out = []
    for farmer_id, share in shares.items():
        dto = farms.get_farmer(session, farmer_id, include_sensitive=True, officer_id=officer_id)
        any_src = next((s for s in f.sources.values() if s.farmer_id == farmer_id), None)
        farmers_out.append(
            {
                "farmer_id": farmer_id,
                "sawie_id": dto.sawie_id if dto else share.sawie_id,
                "name": dto.name if dto else share.farmer_name,
                "father_or_farm": (
                    any_src.father_name if f.heap.crop == "cotton" else any_src.farm_name
                )
                if any_src
                else None,
                "id_number": dto.id_number if dto else None,
                "phone": dto.phone if dto else None,
                "sensitive_visible": dto.sensitive_included if dto else False,
                "licence_no": dto.home_office_licence_no if dto else None,
                "location": ", ".join(
                    p
                    for p in (
                        [any_src.village, any_src.tehsil, any_src.district]
                        if f.heap.crop == "cotton"
                        else [any_src.county, any_src.region]
                    )
                    if p
                )
                if any_src
                else None,
                "registered_by": officers.get(dto.registered_by or "") if dto else None,
                "registered_at": any_src.farmer_registered_at if any_src else None,
                "kg": _decimal(share.kg),
                "pct": _decimal(share.pct),
            }
        )
    fields_out = []
    for d in f.deliveries:
        if any(x["field_id"] == d.field_id for x in fields_out):
            continue
        src = f.sources.get(d.field_id)
        book = f.books.get((d.field_id, d.season_year))
        log = fieldbooks.get_activity_timeline(session, d.field_id, d.season_year)
        fields_out.append(
            {
                "field_id": d.field_id,
                "field_code": d.field_code,
                "farmer_id": d.farmer_id,
                "area_acre": src.area_acre if src else None,
                "area_ha": src.area_ha if src else None,
                "geometry": src.geometry if src else farms.get_field_geometry(session, d.field_id),
                "centre": [src.pin_lat, src.pin_lng] if src else None,
                "season_year": d.season_year,
                "fieldbook": {
                    "id": book.id,
                    "status": book.status,
                    "submitted_at": book.submitted_at,
                    "steps_complete": book.steps_complete,
                    "steps_total": book.steps_total,
                }
                if book
                else None,
                "log": [
                    {
                        "at": e.at,
                        "step": (e.step_key or e.kind).replace("_", " ").capitalize(),
                        "kind": e.kind,
                        "summary": e.summary,
                        "officer": officers.get(e.officer_id or ""),
                    }
                    for e in log
                ],
            }
        )
    return {
        "bale": {
            "serial": bale.bale_serial,
            "weight_kg": bale.weight_kg,
            "status": bale.status,
            "created_at": bale.created_at,
        }
        if bale
        else None,
        "heap": {
            "heap_id": f.heap.heap_id,
            "crop": f.heap.crop,
            "status": f.heap.status,
            "kind": "Heap" if f.heap.crop == "cotton" else "Batch",
            "site_name": f.site.name if f.site else None,
            "site_code": f.site.code if f.site else None,
            "opened_at": f.heap.opened_at,
            "closed_at": f.heap.closed_at,
            "input_kg": _decimal(f.totals.input_kg),
            "expected_output_kg": _decimal(f.totals.expected_output_kg),
            "outturn_ratio_pct": f.heap.outturn_ratio_pct,
            "bales_made": f.totals.bales_made,
            "max_bales": f.totals.max_bales,
        },
        "deliveries": [
            {
                "id": d.id,
                "delivery_no": d.delivery_no,
                "farmer_id": d.farmer_id,
                "field_id": d.field_id,
                "field_code": d.field_code,
                "status": d.status,
                "delivered_at": d.delivered_at,
                "field_weight_kg": d.field_weight_kg,
                "weighbridge_weight_kg": d.weighbridge_weight_kg,
                "moisture_pct": d.moisture_pct,
                "vehicle_no": d.vehicle_no,
            }
            for d in f.deliveries
        ],
        "farmers": farmers_out,
        "fields": fields_out,
        "checks": [
            {"key": c.key, "label": c.label, "passed": c.passed, "detail": c.detail}
            for c in checks(f)
        ],
    }
