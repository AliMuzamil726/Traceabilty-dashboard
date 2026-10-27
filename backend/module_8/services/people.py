"""Officers and field offices.

Two rules matter more than the rest and are enforced here rather than in the router:

* **No lockout.** The last active administrator cannot be deactivated or demoted, and
  nobody can deactivate themselves. Without a login there is no password reset, so an
  empty administrator list would mean editing the database by hand.
* **Nothing referenced is deleted.** An officer who registered a farmer, filled in a
  fieldbook or weighed a load is deactivated, never removed: the audit trail and every
  record that names them must keep resolving.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import audit, usage
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import OFFICER_CREATED, OFFICER_DEACTIVATED, OFFICER_UPDATED, bus
from core.passwords import DEFAULT_PASSWORD, hash_password
from shared.models.field_office import FieldOffice
from shared.models.officer import ROLE_ADMIN, ROLE_OFFICER, ROLES, Officer
from shared.repositories.officers import OfficerRepository
from shared.repositories.offices import FieldOfficeRepository

MAX_NAME = 120
CODE_MAX = 32


@dataclass(frozen=True)
class ImportReport:
    """What a CSV import did, or would do when ``dry_run`` is on."""

    created: int
    updated: int
    skipped: int
    errors: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "ok": not self.errors,
        }


def _clean(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        raise ValidationAppError(f"That value is longer than {limit} characters.")
    return text


class OfficerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = OfficerRepository(session)
        self.offices = FieldOfficeRepository(session)

    # -------------------------------------------------------------------- reading

    def list_officers(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        active: bool | None = None,
        office_id: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(Officer).order_by(Officer.full_name)
        if office_id:
            stmt = stmt.where(Officer.field_office_id == office_id)
        if role:
            stmt = stmt.where(Officer.role == role)
        if active is not None:
            stmt = stmt.where(Officer.active.is_(active))
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                func.lower(Officer.full_name).like(like) | func.lower(Officer.code).like(like)
            )
        rows = list(self.session.execute(stmt).scalars())
        offices = {o.id: o for o in self.session.execute(select(FieldOffice)).scalars()}
        return [self._as_dict(o, offices) for o in rows]

    def get(self, officer_id: str) -> dict[str, Any]:
        officer = self.repo.get(officer_id)
        if officer is None:
            raise NotFoundError("That officer does not exist.", code="officer_not_found")
        offices = {o.id: o for o in self.session.execute(select(FieldOffice)).scalars()}
        return self._as_dict(officer, offices)

    def _as_dict(self, officer: Officer, offices: dict[str, FieldOffice]) -> dict[str, Any]:
        office = offices.get(officer.field_office_id or "")
        return {
            "id": officer.id,
            "code": officer.code,
            "full_name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "role": officer.role,
            "country": officer.country,
            "field_office_id": officer.field_office_id,
            "field_office_name": office.name if office else None,
            "is_dummy": officer.is_dummy,
            "active": officer.active,
            "usage": usage.count_usage(self.session, usage.KIND_OFFICER, officer.id),
            "created_at": officer.created_at.isoformat(),
            "updated_at": officer.updated_at.isoformat(),
        }

    # -------------------------------------------------------------------- writing

    def create(self, data: dict[str, Any], officer: CurrentOfficer) -> dict[str, Any]:
        code = _clean(data.get("code"), limit=CODE_MAX).upper()
        if not code:
            raise ValidationAppError("Give the officer a code, for example PK-MUL-02.")
        if self.repo.get_by_code(code) is not None:
            raise ConflictError(
                f"An officer with the code {code} already exists.", code="duplicate_code"
            )
        row = Officer(
            code=code,
            full_name=self._name(data.get("full_name")),
            email=_clean(data.get("email"), limit=254) or None,
            phone=_clean(data.get("phone"), limit=32) or None,
            role=self._role(data.get("role", ROLE_OFFICER)),
            country=_clean(data.get("country"), limit=2).upper() or "PK",
            field_office_id=self._office(data.get("field_office_id")),
            # A new account starts on the default password and changes it on first use.
            password_hash=hash_password(DEFAULT_PASSWORD),
            active=bool(data.get("active", True)),
            is_dummy=False,
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.repo.add(row)
        audit.record(
            "officer",
            row.id,
            audit.ACTION_CREATE,
            officer.id,
            audit.compute_diff(
                None, {"code": row.code, "full_name": row.full_name, "role": row.role}
            ),
            session=self.session,
        )
        bus.publish(OFFICER_CREATED, {"officer_id": row.id, "code": row.code}, session=self.session)
        self.session.commit()
        return self.get(row.id)

    def update(
        self, officer_id: str, data: dict[str, Any], officer: CurrentOfficer
    ) -> dict[str, Any]:
        row = self.repo.get(officer_id)
        if row is None:
            raise NotFoundError("That officer does not exist.", code="officer_not_found")
        before = self._snapshot(row)

        if "full_name" in data:
            row.full_name = self._name(data["full_name"])
        if "email" in data:
            row.email = _clean(data["email"], limit=254) or None
        if "phone" in data:
            row.phone = _clean(data["phone"], limit=32) or None
        if "field_office_id" in data:
            row.field_office_id = self._office(data["field_office_id"])
        if data.get("country"):
            row.country = _clean(data["country"], limit=2).upper()
        if "role" in data:
            new_role = self._role(data["role"])
            if new_role != row.role and row.role == ROLE_ADMIN:
                self._guard_last_admin(row, "change the role of")
            row.role = new_role
        if "active" in data and bool(data["active"]) != row.active:
            if data["active"]:
                row.active = True
            else:
                self._guard_deactivate(row, officer)
                row.active = False

        row.updated_by = officer.id
        self.session.flush()
        diff = audit.compute_diff(before, self._snapshot(row))
        if diff:
            audit.record(
                "officer", row.id, audit.ACTION_UPDATE, officer.id, diff, session=self.session
            )
            bus.publish(
                OFFICER_UPDATED, {"officer_id": row.id, "code": row.code}, session=self.session
            )
        self.session.commit()
        return self.get(row.id)

    def set_active(self, officer_id: str, active: bool, officer: CurrentOfficer) -> dict[str, Any]:
        row = self.repo.get(officer_id)
        if row is None:
            raise NotFoundError("That officer does not exist.", code="officer_not_found")
        if not active:
            self._guard_deactivate(row, officer)
        before = self._snapshot(row)
        row.active = active
        row.updated_by = officer.id
        self.session.flush()
        audit.record(
            "officer",
            row.id,
            audit.ACTION_STATE_CHANGE,
            officer.id,
            audit.compute_diff(before, self._snapshot(row)),
            session=self.session,
        )
        bus.publish(
            OFFICER_DEACTIVATED if not active else OFFICER_UPDATED,
            {"officer_id": row.id, "code": row.code},
            session=self.session,
        )
        self.session.commit()
        return self.get(row.id)

    # --------------------------------------------------------------------- CSV

    COLUMNS = (
        "code",
        "full_name",
        "email",
        "phone",
        "role",
        "country",
        "field_office_code",
        "active",
    )

    def export_csv(self) -> str:
        from core import csvsafe

        buffer = io.StringIO()
        writer = csvsafe.writer(buffer)
        writer.writerow(self.COLUMNS)
        offices = {o.id: o for o in self.session.execute(select(FieldOffice)).scalars()}
        for row in self.session.execute(select(Officer).order_by(Officer.code)).scalars():
            office = offices.get(row.field_office_id or "")
            writer.writerow(
                [
                    row.code,
                    row.full_name,
                    row.email or "",
                    row.phone or "",
                    row.role,
                    row.country,
                    office.code if office else "",
                    "yes" if row.active else "no",
                ]
            )
        return buffer.getvalue()

    def import_csv(
        self, text: str, officer: CurrentOfficer, *, dry_run: bool = True
    ) -> ImportReport:
        reader = csv.DictReader(io.StringIO(text))
        created = updated = skipped = 0
        errors: list[dict[str, Any]] = []
        offices = {o.code.upper(): o for o in self.session.execute(select(FieldOffice)).scalars()}
        seen: set[str] = set()

        for number, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            code = row.get("code", "").upper()
            try:
                if not code:
                    raise ValidationAppError("The code column is empty.")
                if code in seen:
                    raise ValidationAppError(f"{code} appears twice in this file.")
                seen.add(code)
                office_code = row.get("field_office_code", "").upper()
                if office_code and office_code not in offices:
                    raise ValidationAppError(
                        f"There is no field office with the code {office_code}."
                    )
                payload = {
                    "code": code,
                    "full_name": row.get("full_name", ""),
                    "email": row.get("email", ""),
                    "phone": row.get("phone", ""),
                    "role": row.get("role") or ROLE_OFFICER,
                    "country": row.get("country") or "PK",
                    "field_office_id": offices[office_code].id if office_code else None,
                    "active": row.get("active", "yes").lower() not in ("no", "false", "0"),
                }
                self._name(payload["full_name"])
                self._role(payload["role"])
                existing = self.repo.get_by_code(code)
                if existing is None:
                    created += 1
                    if not dry_run:
                        self.create(payload, officer)
                else:
                    updated += 1
                    if not dry_run:
                        self.update(existing.id, payload, officer)
            except (ValidationAppError, ConflictError, NotFoundError) as error:
                skipped += 1
                errors.append({"row": number, "code": code, "message": error.message})

        return ImportReport(created=created, updated=updated, skipped=skipped, errors=errors)

    # ------------------------------------------------------------------- guards

    def _guard_deactivate(self, row: Officer, officer: CurrentOfficer) -> None:
        if row.id == officer.id:
            raise ValidationAppError(
                "You cannot deactivate your own account. Ask another administrator.",
                code="self_deactivation",
            )
        if row.role == ROLE_ADMIN:
            self._guard_last_admin(row, "deactivate")

    def _guard_last_admin(self, row: Officer, verb: str) -> None:
        remaining = int(
            self.session.execute(
                select(func.count())
                .select_from(Officer)
                .where(Officer.role == ROLE_ADMIN, Officer.active.is_(True), Officer.id != row.id)
            ).scalar_one()
        )
        if remaining == 0:
            raise ValidationAppError(
                f"This is the last active administrator. Make someone else an administrator "
                f"before you {verb} this account.",
                code="last_admin",
            )

    def _name(self, value: Any) -> str:
        name = _clean(value, limit=MAX_NAME)
        if len(name) < 2:
            raise ValidationAppError("Give the officer's full name.")
        return name

    def _role(self, value: Any) -> str:
        role = str(value or "").strip().lower()
        if role not in ROLES:
            raise ValidationAppError(f"The role must be one of: {', '.join(ROLES)}.")
        return role

    def _office(self, value: Any) -> str | None:
        if not value:
            return None
        office = self.offices.get(str(value))
        if office is None:
            raise ValidationAppError("That field office does not exist.", code="office_not_found")
        return office.id

    def _snapshot(self, row: Officer) -> dict[str, Any]:
        return {
            "code": row.code,
            "full_name": row.full_name,
            "email": row.email,
            "phone": row.phone,
            "role": row.role,
            "country": row.country,
            "field_office_id": row.field_office_id,
            "active": row.active,
        }


class OfficeService:
    """Field offices. Deactivating one keeps every officer and farmer that names it."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = FieldOfficeRepository(session)

    def list_offices(self, *, active: bool | None = None) -> list[dict[str, Any]]:
        stmt = select(FieldOffice).order_by(FieldOffice.country, FieldOffice.name)
        if active is not None:
            stmt = stmt.where(FieldOffice.active.is_(active))
        return [self._as_dict(o) for o in self.session.execute(stmt).scalars()]

    def _as_dict(self, office: FieldOffice) -> dict[str, Any]:
        officers = int(
            self.session.execute(
                select(func.count())
                .select_from(Officer)
                .where(Officer.field_office_id == office.id)
            ).scalar_one()
        )
        return {
            "id": office.id,
            "code": office.code,
            "name": office.name,
            "country": office.country,
            "province": office.province,
            "district": office.district,
            "is_dummy": office.is_dummy,
            "active": office.active,
            "officer_count": officers,
            "usage": usage.count_usage(self.session, usage.KIND_OFFICE, office.id),
        }

    def create(self, data: dict[str, Any], officer: CurrentOfficer) -> dict[str, Any]:
        code = _clean(data.get("code"), limit=CODE_MAX).upper()
        if not code:
            raise ValidationAppError("Give the office a code.")
        if self.repo.get_by_code(code) is not None:
            raise ConflictError(
                f"An office with the code {code} already exists.", code="duplicate_code"
            )
        row = FieldOffice(
            code=code,
            name=_clean(data.get("name"), limit=MAX_NAME),
            country=_clean(data.get("country"), limit=2).upper() or "PK",
            province=_clean(data.get("province"), limit=MAX_NAME) or None,
            district=_clean(data.get("district"), limit=MAX_NAME) or None,
            active=bool(data.get("active", True)),
            created_by=officer.id,
            updated_by=officer.id,
        )
        if not row.name:
            raise ValidationAppError("Give the office a name.")
        self.session.add(row)
        self.session.flush()
        audit.record(
            "field_office",
            row.id,
            audit.ACTION_CREATE,
            officer.id,
            audit.compute_diff(None, {"code": row.code, "name": row.name}),
            session=self.session,
        )
        self.session.commit()
        return self._as_dict(row)

    def update(
        self, office_id: str, data: dict[str, Any], officer: CurrentOfficer
    ) -> dict[str, Any]:
        row = self.repo.get(office_id)
        if row is None:
            raise NotFoundError("That field office does not exist.", code="office_not_found")
        before = {
            "name": row.name,
            "province": row.province,
            "district": row.district,
            "active": row.active,
        }
        if data.get("name"):
            row.name = _clean(data["name"], limit=MAX_NAME)
        if "province" in data:
            row.province = _clean(data["province"], limit=MAX_NAME) or None
        if "district" in data:
            row.district = _clean(data["district"], limit=MAX_NAME) or None
        if "active" in data:
            row.active = bool(data["active"])
        row.updated_by = officer.id
        self.session.flush()
        diff = audit.compute_diff(
            before,
            {
                "name": row.name,
                "province": row.province,
                "district": row.district,
                "active": row.active,
            },
        )
        if diff:
            audit.record(
                "field_office", row.id, audit.ACTION_UPDATE, officer.id, diff, session=self.session
            )
        self.session.commit()
        return self._as_dict(row)


def iter_dicts(rows: Iterable[Any]) -> list[dict[str, Any]]:  # pragma: no cover - helper
    return [dict(r) for r in rows]


__all__ = ["ImportReport", "OfficeService", "OfficerService"]
