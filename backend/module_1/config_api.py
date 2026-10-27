"""Dashboard alert thresholds as configuration.

The Dashboard owns no tables, so its thresholds are generic settings
(``alerts.*`` in the Module 8 registry) rather than rows of its own. They are still
read and written through this module, so Settings treats every owner the same way and
no screen reaches past a module into its numbers (DECISIONS D-117).

``module_1.config`` keeps the constants: they stay the defaults, so a database with no
override behaves exactly as before.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core import app_settings
from module_1 import config

CONFIG_KEY = "config.alerts"

#: Setting key -> the constant it defaults to, so the two can never drift apart.
KEYS: dict[str, int] = {
    "alerts.ready_without_pickup_days": config.READY_WITHOUT_PICKUP_DAYS,
    "alerts.heap_idle_days": config.HEAP_IDLE_DAYS,
    "alerts.draft_fieldbook_idle_days": config.DRAFT_FIELDBOOK_IDLE_DAYS,
    "alerts.licence_expiry_warning_days": config.LICENCE_EXPIRY_WARNING_DAYS,
    "alerts.dispatch_grace_days": config.DISPATCH_GRACE_DAYS,
}


def get_config(session: Session | None = None) -> dict[str, Any]:
    """Every alert threshold in force, with its default."""
    return {
        "key": CONFIG_KEY,
        "version": 0,  # each threshold carries its own version in app_settings
        "values": {
            key: app_settings.setting_or(key, default, session) for key, default in KEYS.items()
        },
        "defaults": dict(KEYS),
    }


def ready_without_pickup_days(session: Session | None = None) -> int:
    return int(
        app_settings.setting_or(
            "alerts.ready_without_pickup_days", config.READY_WITHOUT_PICKUP_DAYS, session
        )
    )


def heap_idle_days(session: Session | None = None) -> int:
    return int(app_settings.setting_or("alerts.heap_idle_days", config.HEAP_IDLE_DAYS, session))


def draft_fieldbook_idle_days(session: Session | None = None) -> int:
    return int(
        app_settings.setting_or(
            "alerts.draft_fieldbook_idle_days", config.DRAFT_FIELDBOOK_IDLE_DAYS, session
        )
    )


def licence_expiry_warning_days(session: Session | None = None) -> int:
    return int(
        app_settings.setting_or(
            "alerts.licence_expiry_warning_days", config.LICENCE_EXPIRY_WARNING_DAYS, session
        )
    )


def dispatch_grace_days(session: Session | None = None) -> int:
    return int(
        app_settings.setting_or("alerts.dispatch_grace_days", config.DISPATCH_GRACE_DAYS, session)
    )


__all__ = [
    "CONFIG_KEY",
    "KEYS",
    "dispatch_grace_days",
    "draft_fieldbook_idle_days",
    "get_config",
    "heap_idle_days",
    "licence_expiry_warning_days",
    "ready_without_pickup_days",
]
