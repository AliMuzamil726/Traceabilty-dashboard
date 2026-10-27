"""The location tree: country, province, district, tehsil (and the UK equivalents).

Farmers store place *names*, not location ids, because a tehsil is sometimes typed by
hand before it exists in the tree. So renaming or merging an entry has to rewrite those
farmers in the same transaction, or the old spelling survives and one district's
figures split in two. That rewrite belongs to Module 2, which owns the farmer table, so
this service calls ``module_2.public_api.replace_location_value`` and never writes
farmers itself.

Every rename and merge reports its affected count first (``preview_*``), so the screen
can ask for confirmation with a real number rather than a warning in general terms.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import module_2.public_api as farmers_api
from core import audit, csvsafe
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import LOCATION_CHANGED, bus
from shared.models.location import LEVEL_DISTRICT, LEVEL_PROVINCE, LEVEL_TEHSIL, LEVELS, Location
from shared.repositories.locations import LocationRepository

#: What each level is called per country, for the screen's headings.
LEVEL_LABELS: dict[str, dict[str, str]] = {
    "PK": {LEVEL_PROVINCE: "Province", LEVEL_DISTRICT: "District", LEVEL_TEHSIL: "Tehsil"},
    "GB": {LEVEL_PROVINCE: "Region", LEVEL_DISTRICT: "County", LEVEL_TEHSIL: "Local authority"},
}

#: Which farmer column a level is stored in, per country.
FARMER_COLUMN: dict[str, dict[str, str]] = {
    "PK": {LEVEL_PROVINCE: "province", LEVEL_DISTRICT: "district", LEVEL_TEHSIL: "tehsil"},
    "GB": {LEVEL_PROVINCE: "region", LEVEL_DISTRICT: "county", LEVEL_TEHSIL: "county"},
}


class LocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = LocationRepository(session)

    # -------------------------------------------------------------------- reading

    def tree(self, country: str) -> dict[str, Any]:
        country = country.upper()
        rows = list(
            self.session.execute(
                select(Location)
                .where(Location.country == country)
                .order_by(Location.level, Location.sort_order, Location.name)
            ).scalars()
        )
        by_parent: dict[str | None, list[Location]] = {}
        for row in rows:
            by_parent.setdefault(row.parent_id, []).append(row)

        def build(parent_id: str | None, level_index: int) -> list[dict[str, Any]]:
            level = LEVELS[level_index] if level_index < len(LEVELS) else None
            out = []
            for row in by_parent.get(parent_id, []):
                if level is not None and row.level != level:
                    continue
                out.append(
                    {
                        "id": row.id,
                        "code": row.code,
                        "name": row.name,
                        "level": row.level,
                        "country": row.country,
                        "active": row.active,
                        "usage": self._usage(row),
                        "children": build(row.id, level_index + 1),
                    }
                )
            return out

        return {
            "country": country,
            "labels": LEVEL_LABELS.get(country, LEVEL_LABELS["PK"]),
            "levels": list(LEVELS),
            "items": build(None, 0),
        }

    def _usage(self, row: Location) -> int:
        column = FARMER_COLUMN.get(row.country, {}).get(row.level)
        if column is None:
            return 0
        return farmers_api.count_farmers_at_location(self.session, column, row.name)

    # -------------------------------------------------------------------- writing

    def create(self, data: dict[str, Any], officer: CurrentOfficer) -> dict[str, Any]:
        country = str(data.get("country") or "PK").upper()
        level = str(data.get("level") or "").lower()
        if level not in LEVELS:
            raise ValidationAppError(f"The level must be one of: {', '.join(LEVELS)}.")
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValidationAppError("Give the place a name.")
        parent_id = data.get("parent_id") or None
        if parent_id and self.repo.get(str(parent_id)) is None:
            raise NotFoundError("That parent place does not exist.", code="parent_not_found")
        if level != LEVEL_PROVINCE and not parent_id:
            raise ValidationAppError("Choose the place this one sits inside.")

        code = str(data.get("code") or "").strip().upper() or self._code_for(country, level, name)
        if self.repo.get_by_code(code) is not None:
            raise ConflictError(f"The code {code} is already used.", code="duplicate_code")
        highest = int(
            self.session.execute(
                select(func.coalesce(func.max(Location.sort_order), 0)).where(
                    Location.country == country, Location.level == level
                )
            ).scalar_one()
        )
        row = Location(
            country=country,
            level=level,
            code=code,
            name=name,
            parent_id=str(parent_id) if parent_id else None,
            sort_order=highest + 1,
            active=bool(data.get("active", True)),
        )
        self.session.add(row)
        self.session.flush()
        audit.record(
            "location",
            row.id,
            audit.ACTION_CREATE,
            officer.id,
            audit.compute_diff(None, {"code": code, "name": name, "level": level}),
            session=self.session,
        )
        self._publish(country, level)
        self.session.commit()
        return {"id": row.id, "code": row.code, "name": row.name, "level": row.level}

    def preview_rename(self, location_id: str, new_name: str) -> dict[str, Any]:
        row = self._get(location_id)
        return {
            "id": row.id,
            "from": row.name,
            "to": new_name.strip(),
            "farmers_affected": self._usage(row),
        }

    def rename(self, location_id: str, new_name: str, officer: CurrentOfficer) -> dict[str, Any]:
        row = self._get(location_id)
        name = new_name.strip()
        if not name:
            raise ValidationAppError("Give the place a name.")
        if name == row.name:
            return {"id": row.id, "name": row.name, "farmers_updated": 0}
        column = FARMER_COLUMN.get(row.country, {}).get(row.level)
        updated = 0
        if column:
            updated = farmers_api.replace_location_value(
                self.session, column, row.name, name, officer.id
            )
        before = row.name
        row.name = name
        self.session.flush()
        audit.record(
            "location",
            row.id,
            audit.ACTION_UPDATE,
            officer.id,
            {"name": {"from": before, "to": name}, "farmers_updated": {"from": 0, "to": updated}},
            session=self.session,
        )
        self._publish(row.country, row.level)
        self.session.commit()
        return {"id": row.id, "name": row.name, "farmers_updated": updated}

    def set_active(self, location_id: str, active: bool, officer: CurrentOfficer) -> dict[str, Any]:
        row = self._get(location_id)
        row.active = active
        self.session.flush()
        audit.record(
            "location",
            row.id,
            audit.ACTION_STATE_CHANGE,
            officer.id,
            {"active": {"from": not active, "to": active}},
            session=self.session,
        )
        self._publish(row.country, row.level)
        self.session.commit()
        return {"id": row.id, "active": row.active}

    def delete(self, location_id: str, officer: CurrentOfficer) -> None:
        row = self._get(location_id)
        used = self._usage(row)
        if used:
            raise ValidationAppError(
                f"{used} farmer(s) are recorded in {row.name}, so it cannot be deleted. "
                "Deactivate it instead, or merge it into another place.",
                code="location_in_use",
                details={"usage": used},
            )
        children = int(
            self.session.execute(
                select(func.count()).select_from(Location).where(Location.parent_id == row.id)
            ).scalar_one()
        )
        if children:
            raise ValidationAppError(
                f"{row.name} still contains {children} place(s). Remove or move them first.",
                code="location_has_children",
            )
        audit.record(
            "location",
            row.id,
            audit.ACTION_DELETE,
            officer.id,
            audit.compute_diff({"code": row.code, "name": row.name}, None),
            session=self.session,
        )
        country, level = row.country, row.level
        self.session.delete(row)
        self._publish(country, level)
        self.session.commit()

    def preview_merge(self, source_id: str, target_id: str) -> dict[str, Any]:
        source, target = self._get(source_id), self._get(target_id)
        self._check_merge(source, target)
        return {
            "from": source.name,
            "to": target.name,
            "farmers_affected": self._usage(source),
            "children_moved": int(
                self.session.execute(
                    select(func.count())
                    .select_from(Location)
                    .where(Location.parent_id == source.id)
                ).scalar_one()
            ),
        }

    def merge(self, source_id: str, target_id: str, officer: CurrentOfficer) -> dict[str, Any]:
        source, target = self._get(source_id), self._get(target_id)
        self._check_merge(source, target)
        column = FARMER_COLUMN.get(source.country, {}).get(source.level)
        updated = 0
        if column:
            updated = farmers_api.replace_location_value(
                self.session, column, source.name, target.name, officer.id
            )
        moved = 0
        for child in self.session.execute(
            select(Location).where(Location.parent_id == source.id)
        ).scalars():
            child.parent_id = target.id
            moved += 1
        self.session.flush()
        audit.record(
            "location",
            source.id,
            audit.ACTION_DELETE,
            officer.id,
            {
                "merged_into": {"from": source.name, "to": target.name},
                "farmers_updated": {"from": 0, "to": updated},
                "children_moved": {"from": 0, "to": moved},
            },
            session=self.session,
        )
        country, level = source.country, source.level
        self.session.delete(source)
        self._publish(country, level)
        self.session.commit()
        return {"farmers_updated": updated, "children_moved": moved, "target": target.name}

    # ------------------------------------------------------------------------ CSV

    COLUMNS = ("country", "level", "code", "name", "parent_code", "active")

    def export_csv(self, country: str) -> str:
        buffer = io.StringIO()
        writer = csvsafe.writer(buffer)
        writer.writerow(self.COLUMNS)
        rows = list(
            self.session.execute(
                select(Location)
                .where(Location.country == country.upper())
                .order_by(Location.level, Location.name)
            ).scalars()
        )
        by_id = {r.id: r for r in rows}
        for row in rows:
            parent = by_id.get(row.parent_id or "")
            writer.writerow(
                [
                    row.country,
                    row.level,
                    row.code,
                    row.name,
                    parent.code if parent else "",
                    "yes" if row.active else "no",
                ]
            )
        return buffer.getvalue()

    def import_csv(
        self, text: str, officer: CurrentOfficer, *, dry_run: bool = True
    ) -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(text))
        created = skipped = 0
        errors: list[dict[str, Any]] = []
        preview: list[dict[str, Any]] = []
        for number, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            try:
                parent_code = row.get("parent_code", "").upper()
                parent = self.repo.get_by_code(parent_code) if parent_code else None
                if parent_code and parent is None:
                    raise ValidationAppError(f"There is no place with the code {parent_code}.")
                payload = {
                    "country": row.get("country") or "PK",
                    "level": row.get("level", ""),
                    "code": row.get("code", ""),
                    "name": row.get("name", ""),
                    "parent_id": parent.id if parent else None,
                    "active": row.get("active", "yes").lower() not in ("no", "false", "0"),
                }
                if row.get("code") and self.repo.get_by_code(row["code"].upper()) is not None:
                    skipped += 1
                    preview.append({"row": number, "action": "skip", "name": payload["name"]})
                    continue
                created += 1
                preview.append(
                    {
                        "row": number,
                        "action": "create",
                        **{k: payload[k] for k in ("country", "level", "name")},
                    }
                )
                if not dry_run:
                    self.create(payload, officer)
            except (ValidationAppError, ConflictError, NotFoundError) as error:
                skipped += 1
                errors.append({"row": number, "message": error.message})
        return {
            "dry_run": dry_run,
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "ok": not errors,
            "preview": preview[:200],
        }

    # -------------------------------------------------------------------- helpers

    def _get(self, location_id: str) -> Location:
        row = self.repo.get(location_id)
        if row is None:
            raise NotFoundError("That place does not exist.", code="location_not_found")
        return row

    def _check_merge(self, source: Location, target: Location) -> None:
        if source.id == target.id:
            raise ValidationAppError("Choose two different places.")
        if source.level != target.level or source.country != target.country:
            raise ValidationAppError(
                "Both places must be at the same level and in the same country.",
                code="merge_mismatch",
            )

    def _code_for(self, country: str, level: str, name: str) -> str:
        base = "".join(c for c in name.upper() if c.isalnum())[:12] or "PLACE"
        code = f"{country}-{level[:3].upper()}-{base}"
        suffix = 1
        while self.repo.get_by_code(code) is not None:
            suffix += 1
            code = f"{country}-{level[:3].upper()}-{base}-{suffix}"
        return code

    def _publish(self, country: str, level: str) -> None:
        bus.publish(LOCATION_CHANGED, {"country": country, "level": level}, session=self.session)


__all__ = ["FARMER_COLUMN", "LEVEL_LABELS", "LocationService"]
