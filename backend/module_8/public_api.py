"""Public API of Module 8 (Settings).

The ONLY file other modules may import from this module. Settings owns no business
record, so this surface is small: configuration other code needs, the officers it may
list, one officer's display choices, and whether the database is being replaced.

A module that needs a single configurable value should call
``core.app_settings.get_setting`` directly rather than coming through here; that
accessor is in ``core`` precisely so no module has to import Module 8 to read a number.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core import app_settings
from module_8.services import backups, public_config
from module_8.services.preferences import DEFAULTS, PreferenceService
from shared.repositories.officers import OfficerRepository


def get_public_config(session: Session | None = None) -> dict[str, Any]:
    """The non-sensitive configuration the browser is served (tiles, QR base URL)."""
    return public_config.public_config(session)


def get_setting(key: str, session: Session | None = None) -> Any:
    """One setting in force: database override, then ``.env``, then the default."""
    return app_settings.get_setting(key, session)


def get_officer_preferences(session: Session, officer_id: str) -> dict[str, Any]:
    """One officer's display choices, or the defaults when they have none saved."""
    row = PreferenceService(session).repo.for_officer(officer_id)
    if row is None:
        return dict(DEFAULTS)
    return {
        "sidebar_collapsed": bool(row.sidebar_collapsed),
        "table_density": row.table_density,
        "default_crop": row.default_crop or "all",
    }


def list_active_officers(session: Session, office_id: str | None = None) -> list[dict[str, Any]]:
    """Active officers, optionally in one field office, for a picker in another module."""
    rows = [o for o in OfficerRepository(session).list_all() if o.active]
    if office_id:
        rows = [o for o in rows if o.field_office_id == office_id]
    return [
        {
            "id": o.id,
            "code": o.code,
            "full_name": o.full_name,
            "role": o.role,
            "field_office_id": o.field_office_id,
        }
        for o in sorted(rows, key=lambda o: o.full_name)
    ]


def is_maintenance_mode() -> bool:
    """True while a restore is replacing the database; every write must refuse."""
    return backups.is_maintenance_mode()


def maintenance_reason() -> str:
    return backups.maintenance_reason()


__all__ = [
    "get_officer_preferences",
    "get_public_config",
    "get_setting",
    "is_maintenance_mode",
    "list_active_officers",
    "maintenance_reason",
]
