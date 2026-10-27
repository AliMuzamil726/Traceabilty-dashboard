"""Pickup requests: the only thing Radar owns.

Rules: only Ready or Harvested fields can be requested; at most one open request
(requested or scheduled) per field and season; officers act only for farmers they
registered (administrators for any); cancelling needs a reason and is allowed only
while a request is still ``requested``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import audit
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import AppError, ForbiddenError, NotFoundError, ValidationAppError
from core.events import bus
from core.ids import next_id
from module_2 import public_api as farms
from module_4 import events
from module_4.models import (
    STATUS_CANCELLED,
    STATUS_FULFILLED,
    STATUS_REQUESTED,
    STATUS_SCHEDULED,
    PickupRequest,
)
from module_4.repository import PickupRequestRepository
from module_4.services import cache
from module_4.services.dataset import RadarRow
from module_4.services.radar import RadarService
from module_4.services.readiness import BUCKET_LABELS, REQUESTABLE

COUNTER_KEY = "pickup_request"
MAX_FIELDS_PER_REQUEST = 500
NOTE_MAX = 1000
REASON_MAX = 500


class PickupStateError(AppError):
    status_code = 409
    code = "pickup_not_cancellable"


@dataclass(frozen=True)
class Skipped:
    field_id: str
    field_code: str | None
    code: str
    reason: str


def request_no(session: Session) -> str:
    """``PR-0001``, ``PR-0002`` ... from the shared id counter."""
    return next_id(session, COUNTER_KEY, "PR", width=4)


class PickupService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = PickupRequestRepository(session)

    # ------------------------------------------------------------------ create

    def _skip_reason(self, row: RadarRow | None, officer: CurrentOfficer) -> tuple[str, str] | None:
        if row is None:
            return ("field_not_found", "This field no longer exists or is not in this crop.")
        if not RadarService.can_act(row, officer):
            return ("pickup_forbidden", "Only the officer who registered this farmer can request.")
        if row.status not in REQUESTABLE:
            return (
                "pickup_not_ready",
                f"The field is {BUCKET_LABELS[row.status].lower()}, not ready or harvested.",
            )
        return None

    def request(
        self,
        officer: CurrentOfficer,
        *,
        crop: str,
        season_year: int,
        field_ids: list[str],
        preferred_date: date | None = None,
        note: str | None = None,
    ) -> tuple[list[PickupRequest], list[Skipped]]:
        """Create one request per eligible field; report every other field with a reason.

        Readiness is computed fresh (not from the cache), inside this transaction.
        """
        unique_ids = list(dict.fromkeys(field_ids))
        if not unique_ids:
            raise ValidationAppError("Choose at least one field.", code="pickup_no_fields")
        if len(unique_ids) > MAX_FIELDS_PER_REQUEST:
            raise ValidationAppError(
                f"Request at most {MAX_FIELDS_PER_REQUEST} fields at a time.",
                code="pickup_too_many",
            )
        note = (note or "").strip() or None
        if note and len(note) > NOTE_MAX:
            raise ValidationAppError("The note is too long.", code="pickup_note_too_long")

        rows = {
            r.field_id: r
            for r in RadarService(self.session).rows_for(crop, season_year, fresh=True)
            if r.field_id in set(unique_ids)
        }
        created: list[PickupRequest] = []
        skipped: list[Skipped] = []
        for field_id in unique_ids:
            row = rows.get(field_id)
            problem = self._skip_reason(row, officer)
            if problem is None and self.repo.open_for(field_id, season_year) is not None:
                problem = ("pickup_already_open", "A pickup is already requested for this field.")
            if problem is not None:
                skipped.append(Skipped(field_id, row.field_code if row else None, *problem))
                continue
            assert row is not None
            request = PickupRequest(
                request_no=request_no(self.session),
                field_id=row.field_id,
                field_code=row.field_code,
                farmer_id=row.farmer_id,
                crop=crop,
                season_year=season_year,
                status=STATUS_REQUESTED,
                estimated_quantity_kg=row.estimated_kg,
                quantity_is_estimate=row.estimate_is_benchmark,
                preferred_date=preferred_date,
                note=note,
                requested_by=officer.id,
                requested_at=utcnow(),
            )
            try:
                # The partial unique index is the last line of defence against a race.
                with self.session.begin_nested():
                    self.repo.add(request)
                    self.session.flush()
            except IntegrityError:
                skipped.append(
                    Skipped(
                        field_id,
                        row.field_code,
                        "pickup_already_open",
                        "A pickup is already requested for this field.",
                    )
                )
                continue
            audit.record(
                "pickup_request",
                request.id,
                "create",
                officer.id,
                {
                    "request_no": request.request_no,
                    "field_id": field_id,
                    "season_year": season_year,
                    "estimated_quantity_kg": request.estimated_quantity_kg,
                },
                session=self.session,
            )
            bus.publish(
                events.PICKUP_REQUESTED,
                self.payload(request),
                officer_id=officer.id,
                session=self.session,
            )
            created.append(request)
        self.session.commit()
        cache.invalidate()
        return created, skipped

    @staticmethod
    def payload(request: PickupRequest) -> dict[str, Any]:
        return {
            "pickup_request_id": request.id,
            "request_no": request.request_no,
            "field_id": request.field_id,
            "farmer_id": request.farmer_id,
            "crop": request.crop,
            "season_year": request.season_year,
            "estimated_quantity_kg": request.estimated_quantity_kg,
            "quantity_is_estimate": request.quantity_is_estimate,
            "preferred_date": request.preferred_date.isoformat()
            if request.preferred_date
            else None,
        }

    # ------------------------------------------------------------------ read

    def get_for(self, request_id: str, officer: CurrentOfficer) -> PickupRequest:
        request = self.repo.get(request_id)
        if request is None:
            raise NotFoundError("That pickup request does not exist.", code="pickup_not_found")
        if not officer.sees_all:
            farmer = farms.get_farmer(self.session, request.farmer_id)
            if farmer is None or farmer.registered_by != officer.id:
                raise ForbiddenError(
                    "This pickup request belongs to another officer's farmer.",
                    code="pickup_forbidden",
                )
        return request

    # ------------------------------------------------------------------ cancel

    def cancel(self, request_id: str, officer: CurrentOfficer, reason: str | None) -> PickupRequest:
        reason = (reason or "").strip()
        if not reason:
            raise ValidationAppError("Give a reason for cancelling.", code="pickup_reason_required")
        if len(reason) > REASON_MAX:
            raise ValidationAppError("The reason is too long.", code="pickup_reason_too_long")
        request = self.get_for(request_id, officer)
        self.cancel_request(request, reason, officer_id=officer.id, only_requested=True)
        self.session.commit()
        cache.invalidate()
        return request

    def cancel_request(
        self,
        request: PickupRequest,
        reason: str,
        *,
        officer_id: str | None,
        only_requested: bool,
    ) -> None:
        """Cancel inside the caller's transaction (no commit)."""
        allowed = (STATUS_REQUESTED,) if only_requested else (STATUS_REQUESTED, STATUS_SCHEDULED)
        if request.status not in allowed:
            raise PickupStateError(
                "Only a request that is still waiting can be cancelled."
                if only_requested
                else "This request is already closed.",
                details={"status": request.status},
            )
        before = request.status
        request.status = STATUS_CANCELLED
        request.cancelled_by = officer_id
        request.cancelled_at = utcnow()
        request.cancel_reason = reason
        audit.record(
            "pickup_request",
            request.id,
            "cancel",
            officer_id,
            {"status": {"from": before, "to": STATUS_CANCELLED}, "reason": reason},
            session=self.session,
        )
        bus.publish(
            events.PICKUP_CANCELLED,
            {**self.payload(request), "reason": reason, "previous_status": before},
            officer_id=officer_id,
            session=self.session,
        )

    # ------------------------------------------------------------------ Module 5 hooks

    def mark_scheduled(self, request_id: str, delivery_id: str) -> PickupRequest:
        request = self._require(request_id)
        if request.status not in (STATUS_REQUESTED, STATUS_SCHEDULED):
            raise PickupStateError(
                "Only an open request can be scheduled.",
                code="pickup_not_open",
                details={"status": request.status},
            )
        before = request.status
        request.status = STATUS_SCHEDULED
        request.delivery_id = delivery_id
        audit.record(
            "pickup_request",
            request.id,
            "schedule",
            None,
            {"status": {"from": before, "to": STATUS_SCHEDULED}, "delivery_id": delivery_id},
            session=self.session,
        )
        self.session.flush()
        cache.invalidate()
        return request

    def mark_fulfilled(self, request_id: str) -> PickupRequest:
        request = self._require(request_id)
        if request.status not in (STATUS_REQUESTED, STATUS_SCHEDULED):
            raise PickupStateError(
                "Only an open request can be fulfilled.",
                code="pickup_not_open",
                details={"status": request.status},
            )
        before = request.status
        request.status = STATUS_FULFILLED
        audit.record(
            "pickup_request",
            request.id,
            "fulfil",
            None,
            {"status": {"from": before, "to": STATUS_FULFILLED}},
            session=self.session,
        )
        self.session.flush()
        cache.invalidate()
        return request

    def _require(self, request_id: str) -> PickupRequest:
        request = self.repo.get(request_id)
        if request is None:
            raise NotFoundError("That pickup request does not exist.", code="pickup_not_found")
        return request
