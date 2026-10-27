"""What the heap screens and the public API read: detail rows, contributions, lineage.

Farmer and field details come from Module 2's ``list_field_sources`` (one query), and
fieldbook facts from Module 3's ``get_crop_status_bulk``, never from their tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from module_2 import public_api as farms
from module_3 import public_api as fieldbooks
from module_5 import public_api as deliveries
from module_6.models import Heap
from module_6.services import heap_calc


@dataclass(frozen=True)
class MemberRow:
    delivery_id: str
    delivery_no: str
    farmer_id: str
    field_id: str
    field_code: str
    sawie_id: int | None
    farmer_name: str | None
    village_or_farm: str | None
    delivered_at: datetime | None
    field_weight_kg: float | None
    weighbridge_weight_kg: float | None
    moisture_pct: float | None


@dataclass(frozen=True)
class ContributionRow:
    farmer_id: str
    sawie_id: int | None
    farmer_name: str | None
    kg: Decimal
    pct: Decimal
    deliveries: int
    fields: int


@dataclass(frozen=True)
class LineageField:
    field_id: str
    field_code: str
    fieldbook_id: str | None
    sowing_date: date | None
    delivery_nos: list[str]
    kg: Decimal


@dataclass(frozen=True)
class LineageFarmer:
    farmer_id: str
    sawie_id: int | None
    farmer_name: str | None
    kg: Decimal
    pct: Decimal
    fields: list[LineageField]


def sources(session: Session) -> dict[str, farms.FieldSourceDTO]:
    return {s.id: s for s in farms.list_field_sources(session)}


def member_rows(session: Session, members: list[deliveries.DeliveryDTO]) -> list[MemberRow]:
    src = sources(session)
    out = []
    for d in members:
        s = src.get(d.field_id)
        place = (s.village if d.crop == "cotton" else s.farm_name) if s else None
        out.append(
            MemberRow(
                delivery_id=d.id,
                delivery_no=d.delivery_no,
                farmer_id=d.farmer_id,
                field_id=d.field_id,
                field_code=d.field_code,
                sawie_id=s.sawie_id if s else None,
                farmer_name=s.farmer_name if s else None,
                village_or_farm=place,
                delivered_at=d.delivered_at,
                field_weight_kg=d.field_weight_kg,
                weighbridge_weight_kg=d.weighbridge_weight_kg,
                moisture_pct=d.moisture_pct,
            )
        )
    return out


def contribution_rows(
    session: Session, members: list[deliveries.DeliveryDTO]
) -> list[ContributionRow]:
    src = sources(session)
    names = {s.farmer_id: (s.sawie_id, s.farmer_name) for s in src.values()}
    missing = [d.farmer_id for d in members if d.farmer_id not in names]
    if missing:
        for f in farms.get_farmers(session, list(set(missing))).values():
            names[f.id] = (f.sawie_id, f.name)
    shares = heap_calc.contributions(
        (d.farmer_id, d.field_id, d.weighbridge_weight_kg) for d in members
    )
    return [
        ContributionRow(
            farmer_id=c.farmer_id,
            sawie_id=names.get(c.farmer_id, (None, None))[0],
            farmer_name=names.get(c.farmer_id, (None, None))[1],
            kg=c.kg,
            pct=c.pct,
            deliveries=c.deliveries,
            fields=c.fields,
        )
        for c in shares
    ]


def lineage(session: Session, heap: Heap) -> list[LineageFarmer]:
    """Bale -> heap -> deliveries -> farmers -> fields, with each farmer's share."""
    members = deliveries.list_by_heap(session, heap.heap_id)
    shares = {c.farmer_id: c for c in contribution_rows(session, members)}
    facts = fieldbooks.get_crop_status_bulk(session, [(d.field_id, d.season_year) for d in members])
    per_field: dict[tuple[str, str], list[deliveries.DeliveryDTO]] = {}
    for d in members:
        per_field.setdefault((d.farmer_id, d.field_id), []).append(d)
    out = []
    for farmer_id, share in shares.items():
        fields = []
        for (f_id, field_id), rows in sorted(per_field.items(), key=lambda kv: kv[1][0].field_code):
            if f_id != farmer_id:
                continue
            fact = facts.get((field_id, rows[0].season_year))
            fields.append(
                LineageField(
                    field_id=field_id,
                    field_code=rows[0].field_code,
                    fieldbook_id=fact.fieldbook_id if fact else None,
                    sowing_date=fact.sowing_date if fact else None,
                    delivery_nos=[r.delivery_no for r in rows],
                    kg=heap_calc.kg(
                        sum((heap_calc.D(r.weighbridge_weight_kg) for r in rows), Decimal(0))
                    ),
                )
            )
        out.append(
            LineageFarmer(
                farmer_id=farmer_id,
                sawie_id=share.sawie_id,
                farmer_name=share.farmer_name,
                kg=share.kg,
                pct=share.pct,
                fields=fields,
            )
        )
    return out
