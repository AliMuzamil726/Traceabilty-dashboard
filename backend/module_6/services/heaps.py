"""Heaps (batches for hemp): open, gather deliveries, record bales, close.

Bale creation and closing lock the heap row inside the write transaction (SQLite takes
the database write lock at ``BEGIN IMMEDIATE``), and recount bales after the lock, so
two people pressing Record bales at once can never exceed ``max_bales``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from core import audit, events
from core.database import utcnow
from core.deps import CurrentOfficer
from core.errors import AppError, ConflictError, NotFoundError, ValidationAppError
from core.events import bus
from core.ids import next_value
from module_5 import public_api as deliveries
from module_6.models import BALE_ACTIVE, BALE_VOIDED, CLOSED, OPEN, Bale, Heap, HeapConfig
from module_6.repository import BaleRepository, HeapConfigRepository, HeapRepository
from module_6.seed import DEFAULT_CONFIG
from module_6.services import heap_calc, permissions
from shared.models.site import Site
from shared.repositories.sites import SiteRepository

MAX_BALES_PER_CALL = 500
REASON_MAX = 1000


class HeapLockedError(AppError):
    status_code = 409
    code = "heap_closed"


@dataclass(frozen=True)
class Skipped:
    delivery_id: str
    delivery_no: str | None
    code: str
    reason: str


def word(crop: str) -> str:
    return "heap" if crop == "cotton" else "batch"


def _reason(raw: str | None, *, required: bool, what: str) -> str | None:
    value = (raw or "").strip() or None
    if required and not value:
        raise ValidationAppError(f"Give a reason for {what}.", code="heap_reason_required")
    if value and len(value) > REASON_MAX:
        raise ValidationAppError("The reason is too long.", code="heap_reason_too_long")
    return value


class HeapService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.heaps = HeapRepository(session)
        self.bales = BaleRepository(session)

    # ------------------------------------------------------------------ reads

    def config(self, crop: str) -> HeapConfig:
        row = HeapConfigRepository(self.session).for_crop(crop)
        if row is not None:
            return row
        ratio, unit, shiv, dust = DEFAULT_CONFIG[crop]
        return HeapConfig(
            crop=crop,
            default_outturn_ratio_pct=ratio,
            default_bale_unit_kg=unit,
            default_shiv_pct=shiv,
            default_dust_pct=dust,
        )

    def get(self, key: str, *, lock: bool = False) -> Heap:
        heap = self.heaps.resolve(key)
        if heap is not None and lock:
            heap = self.heaps.get_for_update(heap.id)
        if heap is None:
            raise NotFoundError("That heap does not exist.", code="heap_not_found")
        return heap

    def site(self, site_id: str) -> Site:
        site = SiteRepository(self.session).get(site_id)
        if site is None:
            raise ValidationAppError("Choose a site.", code="site_not_found")
        return site

    def members(self, heap: Heap) -> list[deliveries.DeliveryDTO]:
        return deliveries.list_by_heap(self.session, heap.heap_id)

    def totals(self, heap: Heap) -> heap_calc.HeapTotals:
        active = [b.weight_kg for b in self.bales.for_heap(heap.id) if b.status == BALE_ACTIVE]
        return heap_calc.totals(
            crop=heap.crop,
            weighbridge_kg=[d.weighbridge_weight_kg for d in self.members(heap)],
            outturn_ratio_pct=heap.outturn_ratio_pct,
            bale_unit_kg=heap.bale_unit_kg,
            active_bale_weights=active,
            shiv_pct=heap.shiv_pct,
            dust_pct=heap.dust_pct,
        )

    @staticmethod
    def _open_or_fail(heap: Heap) -> None:
        if heap.status != OPEN:
            raise HeapLockedError(
                f"{heap.heap_id} is closed and can no longer change.",
                details={"heap_id": heap.heap_id},
            )

    # ------------------------------------------------------------------ open

    def open(
        self, officer: CurrentOfficer, *, site_id: str, note: str | None = None
    ) -> tuple[Heap, list[str]]:
        site = self.site(site_id)
        if not site.active:
            raise ValidationAppError("That site is not active.", code="site_inactive")
        warnings = []
        already = self.heaps.open_at(site.id)
        if already:
            warnings.append(
                f"{', '.join(h.heap_id for h in already)} is already open at {site.name}."
            )
        cfg = self.config(site.crop)
        number = next_value(self.session, f"heap:{site.code}")
        suffix = "H" if site.crop == "cotton" else "BT"
        heap = Heap(
            heap_id=f"{site.code}-{suffix}{number:02d}",
            site_id=site.id,
            crop=site.crop,
            status=OPEN,
            opened_at=utcnow(),
            opened_by=officer.id,
            outturn_ratio_pct=cfg.default_outturn_ratio_pct,
            bale_unit_kg=cfg.default_bale_unit_kg,
            shiv_pct=cfg.default_shiv_pct if site.crop == "hemp" else None,
            dust_pct=cfg.default_dust_pct if site.crop == "hemp" else None,
            note=_reason(note, required=False, what="the note"),
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.heaps.add(heap)
        self.session.flush()
        audit.record(
            "heap",
            heap.id,
            "open",
            officer.id,
            {
                "heap_id": heap.heap_id,
                "site_id": site.id,
                "outturn_ratio_pct": heap.outturn_ratio_pct,
                "bale_unit_kg": heap.bale_unit_kg,
            },
            session=self.session,
        )
        bus.publish(
            events.HEAP_OPENED,
            {
                "heap_pk": heap.id,
                "heap_id": heap.heap_id,
                "kind": word(heap.crop),
                "crop": heap.crop,
                "site_id": site.id,
            },
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return heap, warnings

    # ------------------------------------------------------------------ edit

    def update(self, key: str, officer: CurrentOfficer, changes: dict[str, Any]) -> Heap:
        heap = self.get(key, lock=True)
        self._open_or_fail(heap)
        diff: dict[str, Any] = {}
        frozen = self.bales.any_for_heap(heap.id)
        for attr, low, high in (
            ("outturn_ratio_pct", 0, 100),
            ("bale_unit_kg", 0, 10_000),
            ("shiv_pct", 0, 100),
            ("dust_pct", 0, 100),
        ):
            if changes.get(attr) is None:
                continue
            if frozen:
                raise ConflictError(
                    "The ratio and the bale unit are fixed once the first bale exists.",
                    code="heap_values_frozen",
                )
            if attr in ("shiv_pct", "dust_pct") and heap.crop != "hemp":
                continue
            value = float(changes[attr])
            if not low < value <= high:
                raise ValidationAppError(
                    f"{attr.replace('_', ' ')} must be above {low} and at most {high}.",
                    code="heap_value_invalid",
                    details={
                        "fields": [
                            {
                                "field": attr,
                                "location": "body",
                                "message": "Out of range.",
                                "type": "value",
                            }
                        ]
                    },
                )
            diff[attr] = {"from": getattr(heap, attr), "to": value}
            setattr(heap, attr, value)
        if "note" in changes:
            diff["note"] = {
                "from": heap.note,
                "to": _reason(changes["note"], required=False, what="the note"),
            }
            heap.note = diff["note"]["to"]
        heap.updated_by = officer.id
        if diff:
            audit.record("heap", heap.id, "update", officer.id, diff, session=self.session)
        self.session.commit()
        return heap

    # ------------------------------------------------------------------ deliveries

    def add_deliveries(
        self, key: str, officer: CurrentOfficer, delivery_ids: list[str]
    ) -> tuple[Heap, list[deliveries.DeliveryDTO], list[Skipped]]:
        heap = self.get(key, lock=True)
        self._open_or_fail(heap)
        ids = list(dict.fromkeys(delivery_ids))
        if not ids:
            raise ValidationAppError("Choose at least one delivery.", code="heap_no_deliveries")
        added: list[deliveries.DeliveryDTO] = []
        skipped: list[Skipped] = []
        for delivery_id in ids:
            try:
                with self.session.begin_nested():
                    dto = deliveries.assign_heap(
                        self.session,
                        delivery_id,
                        heap.heap_id,
                        officer.id,
                        site_id=heap.site_id,
                        crop=heap.crop,
                    )
            except AppError as exc:
                current = deliveries.get_delivery(self.session, delivery_id)
                skipped.append(
                    Skipped(
                        delivery_id,
                        current.delivery_no if current else None,
                        exc.code or "delivery_invalid",
                        exc.message,
                    )
                )
                continue
            added.append(dto)
        if added:
            audit.record(
                "heap",
                heap.id,
                "add_deliveries",
                officer.id,
                {
                    "delivery_ids": [d.id for d in added],
                    "delivery_nos": [d.delivery_no for d in added],
                },
                session=self.session,
            )
            heap.updated_by = officer.id
        self.session.commit()
        return heap, added, skipped

    def remove_delivery(
        self, key: str, delivery_id: str, officer: CurrentOfficer, reason: str | None
    ) -> Heap:
        heap = self.get(key, lock=True)
        self._open_or_fail(heap)
        reason = _reason(reason, required=True, what="removing the delivery")
        current = deliveries.get_delivery(self.session, delivery_id)
        if current is None or current.heap_id != heap.heap_id:
            raise NotFoundError(
                f"That delivery is not in {heap.heap_id}.", code="heap_delivery_not_found"
            )
        deliveries.unassign_heap(self.session, delivery_id, officer.id, reason or "")
        audit.record(
            "heap",
            heap.id,
            "remove_delivery",
            officer.id,
            {"delivery_id": delivery_id, "delivery_no": current.delivery_no, "reason": reason},
            session=self.session,
        )
        self.session.commit()
        return heap

    # ------------------------------------------------------------------ bales

    def create_bales(self, key: str, officer: CurrentOfficer, count: int) -> list[Bale]:
        if not 1 <= count <= MAX_BALES_PER_CALL:
            raise ValidationAppError(
                f"Record between 1 and {MAX_BALES_PER_CALL} bales at a time.",
                code="heap_bale_count_invalid",
            )
        heap = self.get(key, lock=True)
        self._open_or_fail(heap)
        t = self.totals(heap)  # recounted after the lock
        if count > t.can_add_bales:
            raise ConflictError(
                f"Only {t.can_add_bales} more {'bale' if t.can_add_bales == 1 else 'bales'} "
                "fit the expected output "
                f"({t.bales_made} of {t.max_bales} made).",
                code="heap_bale_limit",
                details={
                    "max_bales": t.max_bales,
                    "bales_made": t.bales_made,
                    "can_add": t.can_add_bales,
                },
            )
        unit = Decimal(str(heap.bale_unit_kg))
        if not heap_calc.mass_balance_ok(t, unit * count):
            raise ConflictError(
                "The bales would weigh more than the expected output.", code="heap_mass_balance"
            )
        start = self.bales.max_seq(heap.id)
        made: list[Bale] = []
        for i in range(1, count + 1):
            seq = start + i
            bale = Bale(
                bale_serial=f"{heap.heap_id}-{seq:03d}",
                heap_pk=heap.id,
                seq=seq,
                weight_kg=heap.bale_unit_kg,
                status=BALE_ACTIVE,
                created_by=officer.id,
                created_at=utcnow(),
            )
            self.bales.add(bale)
            made.append(bale)
        self.session.flush()
        audit.record(
            "heap",
            heap.id,
            "create_bales",
            officer.id,
            {"count": count, "first": made[0].bale_serial, "last": made[-1].bale_serial},
            session=self.session,
        )
        for bale in made:
            bus.publish(
                events.BALE_CREATED,
                {
                    "bale_id": bale.id,
                    "bale_serial": bale.bale_serial,
                    "heap_id": heap.heap_id,
                    "heap_pk": heap.id,
                    "weight_kg": bale.weight_kg,
                    "crop": heap.crop,
                },
                officer_id=officer.id,
                session=self.session,
            )
        heap.updated_by = officer.id
        self.session.commit()
        return made

    def void_bale(self, serial: str, officer: CurrentOfficer, reason: str | None) -> Bale:
        permissions.require_void_bale(officer)
        reason = _reason(reason, required=True, what="voiding the bale")
        bale = self.bales.by_serial(serial)
        if bale is None:
            raise NotFoundError("That bale does not exist.", code="bale_not_found")
        heap = self.get(bale.heap_pk, lock=True)
        self._open_or_fail(heap)
        if bale.status != BALE_ACTIVE:
            raise ConflictError("That bale is already voided.", code="bale_already_voided")
        bale.status, bale.void_reason = BALE_VOIDED, reason
        bale.voided_by, bale.voided_at = officer.id, utcnow()
        audit.record(
            "bale",
            bale.id,
            "void",
            officer.id,
            {"bale_serial": serial, "reason": reason},
            session=self.session,
        )
        bus.publish(
            events.BALE_VOIDED,
            {"bale_id": bale.id, "bale_serial": serial, "heap_id": heap.heap_id, "reason": reason},
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return bale

    # ------------------------------------------------------------------ close

    def close(
        self, key: str, officer: CurrentOfficer, *, reason: str | None, with_remainder: bool
    ) -> Heap:
        heap = self.get(key, lock=True)
        self._open_or_fail(heap)
        t = self.totals(heap)
        if not self.members(heap):
            raise ConflictError(
                f"A {word(heap.crop)} needs at least one delivery before it can close.",
                code="heap_empty",
            )
        reason = (reason or "").strip() or None
        if t.bales_made == 0 and not reason:
            raise ValidationAppError(
                "Closing with no bales needs a reason.", code="heap_reason_required"
            )
        remainder = not t.can_close
        if remainder:
            if not with_remainder:
                raise ConflictError(
                    f"{t.remaining_output_kg} kg of output is still expected. "
                    "Record more bales or close with remainder.",
                    code="heap_has_remainder",
                    details={
                        "remaining_output_kg": str(t.remaining_output_kg),
                        "remaining_input_kg": str(t.remaining_input_kg),
                    },
                )
            permissions.require_close_with_remainder(officer)
            _reason(reason, required=True, what="closing with a remainder")
        heap.status = CLOSED
        heap.closed_at, heap.closed_by, heap.close_reason = utcnow(), officer.id, reason
        heap.updated_by = officer.id
        audit.record(
            "heap",
            heap.id,
            "close",
            officer.id,
            {
                "heap_id": heap.heap_id,
                "reason": reason,
                "with_remainder": remainder,
                "input_kg": str(t.input_kg),
                "expected_output_kg": str(t.expected_output_kg),
                "bales_made": t.bales_made,
                "max_bales": t.max_bales,
                "remaining_input_kg": str(t.remaining_input_kg),
                "remaining_output_kg": str(t.remaining_output_kg),
            },
            session=self.session,
        )
        bus.publish(
            events.HEAP_CLOSED,
            {
                "heap_pk": heap.id,
                "heap_id": heap.heap_id,
                "crop": heap.crop,
                "site_id": heap.site_id,
                "total_input_kg": float(t.input_kg),
                "bale_count": t.bales_made,
                "with_remainder": remainder,
            },
            officer_id=officer.id,
            session=self.session,
        )
        self.session.commit()
        return heap
