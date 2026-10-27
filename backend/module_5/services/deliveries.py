"""Deliveries: scheduling from Radar requests, and the strict status machine.

scheduled -> in_transit (dispatch) -> delivered (receive at gate)
scheduled or in_transit -> cancelled (with a reason)

Every transition writes the delivery, one history row, one audit entry and one event
in the same transaction. ``delivered`` is terminal: only an administrator correction,
with a reason, may change its weights afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import audit, events
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import AppError, ForbiddenError, NotFoundError, ValidationAppError
from core.events import bus
from core.guards import DELIVERY_CAN_CORRECT, DELIVERY_CAN_UNASSIGN, guards
from core.ids import next_id
from module_2 import public_api as farms
from module_4 import public_api as radar
from module_5.models import (
    CANCELLED,
    DELIVERED,
    IN_TRANSIT,
    LEVEL_FLAG,
    SCHEDULED,
    TRANSITIONS,
    Delivery,
    DeliveryConfig,
    DeliveryStatusHistory,
)
from module_5.repository import ConfigRepository, DeliveryRepository, HistoryRepository
from module_5.seed import DEFAULT_CONFIG
from module_5.services import validators
from module_5.services.weights import moisture_warning, variance
from shared.models.site import Site
from shared.repositories.sites import SiteRepository

COUNTER_KEY = "delivery"
NOTE_MAX = 1000
MAX_BULK = 200


class InvalidTransitionError(AppError):
    status_code = 409
    code = "invalid_transition"


class DeliveryLockedError(AppError):
    status_code = 409
    code = "delivery_locked"


@dataclass(frozen=True)
class Skipped:
    pickup_request_id: str
    field_code: str | None
    code: str
    reason: str


def today() -> date:
    return datetime.now(UTC).date()


def _note(raw: str | None, field: str = "note") -> str | None:
    value = (raw or "").strip() or None
    if value and len(value) > NOTE_MAX:
        raise ValidationAppError(
            f"The {field.replace('_', ' ')} is too long.", code="delivery_note_too_long"
        )
    return value


class DeliveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DeliveryRepository(session)
        self.history = HistoryRepository(session)
        self.sites = SiteRepository(session)

    # ------------------------------------------------------------------ helpers

    def config(self, crop: str) -> DeliveryConfig:
        row = ConfigRepository(self.session).for_crop(crop)
        if row is not None:
            return row
        warn, flag, moisture = DEFAULT_CONFIG[crop]
        return DeliveryConfig(
            crop=crop, variance_warn_pct=warn, variance_flag_pct=flag, moisture_warn_pct=moisture
        )

    def _site(self, site_id: str) -> Site:
        site = self.sites.get(site_id)
        if site is None or not site.active:
            raise ValidationAppError(
                "Choose an active site.",
                code="site_not_found",
                details={
                    "fields": [
                        {
                            "field": "site_id",
                            "location": "body",
                            "message": "Choose an active site.",
                            "type": "value",
                        }
                    ]
                },
            )
        return site

    def may_act(self, farmer_id: str, officer: CurrentOfficer) -> bool:
        if officer.sees_all:
            return True
        farmer = farms.get_farmer(self.session, farmer_id)
        return farmer is not None and farmer.registered_by == officer.id

    def get_for(self, delivery_id: str, officer: CurrentOfficer, *, lock: bool = False) -> Delivery:
        delivery = self.repo.get_for_update(delivery_id) if lock else self.repo.get(delivery_id)
        if delivery is None:
            raise NotFoundError("That delivery does not exist.", code="delivery_not_found")
        if not self.may_act(delivery.farmer_id, officer):
            raise ForbiddenError(
                "This delivery belongs to another officer's farmer.", code="delivery_forbidden"
            )
        return delivery

    def _move(self, d: Delivery, to: str, officer_id: str | None, note: str | None = None) -> str:
        """Apply one transition with its history row, or refuse it."""
        before = d.status
        if to not in TRANSITIONS[before]:
            raise InvalidTransitionError(
                f"A {before.replace('_', ' ')} delivery cannot become {to.replace('_', ' ')}.",
                details={"from": before, "to": to, "allowed": list(TRANSITIONS[before])},
            )
        d.status = to
        d.updated_by = officer_id
        self.history.add(
            DeliveryStatusHistory(
                delivery_id=d.id, from_status=before, to_status=to, officer_id=officer_id, note=note
            )
        )
        return before

    @staticmethod
    def _payload(d: Delivery) -> dict[str, Any]:
        return {
            "delivery_id": d.id,
            "delivery_no": d.delivery_no,
            "pickup_request_id": d.pickup_request_id,
            "field_id": d.field_id,
            "farmer_id": d.farmer_id,
            "site_id": d.site_id,
            "crop": d.crop,
            "season_year": d.season_year,
        }

    # ------------------------------------------------------------------ schedule

    def schedule(
        self,
        officer: CurrentOfficer,
        *,
        request_ids: list[str],
        site_id: str,
        scheduled_date: date,
        driver_name: str,
        driver_phone: str,
        vehicle_no: str,
        note: str | None = None,
    ) -> tuple[list[Delivery], list[Skipped]]:
        """One delivery per waiting request, with shared transport details."""
        ids = list(dict.fromkeys(request_ids))
        if not ids:
            raise ValidationAppError("Choose at least one request.", code="delivery_no_requests")
        if len(ids) > MAX_BULK:
            raise ValidationAppError(
                f"Schedule at most {MAX_BULK} at a time.", code="delivery_too_many"
            )
        site = self._site(site_id)
        if scheduled_date < today():
            raise ValidationAppError(
                "The scheduled date cannot be in the past.",
                code="delivery_date_past",
                details={
                    "fields": [
                        {
                            "field": "scheduled_date",
                            "location": "body",
                            "message": "Choose today or a later date.",
                            "type": "value",
                        }
                    ]
                },
            )
        name = validators.clean_name(driver_name)
        phone = validators.normalise_phone(driver_phone, site.country)
        vehicle = validators.normalise_vehicle(vehicle_no)
        note = _note(note)

        created: list[Delivery] = []
        skipped: list[Skipped] = []
        for request_id in ids:
            req = radar.get_pickup_request(self.session, request_id)
            problem: tuple[str, str] | None = None
            if req is None:
                problem = ("pickup_not_found", "That pickup request no longer exists.")
            elif req.status != "requested":
                problem = ("pickup_not_waiting", f"The request is already {req.status}.")
            elif not self.may_act(req.farmer_id, officer):
                problem = (
                    "delivery_forbidden",
                    "Only the officer who registered this farmer can schedule.",
                )
            elif req.crop != site.crop:
                problem = (
                    "site_crop_mismatch",
                    f"{site.name} takes {site.crop}, but this request is {req.crop}.",
                )
            if problem is not None:
                skipped.append(Skipped(request_id, req.field_code if req else None, *problem))
                continue
            assert req is not None
            try:
                with self.session.begin_nested():
                    d = Delivery(
                        delivery_no=next_id(self.session, COUNTER_KEY, "DL", width=4),
                        pickup_request_id=req.id,
                        farmer_id=req.farmer_id,
                        field_id=req.field_id,
                        field_code=req.field_code,
                        crop=req.crop,
                        season_year=req.season_year,
                        status=SCHEDULED,
                        site_id=site.id,
                        scheduled_date=scheduled_date,
                        driver_name=name,
                        driver_phone=phone,
                        vehicle_no=vehicle,
                        estimated_quantity_kg=req.estimated_quantity_kg,
                        note=note,
                        created_by=officer.id,
                        updated_by=officer.id,
                    )
                    self.repo.add(d)
                    self.session.flush()
                    self.history.add(
                        DeliveryStatusHistory(
                            delivery_id=d.id,
                            from_status=None,
                            to_status=SCHEDULED,
                            officer_id=officer.id,
                        )
                    )
                    radar.mark_pickup_scheduled(self.session, req.id, d.id)
            except (IntegrityError, AppError) as exc:
                reason = (
                    exc.message if isinstance(exc, AppError) else "The request changed meanwhile."
                )
                skipped.append(Skipped(request_id, req.field_code, "pickup_not_waiting", reason))
                continue
            audit.record(
                "delivery",
                d.id,
                "schedule",
                officer.id,
                {
                    "delivery_no": d.delivery_no,
                    "pickup_request_id": req.id,
                    "site_id": site.id,
                    "scheduled_date": scheduled_date.isoformat(),
                },
                session=self.session,
            )
            bus.publish(
                events.DELIVERY_SCHEDULED,
                {**self._payload(d), "scheduled_date": scheduled_date.isoformat()},
                officer_id=officer.id,
                session=self.session,
            )
            created.append(d)
        self.session.commit()
        return created, skipped

    # ------------------------------------------------------------------ edit

    def update(
        self, delivery_id: str, officer: CurrentOfficer, changes: dict[str, Any]
    ) -> Delivery:
        """Edit transport details while still scheduled."""
        d = self.get_for(delivery_id, officer, lock=True)
        if d.status != SCHEDULED:
            raise DeliveryLockedError(
                "Only a scheduled delivery can be edited.", details={"status": d.status}
            )
        diff: dict[str, Any] = {}
        site = self.sites.get(d.site_id)
        if changes.get("site_id") and changes["site_id"] != d.site_id:
            site = self._site(changes["site_id"])
            if site.crop != d.crop:
                raise ValidationAppError(
                    f"{site.name} takes {site.crop}, but this delivery is {d.crop}.",
                    code="site_crop_mismatch",
                )
            diff["site_id"] = {"from": d.site_id, "to": site.id}
            d.site_id = site.id
        assert site is not None
        if changes.get("scheduled_date") is not None:
            new_date: date = changes["scheduled_date"]
            if new_date < today():
                raise ValidationAppError(
                    "The scheduled date cannot be in the past.", code="delivery_date_past"
                )
            diff["scheduled_date"] = {"from": d.scheduled_date, "to": new_date}
            d.scheduled_date = new_date
        if changes.get("driver_name") is not None:
            d.driver_name = validators.clean_name(changes["driver_name"])
            diff["driver_name"] = d.driver_name
        if changes.get("driver_phone") is not None:
            d.driver_phone = validators.normalise_phone(changes["driver_phone"], site.country)
            diff["driver_phone"] = d.driver_phone
        if changes.get("vehicle_no") is not None:
            d.vehicle_no = validators.normalise_vehicle(changes["vehicle_no"])
            diff["vehicle_no"] = d.vehicle_no
        if "note" in changes:
            d.note = _note(changes["note"])
            diff["note"] = d.note
        d.updated_by = officer.id
        audit.record("delivery", d.id, "update", officer.id, diff, session=self.session)
        self.session.commit()
        return d

    # ------------------------------------------------------------------ transitions

    def dispatch(
        self,
        delivery_id: str,
        officer: CurrentOfficer,
        *,
        field_weight_kg: float | None = None,
        note: str | None = None,
    ) -> Delivery:
        d = self.get_for(delivery_id, officer, lock=True)
        if field_weight_kg is not None and field_weight_kg <= 0:
            raise ValidationAppError(
                "The field weight must be more than 0 kg.", code="delivery_weight_invalid"
            )
        note = _note(note)
        self._move(d, IN_TRANSIT, officer.id, note)
        d.dispatched_at = utcnow()
        d.field_weight_kg = field_weight_kg
        audit.record(
            "delivery",
            d.id,
            "dispatch",
            officer.id,
            {"status": {"from": SCHEDULED, "to": IN_TRANSIT}, "field_weight_kg": field_weight_kg},
            session=self.session,
        )
        bus.publish(
            events.DELIVERY_DISPATCHED,
            {
                **self._payload(d),
                "dispatched_at": d.dispatched_at.isoformat(),
                "field_weight_kg": field_weight_kg,
            },
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return d

    def _apply_weights(
        self, d: Delivery, *, weighbridge_kg: float, moisture_pct: float, note: str | None
    ) -> list[str]:
        if not weighbridge_kg or weighbridge_kg <= 0:
            raise ValidationAppError(
                "The weighbridge weight must be more than 0 kg.",
                code="delivery_weight_invalid",
                details={
                    "fields": [
                        {
                            "field": "weighbridge_weight_kg",
                            "location": "body",
                            "message": "Enter a weight above 0 kg.",
                            "type": "value",
                        }
                    ]
                },
            )
        if moisture_pct is None or not 0 <= moisture_pct <= 100:
            raise ValidationAppError(
                "Moisture must be between 0 and 100 percent.",
                code="delivery_moisture_invalid",
                details={
                    "fields": [
                        {
                            "field": "moisture_pct",
                            "location": "body",
                            "message": "Enter 0 to 100.",
                            "type": "value",
                        }
                    ]
                },
            )
        cfg = self.config(d.crop)
        v = variance(
            weighbridge_kg,
            field_weight_kg=d.field_weight_kg,
            estimated_kg=d.estimated_quantity_kg,
            warn_pct=cfg.variance_warn_pct,
            flag_pct=cfg.variance_flag_pct,
        )
        if v.level == LEVEL_FLAG and not note:
            raise ValidationAppError(
                f"The weight differs by {v.variance_pct:g}%, above the "
                f"{cfg.variance_flag_pct:g}% limit. Add a note.",
                code="delivery_flag_note_required",
                details={
                    "fields": [
                        {
                            "field": "note",
                            "location": "body",
                            "message": "Explain the weight difference.",
                            "type": "value",
                        }
                    ]
                },
            )
        d.weighbridge_weight_kg = weighbridge_kg
        d.moisture_pct = moisture_pct
        d.variance_kg, d.variance_pct, d.variance_level = v.variance_kg, v.variance_pct, v.level
        warnings = []
        moist = moisture_warning(moisture_pct, cfg.moisture_warn_pct)
        if moist:
            warnings.append(moist)
        if v.level == "warn":
            warnings.append(
                f"The weight differs by {v.variance_pct:g}% from the "
                f"{(v.reference or 'reference').replace('_', ' ')}."
            )
        return warnings

    def receive(
        self,
        delivery_id: str,
        officer: CurrentOfficer,
        *,
        weighbridge_weight_kg: float,
        moisture_pct: float,
        note: str | None = None,
    ) -> tuple[Delivery, list[str]]:
        d = self.get_for(delivery_id, officer, lock=True)
        if d.status != IN_TRANSIT:
            self._move(d, DELIVERED, officer.id)  # raises invalid_transition
        note = _note(note)
        warnings = self._apply_weights(
            d, weighbridge_kg=weighbridge_weight_kg, moisture_pct=moisture_pct, note=note
        )
        if note:
            d.note = f"{d.note}\n{note}" if d.note else note
        self._move(d, DELIVERED, officer.id, note)
        d.delivered_at = utcnow()
        audit.record(
            "delivery",
            d.id,
            "receive",
            officer.id,
            {
                "status": {"from": IN_TRANSIT, "to": DELIVERED},
                "weighbridge_weight_kg": d.weighbridge_weight_kg,
                "moisture_pct": d.moisture_pct,
                "variance_pct": d.variance_pct,
                "variance_level": d.variance_level,
            },
            session=self.session,
        )
        bus.publish(
            events.DELIVERY_DELIVERED,
            {
                **self._payload(d),
                "weighbridge_weight_kg": d.weighbridge_weight_kg,
                "moisture_pct": d.moisture_pct,
                "variance_level": d.variance_level,
                "delivered_at": d.delivered_at.isoformat(),
            },
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return d, warnings

    def cancel(self, delivery_id: str, officer: CurrentOfficer, reason: str | None) -> Delivery:
        reason = (reason or "").strip()
        if not reason:
            raise ValidationAppError(
                "Give a reason for cancelling.", code="delivery_reason_required"
            )
        if len(reason) > 500:
            raise ValidationAppError("The reason is too long.", code="delivery_reason_too_long")
        d = self.get_for(delivery_id, officer, lock=True)
        if d.status == DELIVERED:
            raise InvalidTransitionError(
                "A delivered delivery cannot be cancelled. "
                "An administrator can correct it instead.",
                details={"from": DELIVERED, "to": CANCELLED, "allowed": []},
            )
        self.cancel_delivery(d, reason, officer_id=officer.id, release_request=True)
        self.session.commit()
        return d

    def cancel_delivery(
        self, d: Delivery, reason: str, *, officer_id: str | None, release_request: bool
    ) -> None:
        """Cancel inside the caller's transaction. Releasing closes the Radar request too,
        so the field can be requested again from Radar."""
        before = self._move(d, CANCELLED, officer_id, reason)
        d.cancel_reason = reason
        audit.record(
            "delivery",
            d.id,
            "cancel",
            officer_id,
            {"status": {"from": before, "to": CANCELLED}, "reason": reason},
            session=self.session,
        )
        bus.publish(
            events.DELIVERY_CANCELLED,
            {**self._payload(d), "reason": reason, "previous_status": before},
            officer_id=officer_id,
            session=self.session,
        )
        if release_request:
            req = radar.get_pickup_request(self.session, d.pickup_request_id)
            if req is not None and req.status in ("requested", "scheduled"):
                radar.mark_pickup_cancelled(
                    self.session,
                    d.pickup_request_id,
                    f"Delivery {d.delivery_no} cancelled: {reason}",
                    officer_id=officer_id,
                )

    # ------------------------------------------------------------------ admin correction

    def correct(
        self,
        delivery_id: str,
        officer: CurrentOfficer,
        *,
        reason: str | None,
        weighbridge_weight_kg: float | None = None,
        moisture_pct: float | None = None,
        field_weight_kg: float | None = None,
    ) -> tuple[Delivery, list[str]]:
        if not officer.sees_all:
            raise ForbiddenError(
                "Only an administrator can correct a delivered delivery.",
                code="delivery_admin_only",
            )
        reason = (reason or "").strip()
        if not reason:
            raise ValidationAppError(
                "A correction needs a reason.", code="delivery_reason_required"
            )
        d = self.get_for(delivery_id, officer, lock=True)
        if d.status != DELIVERED:
            raise InvalidTransitionError(
                "Only a delivered delivery is corrected; edit or cancel the others.",
                code="delivery_not_delivered",
                details={"status": d.status},
            )
        guards.enforce(
            DELIVERY_CAN_CORRECT, delivery_id=d.id, heap_id=d.heap_id, session=self.session
        )
        before = {
            "weighbridge_weight_kg": d.weighbridge_weight_kg,
            "moisture_pct": d.moisture_pct,
            "field_weight_kg": d.field_weight_kg,
            "variance_pct": d.variance_pct,
            "variance_level": d.variance_level,
        }
        if field_weight_kg is not None:
            if field_weight_kg <= 0:
                raise ValidationAppError(
                    "The field weight must be more than 0 kg.", code="delivery_weight_invalid"
                )
            d.field_weight_kg = field_weight_kg
        warnings = self._apply_weights(
            d,
            weighbridge_kg=weighbridge_weight_kg
            if weighbridge_weight_kg is not None
            else d.weighbridge_weight_kg or 0,
            moisture_pct=moisture_pct if moisture_pct is not None else d.moisture_pct or 0,
            note=reason,
        )
        d.updated_by = officer.id
        after = {k: getattr(d, k) for k in before}
        self.history.add(
            DeliveryStatusHistory(
                delivery_id=d.id,
                from_status=DELIVERED,
                to_status=DELIVERED,
                officer_id=officer.id,
                note=f"Correction: {reason}",
            )
        )
        audit.record(
            "delivery",
            d.id,
            "correct",
            officer.id,
            {
                "reason": reason,
                **{k: {"from": before[k], "to": after[k]} for k in before if before[k] != after[k]},
            },
            session=self.session,
        )
        self.session.commit()
        return d, warnings

    # ------------------------------------------------------------------ heap links (Module 6)

    def assign_heap(
        self, delivery_id: str, heap_id: str, *, site_id: str, crop: str, officer_id: str | None
    ) -> Delivery:
        """Link a delivered, unassigned delivery to a heap of the same site and crop.

        Runs in the caller's transaction (no commit)."""
        d = self.repo.get_for_update(delivery_id)
        if d is None:
            raise NotFoundError("That delivery does not exist.", code="delivery_not_found")
        if d.status != DELIVERED:
            raise ValidationAppError(
                f"{d.delivery_no} is {d.status.replace('_', ' ')}, not delivered.",
                code="delivery_not_delivered",
            )
        if d.heap_id:
            raise ValidationAppError(
                f"{d.delivery_no} is already in {d.heap_id}.", code="delivery_already_assigned"
            )
        if d.site_id != site_id:
            raise ValidationAppError(
                f"{d.delivery_no} was delivered to another site.", code="delivery_wrong_site"
            )
        if d.crop != crop:
            raise ValidationAppError(
                f"{d.delivery_no} is {d.crop}, not {crop}.", code="delivery_wrong_crop"
            )
        d.heap_id = heap_id
        d.updated_by = officer_id
        audit.record(
            "delivery",
            d.id,
            "assign_heap",
            officer_id,
            {"heap_id": {"from": None, "to": heap_id}},
            session=self.session,
        )
        self.session.flush()
        return d

    def unassign_heap(self, delivery_id: str, *, officer_id: str | None, reason: str) -> Delivery:
        reason = (reason or "").strip()
        if not reason:
            raise ValidationAppError(
                "Give a reason for removing the delivery.", code="delivery_reason_required"
            )
        d = self.repo.get_for_update(delivery_id)
        if d is None:
            raise NotFoundError("That delivery does not exist.", code="delivery_not_found")
        if not d.heap_id:
            raise ValidationAppError(
                f"{d.delivery_no} is not in a heap.", code="delivery_not_assigned"
            )
        guards.enforce(
            DELIVERY_CAN_UNASSIGN, delivery_id=d.id, heap_id=d.heap_id, session=self.session
        )
        audit.record(
            "delivery",
            d.id,
            "unassign_heap",
            officer_id,
            {"heap_id": {"from": d.heap_id, "to": None}, "reason": reason},
            session=self.session,
        )
        d.heap_id = None
        d.updated_by = officer_id
        self.session.flush()
        return d
