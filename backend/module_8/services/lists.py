"""The dropdown list manager.

Two rules make this screen safe to use on a live database:

* **Keys are stable, labels are not.** Every module stores the value *key*
  (``urea``), never the label ("Urea"). So a label may be corrected at any time and
  every existing record follows along, while a key that is in use can never change.
  ``backend/tests/test_stable_keys.py`` proves no module stores a label.
* **Deactivate hides, delete removes.** Deactivating a value takes it out of new
  dropdowns and leaves every existing record and draft exactly as it is. Deleting is
  refused while any record uses it (``core.usage``).

List *keys* cannot be created or deleted here: a list exists because a form step
refers to it. :data:`REQUIRED_BY` names the screens that use each one, so an
administrator can see what a change touches.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Final

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from core import audit, csvsafe, usage
from core.deps import CurrentOfficer
from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.events import LIST_CHANGED, bus
from shared.models.master_list import MasterList
from shared.repositories.master_lists import MasterListRepository

#: Which screens read each list. Shown as "Required by" so a change is never blind.
REQUIRED_BY: Final[dict[str, tuple[str, ...]]] = {
    "irrigation_source": ("Fieldbook: Irrigation",),
    "irrigation_method": ("Fieldbook: Irrigation",),
    "fertiliser": ("Fieldbook: Soil and nutrition",),
    "pesticide": ("Fieldbook: Pest and disease",),
    "seed_variety": ("Fieldbook: Sowing", "Register Farmer"),
    "tillage": ("Fieldbook: Land preparation",),
    "soil_texture": ("Fieldbook: Field information",),
    "energy_source": ("Fieldbook: Energy",),
    "tenure": ("Register Farmer",),
    "crop_variety": ("Fieldbook: Sowing",),
}

#: Groups the left column of the screen shows.
GROUP_COTTON = "cotton"
GROUP_HEMP = "hemp"
GROUP_SHARED = "shared"


def group_for(list_key: str, crop: str | None) -> str:
    if crop == "cotton":
        return GROUP_COTTON
    if crop == "hemp":
        return GROUP_HEMP
    return GROUP_SHARED


class ListService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = MasterListRepository(session)

    # -------------------------------------------------------------------- reading

    def list_lists(self) -> list[dict[str, Any]]:
        """Every list key with its size and how many records use its values."""
        rows = self.session.execute(
            select(
                MasterList.list_key,
                MasterList.crop,
                func.count(MasterList.id),
                func.sum(func.cast(MasterList.active, Integer)),
            ).group_by(MasterList.list_key, MasterList.crop)
        ).all()
        out: dict[str, dict[str, Any]] = {}
        for list_key, crop, total, active in rows:
            entry = out.setdefault(
                list_key,
                {
                    "key": list_key,
                    "label": list_key.replace("_", " ").capitalize(),
                    "group": group_for(list_key, crop),
                    "values": 0,
                    "active_values": 0,
                    "required_by": list(REQUIRED_BY.get(list_key, ())),
                },
            )
            entry["values"] += int(total or 0)
            entry["active_values"] += int(active or 0)
        return sorted(out.values(), key=lambda e: (e["group"], e["key"]))

    def values_for(self, list_key: str, *, include_usage: bool = True) -> list[dict[str, Any]]:
        if not self.repo.key_exists(list_key):
            raise NotFoundError(f"There is no list called {list_key}.", code="unknown_list")
        rows = self.repo.options(list_key, include_inactive=True)
        return [self._as_dict(row, include_usage=include_usage) for row in rows]

    def _as_dict(self, row: MasterList, *, include_usage: bool = True) -> dict[str, Any]:
        used = (
            usage.count_usage(self.session, usage.KIND_LIST_VALUE, f"{row.list_key}:{row.value}")
            if include_usage
            else 0
        )
        return {
            "id": row.id,
            "list_key": row.list_key,
            "value": row.value,
            "label": row.label,
            "sort_order": row.sort_order,
            "country": row.country,
            "crop": row.crop,
            "active": row.active,
            "usage": used,
            "can_delete": used == 0,
        }

    # -------------------------------------------------------------------- writing

    def add_value(
        self, list_key: str, data: dict[str, Any], officer: CurrentOfficer
    ) -> dict[str, Any]:
        if not self.repo.key_exists(list_key):
            raise NotFoundError(f"There is no list called {list_key}.", code="unknown_list")
        value = self._value_key(data.get("value") or data.get("label"))
        country = (data.get("country") or None) and str(data["country"]).upper()
        crop = (data.get("crop") or None) and str(data["crop"]).lower()
        if self.repo.find_exact(list_key, value, country, crop) is not None:
            raise ConflictError(
                f"This list already has a value called {value}.", code="duplicate_value"
            )
        label = str(data.get("label") or value).strip()
        if not label:
            raise ValidationAppError("Give the value a label.")
        highest = int(
            self.session.execute(
                select(func.coalesce(func.max(MasterList.sort_order), 0)).where(
                    MasterList.list_key == list_key
                )
            ).scalar_one()
        )
        row = MasterList(
            list_key=list_key,
            value=value,
            label=label,
            sort_order=highest + 1,
            country=country,
            crop=crop,
            active=bool(data.get("active", True)),
            created_by=officer.id,
            updated_by=officer.id,
        )
        self.session.add(row)
        self.session.flush()
        audit.record(
            "master_list",
            row.id,
            audit.ACTION_CREATE,
            officer.id,
            audit.compute_diff(None, {"list_key": list_key, "value": value, "label": label}),
            session=self.session,
        )
        self._publish(list_key, "created")
        self.session.commit()
        return self._as_dict(row)

    def update_value(
        self, value_id: str, data: dict[str, Any], officer: CurrentOfficer
    ) -> dict[str, Any]:
        row = self.repo.get(value_id)
        if row is None:
            raise NotFoundError("That value does not exist.", code="value_not_found")
        before = {
            "label": row.label,
            "active": row.active,
            "country": row.country,
            "crop": row.crop,
        }

        if "value" in data and data["value"] and data["value"] != row.value:
            # The key is what every record stores, so it can only change while unused.
            if usage.is_in_use(self.session, usage.KIND_LIST_VALUE, f"{row.list_key}:{row.value}"):
                raise ValidationAppError(
                    "This value is already stored on records, so its key cannot change. "
                    "You can edit the label instead.",
                    code="key_in_use",
                )
            row.value = self._value_key(data["value"])
        if data.get("label"):
            row.label = str(data["label"]).strip()
        if "active" in data:
            row.active = bool(data["active"])
        if "country" in data:
            row.country = str(data["country"]).upper() if data["country"] else None
        if "crop" in data:
            row.crop = str(data["crop"]).lower() if data["crop"] else None
        row.updated_by = officer.id
        self.session.flush()
        diff = audit.compute_diff(
            before,
            {"label": row.label, "active": row.active, "country": row.country, "crop": row.crop},
        )
        if diff:
            audit.record(
                "master_list", row.id, audit.ACTION_UPDATE, officer.id, diff, session=self.session
            )
            self._publish(row.list_key, "updated")
        self.session.commit()
        return self._as_dict(row)

    def delete_value(self, value_id: str, officer: CurrentOfficer) -> None:
        row = self.repo.get(value_id)
        if row is None:
            raise NotFoundError("That value does not exist.", code="value_not_found")
        used = usage.count_usage(self.session, usage.KIND_LIST_VALUE, f"{row.list_key}:{row.value}")
        if used:
            raise ValidationAppError(
                f"{used} record(s) use this value, so it cannot be deleted. "
                "Deactivate it instead: it then disappears from new entries and existing "
                "records keep showing it.",
                code="value_in_use",
                details={"usage": used},
            )
        audit.record(
            "master_list",
            row.id,
            audit.ACTION_DELETE,
            officer.id,
            audit.compute_diff(
                {"list_key": row.list_key, "value": row.value, "label": row.label}, None
            ),
            session=self.session,
        )
        list_key = row.list_key
        self.session.delete(row)
        self._publish(list_key, "deleted")
        self.session.commit()

    def reorder(
        self, list_key: str, value_ids: list[str], officer: CurrentOfficer
    ) -> list[dict[str, Any]]:
        rows = {r.id: r for r in self.repo.options(list_key, include_inactive=True)}
        unknown = [i for i in value_ids if i not in rows]
        if unknown:
            raise ValidationAppError(
                "That order names a value from another list.", code="bad_order"
            )
        for position, value_id in enumerate(value_ids, start=1):
            rows[value_id].sort_order = position
            rows[value_id].updated_by = officer.id
        self.session.flush()
        audit.record(
            "master_list",
            list_key,
            audit.ACTION_UPDATE,
            officer.id,
            {"order": {"from": "previous", "to": [rows[i].value for i in value_ids]}},
            session=self.session,
        )
        self._publish(list_key, "reordered")
        self.session.commit()
        return self.values_for(list_key)

    # ------------------------------------------------------------------------ CSV

    COLUMNS = ("value", "label", "sort_order", "country", "crop", "active")

    def export_csv(self, list_key: str) -> str:
        rows = self.values_for(list_key, include_usage=False)
        buffer = io.StringIO()
        writer = csvsafe.writer(buffer)
        writer.writerow(self.COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    row["value"],
                    row["label"],
                    row["sort_order"],
                    row["country"] or "",
                    row["crop"] or "",
                    "yes" if row["active"] else "no",
                ]
            )
        return buffer.getvalue()

    def import_csv(
        self, list_key: str, text: str, officer: CurrentOfficer, *, dry_run: bool = True
    ) -> dict[str, Any]:
        if not self.repo.key_exists(list_key):
            raise NotFoundError(f"There is no list called {list_key}.", code="unknown_list")
        reader = csv.DictReader(io.StringIO(text))
        created = updated = skipped = 0
        errors: list[dict[str, Any]] = []
        preview: list[dict[str, Any]] = []
        seen: set[str] = set()

        for number, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            try:
                value = self._value_key(row.get("value") or row.get("label"))
                if value in seen:
                    raise ValidationAppError(f"{value} appears twice in this file.")
                seen.add(value)
                country = row.get("country", "").upper() or None
                crop = row.get("crop", "").lower() or None
                existing = self.repo.find_exact(list_key, value, country, crop)
                action = "update" if existing else "create"
                payload = {
                    "value": value,
                    "label": row.get("label") or value,
                    "country": country,
                    "crop": crop,
                    "active": row.get("active", "yes").lower() not in ("no", "false", "0"),
                }
                preview.append({"row": number, "action": action, **payload})
                if action == "create":
                    created += 1
                    if not dry_run:
                        self.add_value(list_key, payload, officer)
                else:
                    updated += 1
                    if not dry_run and existing is not None:
                        self.update_value(existing.id, payload, officer)
            except (ValidationAppError, ConflictError, NotFoundError) as error:
                skipped += 1
                errors.append({"row": number, "message": error.message})

        return {
            "dry_run": dry_run,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "ok": not errors,
            "preview": preview[:200],
        }

    # -------------------------------------------------------------------- helpers

    def _value_key(self, raw: Any) -> str:
        text = str(raw or "").strip().lower().replace(" ", "_")
        key = "".join(c for c in text if c.isalnum() or c in "_-")
        if not key:
            raise ValidationAppError("Give the value a key, for example 'drip_irrigation'.")
        if len(key) > 64:
            raise ValidationAppError("A value key may be at most 64 characters.")
        return key

    def _publish(self, list_key: str, action: str) -> None:
        bus.publish(LIST_CHANGED, {"list_key": list_key, "action": action}, session=self.session)


__all__ = ["GROUP_COTTON", "GROUP_HEMP", "GROUP_SHARED", "REQUIRED_BY", "ListService", "group_for"]
