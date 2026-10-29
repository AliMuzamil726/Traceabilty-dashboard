"""Public API of Module 9 (Gate Reception).

The ONLY file other modules may import from this module. Functions take a ``Session``
and return frozen DTOs; none of them commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from module_9.models import PENDING, GateEntry
from module_9.repository import GateRepository


@dataclass(frozen=True)
class GateEntryDTO:
    id: str
    delivery_id: str
    delivery_no: str
    site_id: str
    crop: str
    status: str  # pending, accepted, rejected
    arrived_at: datetime
    net_weight_kg: float | None
    moisture_pct: float | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None


def _dto(row: GateEntry) -> GateEntryDTO:
    return GateEntryDTO(
        id=row.id,
        delivery_id=row.delivery_id,
        delivery_no=row.delivery_no,
        site_id=row.site_id,
        crop=row.crop,
        status=row.status,
        arrived_at=row.arrived_at,
        net_weight_kg=row.net_weight_kg,
        moisture_pct=row.moisture_pct,
        accepted_at=row.accepted_at,
        rejected_at=row.rejected_at,
        rejection_reason=row.rejection_reason,
    )


def get_entry_for_delivery(session: Session, delivery_id: str) -> GateEntryDTO | None:
    """The gate entry of one delivery, whatever its status."""
    row = GateRepository(session).by_delivery(delivery_id)
    return _dto(row) if row is not None else None


def pending_count(session: Session, site_id: str) -> int:
    """Loads standing at the gate of one site, not yet accepted or rejected."""
    return GateRepository(session).count_for_site(site_id, status=PENDING)


__all__ = ["GateEntryDTO", "get_entry_for_delivery", "pending_count"]
