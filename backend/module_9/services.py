"""Business logic for Module 9 (Gate Reception).

A gate entry is one load arriving at a ginner or processor gate. Accepting it records
the weighbridge reading and asks Module 5 to receive the delivery, so the delivery's
net weight, variance, heap totals and the dashboard all stay in one place. Rejecting it
asks Module 5 to cancel the delivery for the same reason. Both writes happen in this
module's transaction: Module 9 commits, Module 5 only flushes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core import audit, events
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import bus
from module_2 import public_api as farms
from module_5 import public_api as deliveries
from module_9.models import ACCEPTED, PENDING, REJECTED, GateEntry
from module_9.repository import GateRepository
from shared.models.site import Site
from shared.repositories.sites import SiteRepository

NOTE_MAX = 1000
REASON_MAX = 500


@dataclass(frozen=True)
class InboundLoad:
    delivery_id: str
    delivery_no: str
    field_code: str
    farmer_id: str
    farmer_name: str | None
    sawie_id: int | None
    crop: str
    site_id: str
    vehicle_no: str
    driver_name: str
    dispatched_at: datetime | None
    estimated_quantity_kg: float | None
    field_weight_kg: float | None


@dataclass(frozen=True)
class GateSummary:
    inbound: int
    pending: int
    accepted_today: int
    rejected_today: int
    net_kg_today: float


@dataclass(frozen=True)
class GateReference:
    """What the gate weighs against: the delivery's reference weight and the tolerances."""

    field_weight_kg: float | None
    estimated_quantity_kg: float | None
    variance_warn_pct: float
    variance_flag_pct: float
    moisture_warn_pct: float


def _text(raw: str | None, field: str) -> str | None:
    value = (raw or "").strip() or None
    if value and len(value) > NOTE_MAX:
        raise ValidationAppError(
            f"The {field.replace('_', ' ')} is too long.", code="gate_note_too_long"
        )
    return value


def start_of_today() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


class GateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = GateRepository(session)
        self.sites = SiteRepository(session)
        # One request reads the same config and each delivery's reference weight at most once.
        self._config: dict[str, Any] | None = None
        self._deliveries: dict[str, deliveries.DeliveryDTO | None] = {}

    def site(self, site_id: str) -> Site:
        site = self.sites.get(site_id)
        if site is None or not site.active:
            raise ValidationAppError(
                "Choose an active site.",
                code="site_not_found",
                details={
                    "fields": [
                        {
                            "field": "site_id",
                            "location": "query",
                            "message": "Choose an active site.",
                            "type": "value",
                        }
                    ]
                },
            )
        return site

    def get(self, entry_id: str) -> GateEntry:
        entry = self.repo.get(entry_id)
        if entry is None:
            raise NotFoundError("That gate entry does not exist.", code="gate_entry_not_found")
        return entry

    def reference(self, entry: GateEntry) -> GateReference | None:
        """What a pending load is weighed against; ``None`` once the entry is decided."""
        if entry.status != PENDING:
            return None
        if self._config is None:
            self._config = deliveries.get_config(self.session)
        crop = self._config["crops"].get(entry.crop) or self._config["defaults"][entry.crop]
        if entry.delivery_id not in self._deliveries:
            self._deliveries[entry.delivery_id] = deliveries.get_delivery(
                self.session, entry.delivery_id
            )
        delivery = self._deliveries[entry.delivery_id]
        return GateReference(
            field_weight_kg=delivery.field_weight_kg if delivery else None,
            estimated_quantity_kg=delivery.estimated_quantity_kg if delivery else None,
            variance_warn_pct=float(crop["variance_warn_pct"]),
            variance_flag_pct=float(crop["variance_flag_pct"]),
            moisture_warn_pct=float(crop["moisture_warn_pct"]),
        )

    # ------------------------------------------------------------------ arrival

    def create(
        self, officer: CurrentOfficer, delivery_id: str, note: str | None = None
    ) -> GateEntry:
        """Record that an in-transit delivery has reached the gate."""
        delivery = deliveries.get_delivery(self.session, delivery_id)
        if delivery is None:
            raise NotFoundError("That delivery does not exist.", code="delivery_not_found")
        if delivery.status != "in_transit":
            raise ValidationAppError(
                f"{delivery.delivery_no} is {delivery.status.replace('_', ' ')}, not in transit.",
                code="gate_delivery_not_in_transit",
                details={"status": delivery.status},
            )
        if self.repo.by_delivery(delivery_id) is not None:
            raise ConflictError(
                f"Gate entry already exists for {delivery.delivery_no}.",
                code="gate_entry_exists",
            )
        entry = GateEntry(
            delivery_id=delivery.id,
            delivery_no=delivery.delivery_no,
            site_id=delivery.site_id,
            crop=delivery.crop,
            status=PENDING,
            arrived_at=utcnow(),
            vehicle_no=delivery.vehicle_no,
            driver_name=delivery.driver_name,
            note=_text(note, "note"),
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.repo.add(entry)
        self.session.flush()
        audit.record(
            "gate_entry",
            entry.id,
            "arrive",
            officer.id,
            {
                "delivery_id": entry.delivery_id,
                "delivery_no": entry.delivery_no,
                "site_id": entry.site_id,
                "vehicle_no": entry.vehicle_no,
            },
            session=self.session,
        )
        bus.publish(
            events.GATE_ENTRY_CREATED,
            self._payload(entry),
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return entry

    # ------------------------------------------------------------------ decision

    def accept(
        self,
        entry_id: str,
        officer: CurrentOfficer,
        *,
        gross_weight_kg: float,
        tare_weight_kg: float,
        moisture_pct: float,
        note: str | None = None,
    ) -> tuple[GateEntry, list[str]]:
        entry = self._pending(entry_id)
        net = round(gross_weight_kg - tare_weight_kg, 2)
        if net <= 0:
            raise ValidationAppError(
                "The gross weight must be more than the tare weight.",
                code="gate_weight_invalid",
                details={
                    "fields": [
                        {
                            "field": "gross_weight_kg",
                            "location": "body",
                            "message": "Enter a gross weight above the tare weight.",
                            "type": "value",
                        }
                    ]
                },
            )
        entry.gross_weight_kg = gross_weight_kg
        entry.tare_weight_kg = tare_weight_kg
        entry.net_weight_kg = net
        entry.moisture_pct = moisture_pct
        note = _text(note, "note")
        if note is not None:
            entry.note = note
        entry.status = ACCEPTED
        entry.accepted_at = utcnow()
        entry.updated_by = officer.id

        # Module 5 moves the delivery to delivered with the net weight, inside this
        # transaction. It publishes delivery.delivered; the entry above is already
        # accepted, so this module's handler leaves it alone.
        _, warnings = deliveries.receive_at_gate(
            self.session,
            entry.delivery_id,
            officer.id,
            gross_weight_kg=gross_weight_kg,
            tare_weight_kg=tare_weight_kg,
            moisture_pct=moisture_pct,
            note=entry.note,
        )
        audit.record(
            "gate_entry",
            entry.id,
            "accept",
            officer.id,
            {
                "delivery_no": entry.delivery_no,
                "gross_weight_kg": entry.gross_weight_kg,
                "tare_weight_kg": entry.tare_weight_kg,
                "net_weight_kg": entry.net_weight_kg,
                "moisture_pct": entry.moisture_pct,
            },
            session=self.session,
        )
        bus.publish(
            events.GATE_ENTRY_ACCEPTED,
            {**self._payload(entry), "warnings": warnings},
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return entry, warnings

    def reject(self, entry_id: str, officer: CurrentOfficer, reason: str) -> GateEntry:
        entry = self._pending(entry_id)
        reason = (reason or "").strip()
        if len(reason) < 3:
            raise ValidationAppError(
                "Give a reason for rejecting the load.", code="gate_reason_required"
            )
        if len(reason) > REASON_MAX:
            raise ValidationAppError("The reason is too long.", code="gate_reason_too_long")
        entry.status = REJECTED
        entry.rejected_at = utcnow()
        entry.rejection_reason = reason
        entry.updated_by = officer.id

        # Module 5 cancels the in-transit delivery and releases the Radar request.
        deliveries.cancel_at_gate(self.session, entry.delivery_id, officer.id, reason)
        audit.record(
            "gate_entry",
            entry.id,
            "reject",
            officer.id,
            {"delivery_no": entry.delivery_no, "reason": reason},
            session=self.session,
        )
        bus.publish(
            events.GATE_ENTRY_REJECTED,
            {**self._payload(entry), "reason": reason},
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return entry

    # ------------------------------------------------------------------ reads

    def entries(
        self,
        site_id: str,
        *,
        status: str | None = None,
        crop: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GateEntry], int]:
        self.site(site_id)
        rows = self.repo.list_for_site(
            site_id, status=status, crop=crop, limit=limit, offset=offset
        )
        total = self.repo.count_for_site(site_id, status=status, crop=crop)
        return rows, total

    def inbound(self, site_id: str, crop: str | None = None) -> list[InboundLoad]:
        """In-transit deliveries due at the site with no gate entry yet, longest wait first."""
        self.site(site_id)
        arrived = self.repo.existing_delivery_ids(site_id, crop=crop)
        rows = deliveries.list_deliveries(
            self.session,
            deliveries.DeliveryQuery(site_id=site_id, crop=crop, statuses=("in_transit",)),
        )
        rows = [d for d in rows if d.id not in arrived]
        rows.sort(key=lambda d: (d.dispatched_at is None, d.dispatched_at, d.delivery_no))
        farmers = farms.get_farmers(self.session, list({d.farmer_id for d in rows}))
        out: list[InboundLoad] = []
        for d in rows:
            farmer = farmers.get(d.farmer_id)
            out.append(
                InboundLoad(
                    delivery_id=d.id,
                    delivery_no=d.delivery_no,
                    field_code=d.field_code,
                    farmer_id=d.farmer_id,
                    farmer_name=farmer.name if farmer else None,
                    sawie_id=farmer.sawie_id if farmer else None,
                    crop=d.crop,
                    site_id=d.site_id,
                    vehicle_no=d.vehicle_no,
                    driver_name=d.driver_name,
                    dispatched_at=d.dispatched_at,
                    estimated_quantity_kg=d.estimated_quantity_kg,
                    field_weight_kg=d.field_weight_kg,
                )
            )
        return out

    def summary(self, site_id: str, crop: str | None = None) -> GateSummary:
        self.site(site_id)
        since = start_of_today()
        accepted, kg = self.repo.accepted_since(site_id, since, crop=crop)
        return GateSummary(
            inbound=len(self.inbound(site_id, crop)),
            pending=self.repo.count_for_site(site_id, status=PENDING, crop=crop),
            accepted_today=accepted,
            rejected_today=self.repo.rejected_since(site_id, since, crop=crop),
            net_kg_today=kg,
        )

    # ------------------------------------------------------------------ helpers

    def _pending(self, entry_id: str) -> GateEntry:
        entry = self.repo.get_for_update(entry_id)
        if entry is None:
            raise NotFoundError("That gate entry does not exist.", code="gate_entry_not_found")
        if entry.status != PENDING:
            raise ConflictError(
                f"This load is already {entry.status}.",
                code="invalid_gate_status",
                details={"status": entry.status},
            )
        return entry

    @staticmethod
    def _payload(entry: GateEntry) -> dict[str, object]:
        return {
            "gate_entry_id": entry.id,
            "delivery_id": entry.delivery_id,
            "delivery_no": entry.delivery_no,
            "site_id": entry.site_id,
            "crop": entry.crop,
            "status": entry.status,
            "net_weight_kg": entry.net_weight_kg,
            "moisture_pct": entry.moisture_pct,
        }
