"""Ginners and processors: the places deliveries arrive and heaps are built.

A site code is printed on heap IDs (``BWP-G1-H01``), so once a heap exists the code can
never change; the name, address and contact may always be corrected. Deactivating a
site keeps every delivery and heap that names it and only takes it out of the pickers
for new work.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import audit, usage
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from shared.models.site import Site
from shared.repositories.sites import SiteRepository

MAX_NAME: Final = 120
CODE_MAX: Final = 32
TYPES: Final[tuple[str, ...]] = ("ginner", "processor")
CROPS: Final[tuple[str, ...]] = ("cotton", "hemp")

#: Audit entity name.
AUDIT_ENTITY = "site"


def _clean(value: Any, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


class SiteService:
    """CRUD for sites, with the usage counts that decide what may still be changed."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = SiteRepository(session)

    # ------------------------------------------------------------------ reading

    def list_sites(
        self, *, crop: str | None = None, active: bool | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(Site).order_by(Site.country, Site.crop, Site.name)
        if crop:
            stmt = stmt.where(Site.crop == crop)
        if active is not None:
            stmt = stmt.where(Site.active.is_(active))
        return [self._as_dict(s) for s in self.session.execute(stmt).scalars()]

    def get(self, site_id: str) -> dict[str, Any]:
        return self._as_dict(self._row(site_id))

    def _row(self, site_id: str) -> Site:
        row = self.repo.get(site_id) or self.repo.get_by_code(str(site_id).upper())
        if row is None:
            raise NotFoundError("That site does not exist.", code="site_not_found")
        return row

    def _as_dict(self, site: Site) -> dict[str, Any]:
        breakdown = usage.usage_breakdown(self.session, usage.KIND_SITE, site.id)
        used = sum(count for _, count in breakdown)
        return {
            "id": site.id,
            "code": site.code,
            "name": site.name,
            "type": site.type,
            "crop": site.crop,
            "country": site.country,
            "address": site.address,
            "region": site.region,
            "contact_person": site.contact_person,
            "contact_phone": site.contact_phone,
            "is_dummy": site.is_dummy,
            "active": site.active,
            "usage": used,
            "usage_breakdown": [{"label": label, "count": count} for label, count in breakdown],
            # The code is printed on heap IDs, so it is frozen as soon as anything uses it.
            "code_locked": used > 0,
        }

    # ------------------------------------------------------------------ writing

    def create(self, data: dict[str, Any], officer: CurrentOfficer) -> dict[str, Any]:
        code = _clean(data.get("code"), limit=CODE_MAX).upper()
        if not code:
            raise ValidationAppError("Give the site a code.")
        if self.repo.get_by_code(code) is not None:
            raise ConflictError(
                f"A site with the code {code} already exists.", code="duplicate_code"
            )
        name = _clean(data.get("name"), limit=MAX_NAME)
        if not name:
            raise ValidationAppError("Give the site a name.")
        kind = _clean(data.get("type"), limit=16).lower()
        if kind not in TYPES:
            raise ValidationAppError(f"Type must be one of: {', '.join(TYPES)}.")
        crop = _clean(data.get("crop"), limit=16).lower()
        if crop not in CROPS:
            raise ValidationAppError(f"Crop must be one of: {', '.join(CROPS)}.")

        row = Site(
            code=code,
            name=name,
            type=kind,
            crop=crop,
            country=_clean(data.get("country"), limit=2).upper() or "PK",
            address=_clean(data.get("address"), limit=255) or None,
            region=_clean(data.get("region"), limit=MAX_NAME) or None,
            contact_person=_clean(data.get("contact_person"), limit=MAX_NAME) or None,
            contact_phone=_clean(data.get("contact_phone"), limit=32) or None,
            active=bool(data.get("active", True)),
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.session.add(row)
        self.session.flush()
        audit.record(
            AUDIT_ENTITY,
            row.id,
            audit.ACTION_CREATE,
            officer.id,
            audit.compute_diff(None, {"code": row.code, "name": row.name, "crop": row.crop}),
            session=self.session,
        )
        self.session.commit()
        self._publish()
        return self._as_dict(row)

    def update(self, site_id: str, data: dict[str, Any], officer: CurrentOfficer) -> dict[str, Any]:
        row = self._row(site_id)
        before = self._snapshot(row)

        if data.get("code"):
            wanted = _clean(data["code"], limit=CODE_MAX).upper()
            if wanted != row.code:
                if usage.is_in_use(self.session, usage.KIND_SITE, row.id):
                    raise ValidationAppError(
                        "This site already has deliveries or heaps, so its code is part of "
                        "records that have been printed. The code can no longer change.",
                        code="code_locked",
                    )
                if self.repo.get_by_code(wanted) is not None:
                    raise ConflictError(
                        f"A site with the code {wanted} already exists.", code="duplicate_code"
                    )
                row.code = wanted
        if data.get("name"):
            row.name = _clean(data["name"], limit=MAX_NAME)
        for field_name, limit in (
            ("address", 255),
            ("region", MAX_NAME),
            ("contact_person", MAX_NAME),
            ("contact_phone", 32),
        ):
            if field_name in data:
                setattr(row, field_name, _clean(data[field_name], limit=limit) or None)
        if "active" in data:
            row.active = bool(data["active"])
        row.updated_by = officer.id
        self.session.flush()

        diff = audit.compute_diff(before, self._snapshot(row))
        if diff:
            audit.record(
                AUDIT_ENTITY, row.id, audit.ACTION_UPDATE, officer.id, diff, session=self.session
            )
        self.session.commit()
        if diff:
            self._publish()
        return self._as_dict(row)

    def set_active(self, site_id: str, active: bool, officer: CurrentOfficer) -> dict[str, Any]:
        return self.update(site_id, {"active": active}, officer)

    def delete(self, site_id: str, officer: CurrentOfficer) -> None:
        """Only an unused site can go; anything referenced is deactivated instead."""
        row = self._row(site_id)
        used = usage.count_usage(self.session, usage.KIND_SITE, row.id)
        if used:
            raise ValidationAppError(
                f"{row.name} is used by {used} record(s). Deactivate it instead, which hides "
                "it from new work and keeps the records that name it.",
                code="site_in_use",
            )
        audit.record(
            AUDIT_ENTITY,
            row.id,
            audit.ACTION_DELETE,
            officer.id,
            audit.compute_diff({"code": row.code, "name": row.name}, None),
            session=self.session,
        )
        self.session.delete(row)
        self.session.commit()
        self._publish()

    def _snapshot(self, row: Site) -> dict[str, Any]:
        return {
            "code": row.code,
            "name": row.name,
            "address": row.address,
            "region": row.region,
            "contact_person": row.contact_person,
            "contact_phone": row.contact_phone,
            "active": row.active,
        }

    def _publish(self) -> None:
        bus.publish(CONFIG_CHANGED, {"key": "sites", "group": "sites"}, session=self.session)

    # --------------------------------------------------------------- statistics

    def counts(self) -> dict[str, int]:
        total = int(self.session.execute(select(func.count()).select_from(Site)).scalar_one())
        active = int(
            self.session.execute(
                select(func.count()).select_from(Site).where(Site.active.is_(True))
            ).scalar_one()
        )
        return {"total": total, "active": active}


__all__ = ["CROPS", "TYPES", "SiteService"]
