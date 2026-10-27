"""Public API of Module 5 (Deliveries).

The ONLY file other modules may import from this module. Functions take a ``Session``
and return frozen DTOs. ``assign_heap`` and ``unassign_heap`` change state inside the
caller's transaction and do not commit; Module 6's service commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from module_5.config_api import (
    get_config,
    update_config,
)
from module_5.models import CANCELLED, DELIVERED, Delivery
from module_5.repository import DeliveryRepository
from module_5.services.deliveries import DeliveryService
from module_5.services.weights import maunds


@dataclass(frozen=True)
class DeliveryDTO:
    id: str
    delivery_no: str
    pickup_request_id: str
    farmer_id: str
    field_id: str
    field_code: str
    crop: str
    season_year: int
    status: str  # scheduled, in_transit, delivered, cancelled
    site_id: str
    heap_id: str | None
    scheduled_date: date
    vehicle_no: str
    dispatched_at: datetime | None
    delivered_at: datetime | None
    estimated_quantity_kg: float | None
    field_weight_kg: float | None
    weighbridge_weight_kg: float | None
    moisture_pct: float | None
    variance_pct: float | None
    variance_level: str | None


@dataclass(frozen=True)
class DeliveryStatsDTO:
    total: int
    by_status: dict[str, int]
    delivered_kg: float
    delivered_maunds: float | None
    weight_flags: int


@dataclass(frozen=True)
class FarmerDeliverySummaryDTO:
    farmer_id: str
    deliveries: int
    delivered: int
    delivered_kg: float
    fields: int
    heaps: list[str]


@dataclass(frozen=True)
class DeliveryQuery:
    crop: str | None = None
    status: str | None = None
    site_id: str | None = None
    heap_id: str | None = None
    farmer_id: str | None = None
    #: Several statuses at once. Added for Module 1 (D-096); ``status`` still works.
    statuses: tuple[str, ...] | None = None
    season_year: int | None = None
    #: Scheduled date range, inclusive.
    date_from: date | None = None
    date_to: date | None = None
    #: When the load was received at the gate. Narrows the delivered figures only.
    delivered_from: datetime | None = None
    delivered_to: datetime | None = None
    #: Restrict to these farmers; an empty tuple matches nothing (officer scoping).
    farmer_ids: tuple[str, ...] | None = None
    #: ``ok``, ``warn`` or ``flag``.
    variance_level: str | None = None
    #: At most this many rows. Use it with :func:`count_deliveries` for "n of many".
    limit: int | None = None


@dataclass(frozen=True)
class DeliveryTotalsDTO:
    """Delivery counts and delivered quantity for a filter. Added for Module 1 (D-096).

    ``delivered_maunds`` is only meaningful for cotton; it is the delivered kilograms
    divided by 40 and is given whatever the crop, so the caller shows it or not.
    """

    total: int
    by_status: dict[str, int]
    delivered: int
    delivered_kg: float
    delivered_maunds: float | None
    average_moisture_pct: float | None
    weight_flags: int


def _dto(d: Delivery) -> DeliveryDTO:
    return DeliveryDTO(
        id=d.id,
        delivery_no=d.delivery_no,
        pickup_request_id=d.pickup_request_id,
        farmer_id=d.farmer_id,
        field_id=d.field_id,
        field_code=d.field_code,
        crop=d.crop,
        season_year=d.season_year,
        status=d.status,
        site_id=d.site_id,
        heap_id=d.heap_id,
        scheduled_date=d.scheduled_date,
        vehicle_no=d.vehicle_no,
        dispatched_at=d.dispatched_at,
        delivered_at=d.delivered_at,
        estimated_quantity_kg=d.estimated_quantity_kg,
        field_weight_kg=d.field_weight_kg,
        weighbridge_weight_kg=d.weighbridge_weight_kg,
        moisture_pct=d.moisture_pct,
        variance_pct=d.variance_pct,
        variance_level=d.variance_level,
    )


def _farmer_filter(q: DeliveryQuery) -> list[str] | None:
    if q.farmer_ids is not None:
        return list(q.farmer_ids)
    return [q.farmer_id] if q.farmer_id else None


def list_deliveries(session: Session, query: DeliveryQuery | None = None) -> list[DeliveryDTO]:
    q = query or DeliveryQuery()
    statuses = list(q.statuses) if q.statuses else ([q.status] if q.status else None)
    rows = DeliveryRepository(session).filtered(
        crop=q.crop,
        statuses=statuses,
        site_id=q.site_id,
        heap_id=q.heap_id,
        season_year=q.season_year,
        farmer_ids=_farmer_filter(q),
        date_from=q.date_from,
        date_to=q.date_to,
        variance_level=q.variance_level,
        limit=q.limit,
    )
    return [_dto(d) for d in rows]


def get_delivery(session: Session, delivery_id: str) -> DeliveryDTO | None:
    d = DeliveryRepository(session).get(delivery_id)
    return _dto(d) if d is not None else None


def list_delivered_unassigned(session: Session, site_id: str, crop: str) -> list[DeliveryDTO]:
    """Delivered deliveries at a site that are not in any heap yet, oldest first."""
    rows = DeliveryRepository(session).filtered(
        crop=crop, statuses=[DELIVERED], site_id=site_id, unassigned_only=True
    )
    return [
        _dto(d) for d in sorted(rows, key=lambda d: (d.delivered_at or d.created_at, d.delivery_no))
    ]


def assign_heap(
    session: Session,
    delivery_id: str,
    heap_id: str,
    officer_id: str | None,
    *,
    site_id: str,
    crop: str,
) -> DeliveryDTO:
    """Only a delivered, unassigned delivery of the heap's site and crop. Raises 422 otherwise."""
    d = DeliveryService(session).assign_heap(
        delivery_id, heap_id, site_id=site_id, crop=crop, officer_id=officer_id
    )
    return _dto(d)


def unassign_heap(
    session: Session, delivery_id: str, officer_id: str | None, reason: str
) -> DeliveryDTO:
    """Take a delivery out of its heap. Checks guard ``delivery.can_unassign`` first."""
    return _dto(
        DeliveryService(session).unassign_heap(delivery_id, officer_id=officer_id, reason=reason)
    )


def list_by_heap(session: Session, heap_id: str) -> list[DeliveryDTO]:
    rows = DeliveryRepository(session).filtered(heap_id=heap_id)
    return [_dto(d) for d in sorted(rows, key=lambda d: d.delivery_no)]


def get_delivery_stats(session: Session, query: DeliveryQuery | None = None) -> DeliveryStatsDTO:
    rows = list_deliveries(session, query)
    by_status = dict.fromkeys(("scheduled", "in_transit", "delivered", "cancelled"), 0)
    for d in rows:
        by_status[d.status] += 1
    kg = round(sum(d.weighbridge_weight_kg or 0 for d in rows if d.status == DELIVERED), 1)
    return DeliveryStatsDTO(
        total=len(rows),
        by_status=by_status,
        delivered_kg=kg,
        delivered_maunds=maunds(kg),
        weight_flags=sum(1 for d in rows if d.status == DELIVERED and d.variance_level == "flag"),
    )


# --------------------------------------------------------------------- aggregates
# Added for Module 1 (Dashboard, D-096): counted in SQL, so the dashboard never loads
# the delivery table to add it up. Two queries for the totals, one for a series.


def count_deliveries(session: Session, query: DeliveryQuery | None = None) -> int:
    """How many deliveries match, counted in SQL rather than by loading them."""
    q = query or DeliveryQuery()
    statuses = list(q.statuses) if q.statuses else ([q.status] if q.status else None)
    return DeliveryRepository(session).count_matching(
        crop=q.crop,
        statuses=statuses,
        farmer_ids=_farmer_filter(q),
        season_year=q.season_year,
        date_from=q.date_from,
        date_to=q.date_to,
        variance_level=q.variance_level,
    )


def get_delivery_totals(session: Session, query: DeliveryQuery | None = None) -> DeliveryTotalsDTO:
    """Status counts plus delivered quantity, moisture and flags for the filter.

    ``date_from`` and ``date_to`` narrow by the scheduled date, which is what a
    delivery is planned for; ``delivered_from`` and ``delivered_to`` narrow the
    delivered figures by when the load was actually weighed in. The status counts
    always describe the whole filter, so a range never hides a scheduled delivery.
    """
    q = query or DeliveryQuery()
    repo = DeliveryRepository(session)
    counts = repo.count_by_status(
        crop=q.crop,
        farmer_ids=_farmer_filter(q),
        season_year=q.season_year,
        date_from=q.date_from,
        date_to=q.date_to,
    )
    delivered, kg, moisture, flags = repo.delivered_totals(
        crop=q.crop,
        farmer_ids=_farmer_filter(q),
        season_year=q.season_year,
        date_from=q.date_from,
        date_to=q.date_to,
        delivered_from=q.delivered_from,
        delivered_to=q.delivered_to,
    )
    by_status = {s: counts.get(s, 0) for s in ("scheduled", "in_transit", "delivered", "cancelled")}
    return DeliveryTotalsDTO(
        total=sum(by_status.values()),
        by_status=by_status,
        delivered=delivered,
        delivered_kg=kg,
        delivered_maunds=maunds(kg),
        average_moisture_pct=moisture,
        weight_flags=flags,
    )


def delivered_rows_in_range(
    session: Session,
    *,
    crop: str | None = None,
    farmer_ids: tuple[str, ...] | None = None,
    season_year: int | None = None,
    delivered_from: datetime | None = None,
    delivered_to: datetime | None = None,
) -> list[tuple[datetime, float, float | None]]:
    """``(delivered_at, weighbridge_kg, moisture_pct)`` for every delivery in the range.

    The caller groups these into weeks or months; see
    :meth:`module_5.repository.DeliveryRepository.delivered_rows` for why not in SQL.
    """
    return DeliveryRepository(session).delivered_rows(
        crop=crop,
        farmer_ids=None if farmer_ids is None else list(farmer_ids),
        season_year=season_year,
        delivered_from=delivered_from,
        delivered_to=delivered_to,
    )


def delivered_totals_by_heap(
    session: Session, *, crop: str | None = None
) -> dict[str, tuple[int, float, datetime | None]]:
    """``{heap_id: (deliveries, weighbridge_kg, last_change_at)}`` for every heap.

    One query for every heap at once, so Module 6 and the Dashboard can show heap
    utilisation without a call per heap.
    """
    return DeliveryRepository(session).totals_by_heap(crop=crop)


def get_farmer_delivery_summary(session: Session, farmer_id: str) -> FarmerDeliverySummaryDTO:
    rows = [d for d in DeliveryRepository(session).for_farmer(farmer_id) if d.status != CANCELLED]
    delivered = [d for d in rows if d.status == DELIVERED]
    return FarmerDeliverySummaryDTO(
        farmer_id=farmer_id,
        deliveries=len(rows),
        delivered=len(delivered),
        delivered_kg=round(sum(d.weighbridge_weight_kg or 0 for d in delivered), 1),
        fields=len({d.field_id for d in rows}),
        heaps=sorted({d.heap_id for d in delivered if d.heap_id}),
    )


__all__ = [
    "DeliveryDTO",
    "DeliveryQuery",
    "DeliveryStatsDTO",
    "DeliveryTotalsDTO",
    "FarmerDeliverySummaryDTO",
    "assign_heap",
    "count_deliveries",
    "delivered_rows_in_range",
    "delivered_totals_by_heap",
    "get_config",
    "get_delivery",
    "get_delivery_stats",
    "get_delivery_totals",
    "get_farmer_delivery_summary",
    "list_by_heap",
    "list_delivered_unassigned",
    "list_deliveries",
    "unassign_heap",
    "update_config",
]
