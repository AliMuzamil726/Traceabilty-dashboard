"""Personal display choices, which every officer changes for themselves.

The rest of Settings is administrator-only; this part is not, because nothing here
affects anybody else's work or any record. An officer may read and write their own row
and no one else's: the officer id comes from the request, never from the body, so there
is no way to ask for someone else's preferences.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from core.errors import ValidationAppError
from module_8.models import DENSITIES, DENSITY_COMFORTABLE, OfficerPreference
from module_8.repository import OfficerPreferenceRepository

#: Crops a default filter may name; ``all`` means no filter.
CROP_CHOICES: Final[tuple[str, ...]] = ("all", "cotton", "hemp")

DEFAULTS: Final[dict[str, Any]] = {
    "sidebar_collapsed": False,
    "table_density": DENSITY_COMFORTABLE,
    "default_crop": "all",
}


class PreferenceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = OfficerPreferenceRepository(session)

    def get(self, officer: CurrentOfficer) -> dict[str, Any]:
        row = self.repo.for_officer(officer.id) if officer.id else None
        if row is None:
            return dict(DEFAULTS)
        return self._as_dict(row)

    def update(self, officer: CurrentOfficer, data: dict[str, Any]) -> dict[str, Any]:
        if not officer.id:  # pragma: no cover - the dependency always supplies one
            raise ValidationAppError("No acting officer.", code="no_officer")
        values: dict[str, Any] = {}

        if "sidebar_collapsed" in data:
            values["sidebar_collapsed"] = bool(data["sidebar_collapsed"])
        if "table_density" in data:
            density = str(data["table_density"] or "").strip().lower()
            if density not in DENSITIES:
                raise ValidationAppError(
                    f"Table density must be one of: {', '.join(DENSITIES)}.",
                    code="invalid_density",
                )
            values["table_density"] = density
        if "default_crop" in data:
            crop = str(data["default_crop"] or "all").strip().lower()
            if crop not in CROP_CHOICES:
                raise ValidationAppError(
                    f"Default crop must be one of: {', '.join(CROP_CHOICES)}.",
                    code="invalid_crop",
                )
            # 'all' is stored as nothing, so a later new crop does not need a migration.
            values["default_crop"] = None if crop == "all" else crop

        if not values:
            return self.get(officer)
        # ``upsert`` skips None, so an explicit clear is applied separately.
        row = self.repo.upsert(officer.id, **{k: v for k, v in values.items() if v is not None})
        if values.get("default_crop", "keep") is None:
            row.default_crop = None
        self.session.flush()
        self.session.commit()
        return self._as_dict(row)

    def _as_dict(self, row: OfficerPreference) -> dict[str, Any]:
        return {
            "sidebar_collapsed": bool(row.sidebar_collapsed),
            "table_density": row.table_density,
            "default_crop": row.default_crop or "all",
        }


__all__ = ["CROP_CHOICES", "DEFAULTS", "PreferenceService"]
