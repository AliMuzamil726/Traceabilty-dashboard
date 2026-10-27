"""Read side of Deliveries: inbox, filtered lists, detail, statistics and CSV.

Farmer and field details come from ``module_2.public_api.list_field_sources`` in one
query, so filtering by farmer, location or officer never calls per delivery.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core import csvsafe
from core.deps import CurrentOfficer
from module_2 import public_api as farms
from module_4 import public_api as radar
from module_5.models import CANCELLED, DELIVERED, IN_TRANSIT, LEVEL_FLAG, SCHEDULED, Delivery
from module_5.repository import DeliveryRepository, HistoryRepository
from module_5.services.weights import maunds
from shared.models.site import Site
from shared.repositories.officers import OfficerRepository
from shared.repositories.sites import SiteRepository


@dataclass(frozen=True)
class DeliveryFilters:
    crop: str | None = None
    status: str | None = None
    site_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    officer_id: str | None = None
    district: str | None = None
    county: str | None = None
    q: str | None = None
    scope: str = "mine"


@dataclass
class Context:
    """Lookups shared by every row of one response."""

    sources: dict[str, farms.FieldSourceDTO] = field(default_factory=dict)
    sites: dict[str, Site] = field(default_factory=dict)
    officers: dict[str, str] = field(default_factory=dict)

    def location(self, field_id: str) -> str:
        src = self.sources.get(field_id)
        if src is None:
            return "-"
        parts = (
            [src.village, src.tehsil, src.district]
            if src.crop == "cotton"
            else [src.county, src.region]
        )
        return ", ".join(p for p in parts if p) or "-"


def week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    start = (now - timedelta(days=now.weekday())).date()
    return datetime(start.year, start.month, start.day, tzinfo=UTC)


class DeliveryQueries:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DeliveryRepository(session)

    def context(self) -> Context:
        return Context(
            sources={s.id: s for s in farms.list_field_sources(self.session)},
            sites={s.id: s for s in SiteRepository(self.session).list_all()},
            officers={o.id: o.full_name for o in OfficerRepository(self.session).list_all()},
        )

    @staticmethod
    def owner(ctx: Context, field_id: str) -> str | None:
        src = ctx.sources.get(field_id)
        return src.registered_by if src else None

    def can_act(self, ctx: Context, d: Delivery, officer: CurrentOfficer) -> bool:
        return officer.sees_all or self.owner(ctx, d.field_id) == officer.id

    # ------------------------------------------------------------------ inbox

    def inbox(
        self, officer: CurrentOfficer, *, crop: str | None = None, scope: str = "mine"
    ) -> tuple[list[dict[str, Any]], Context]:
        ctx = self.context()
        rows = []
        for req in radar.list_open_pickup_requests(self.session, crop=crop):
            if req.status != "requested":
                continue
            src = ctx.sources.get(req.field_id)
            owner = src.registered_by if src else None
            mine = officer.sees_all or owner == officer.id
            if not mine and scope == "mine":
                continue
            rows.append(
                {
                    "request": req,
                    "source": src,
                    "location": ctx.location(req.field_id),
                    "officer_name": ctx.officers.get(owner or ""),
                    "can_schedule": mine,
                }
            )
        return rows, ctx

    # ------------------------------------------------------------------ list

    def _match(
        self, d: Delivery, f: DeliveryFilters, ctx: Context, officer: CurrentOfficer
    ) -> bool:
        src = ctx.sources.get(d.field_id)
        owner = src.registered_by if src else None
        if not officer.sees_all and f.scope == "mine" and owner != officer.id:
            return False
        if f.officer_id and owner != f.officer_id:
            return False
        if f.district and (src is None or src.district != f.district):
            return False
        if f.county and (src is None or src.county != f.county):
            return False
        if f.q:
            needle = f.q.strip().lower()
            hay = " ".join(
                str(x)
                for x in (
                    d.delivery_no,
                    d.vehicle_no,
                    d.field_code,
                    src.farmer_name if src else "",
                    src.sawie_id if src else "",
                )
            ).lower()
            if needle not in hay:
                return False
        return True

    def list(self, f: DeliveryFilters, officer: CurrentOfficer) -> tuple[list[Delivery], Context]:
        ctx = self.context()
        rows = self.repo.filtered(
            crop=f.crop,
            statuses=[f.status] if f.status else None,
            site_id=f.site_id,
            date_from=f.date_from,
            date_to=f.date_to,
        )
        return [d for d in rows if self._match(d, f, ctx, officer)], ctx

    def status_counts(self, rows: list[Delivery]) -> dict[str, int]:
        counts = dict.fromkeys((SCHEDULED, IN_TRANSIT, DELIVERED, CANCELLED), 0)
        for d in rows:
            counts[d.status] += 1
        return counts

    # ------------------------------------------------------------------ stats

    def stats(self, f: DeliveryFilters, officer: CurrentOfficer) -> dict[str, Any]:
        inbox, _ = self.inbox(officer, crop=f.crop, scope=f.scope)
        rows, _ = self.list(DeliveryFilters(**{**f.__dict__, "status": None}), officer)
        since = week_start()
        delivered_week = [
            d
            for d in rows
            if d.status == DELIVERED
            and d.delivered_at is not None
            and (d.delivered_at if d.delivered_at.tzinfo else d.delivered_at.replace(tzinfo=UTC))
            >= since
        ]
        kg = round(sum(d.weighbridge_weight_kg or 0 for d in delivered_week), 1)
        return {
            "requests_waiting": len(inbox),
            "scheduled": sum(1 for d in rows if d.status == SCHEDULED),
            "in_transit": sum(1 for d in rows if d.status == IN_TRANSIT),
            "delivered_this_week": len(delivered_week),
            "delivered_this_week_kg": kg,
            "delivered_this_week_maunds": maunds(kg),
            "weight_flags": sum(
                1 for d in rows if d.status == DELIVERED and d.variance_level == LEVEL_FLAG
            ),
            "week_start": since.date(),
        }

    def history(self, delivery_id: str) -> list[Any]:
        return HistoryRepository(self.session).for_delivery(delivery_id)

    # ------------------------------------------------------------------ csv

    def csv_lines(self, f: DeliveryFilters, officer: CurrentOfficer) -> Iterator[str]:
        rows, ctx = self.list(f, officer)
        head = [
            "Delivery",
            "Status",
            "SAWIE ID",
            "Farmer",
            "Field ID",
            "Location",
            "Crop",
            "Site",
            "Scheduled date",
            "Driver",
            "Driver phone",
            "Vehicle",
            "Dispatched at",
            "Delivered at",
            "Estimated (kg)",
            "Field weight (kg)",
            "Weighbridge (kg)",
            "Weighbridge (maunds)",
            "Moisture (%)",
            "Variance (kg)",
            "Variance (%)",
            "Variance level",
            "Heap",
            "Note",
        ]

        def line(values: list[Any]) -> str:
            buf = io.StringIO()
            csvsafe.writer(buf, lineterminator="\r\n").writerow(
                ["" if v is None else v for v in values]
            )
            return buf.getvalue()

        yield "﻿" + line(head)
        for d in rows:
            src = ctx.sources.get(d.field_id)
            site = ctx.sites.get(d.site_id)
            yield line(
                [
                    d.delivery_no,
                    d.status.replace("_", " "),
                    src.sawie_id if src else "",
                    src.farmer_name if src else "",
                    d.field_code,
                    ctx.location(d.field_id),
                    d.crop,
                    site.name if site else "",
                    d.scheduled_date.isoformat(),
                    d.driver_name,
                    d.driver_phone,
                    d.vehicle_no,
                    d.dispatched_at.isoformat() if d.dispatched_at else None,
                    d.delivered_at.isoformat() if d.delivered_at else None,
                    d.estimated_quantity_kg,
                    d.field_weight_kg,
                    d.weighbridge_weight_kg,
                    maunds(d.weighbridge_weight_kg) if d.crop == "cotton" else None,
                    d.moisture_pct,
                    d.variance_kg,
                    d.variance_pct,
                    d.variance_level,
                    d.heap_id,
                    d.note,
                ]
            )
