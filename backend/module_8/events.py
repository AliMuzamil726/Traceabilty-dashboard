"""Events published by Module 8 (Settings), and what it installs at startup.

Settings is the one module that registers things rather than only subscribing: the
setting definitions go to :mod:`core.app_settings` here, so ``core`` never imports a
module, and the usage counters for its own shared data go to :mod:`core.usage`.

It also subscribes to its own ``config.changed``: a value is written by one worker's
service call, and every cache that holds a resolved value has to let go of it. Doing
that in a handler rather than inside the service means any future publisher of
``config.changed`` gets the same invalidation for free.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from core import app_settings, events, usage
from core.events import Event, EventBus
from core.guards import GuardRegistry

logger = logging.getLogger("sawie.module_8")

PUBLISHES: tuple[str, ...] = (
    events.CONFIG_CHANGED,
    events.OFFICER_CREATED,
    events.OFFICER_UPDATED,
    events.OFFICER_DEACTIVATED,
    events.LIST_CHANGED,
    events.LOCATION_CHANGED,
    events.BACKUP_CREATED,
    events.BACKUP_RESTORED,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""

SUBSCRIBES: tuple[str, ...] = (
    events.CONFIG_CHANGED,
    events.LIST_CHANGED,
    events.LOCATION_CHANGED,
)

OWNER = "module_8"


def on_config_changed(event: Event) -> None:
    """Drop resolved values so the next read sees the new one (no restart needed)."""
    key = event.payload.get("key")
    # A block change (the crop clock, a list) can move any number of values, so the
    # whole cache goes; a single key clears only itself.
    if isinstance(key, str) and key in app_settings.definitions():
        app_settings.clear_cache(key)
    else:
        app_settings.clear_cache()
    logger.debug("Settings cache cleared after %s (%s)", event.name, key)


def on_reference_changed(event: Event) -> None:
    """A list value or location changed: anything derived from reference data refreshes."""
    app_settings.clear_cache()
    logger.debug("Reference data changed: %s", event.payload)


def _count_officer_backups(session: Any, officer_id: str) -> int:
    """An officer who took backups is still referenced by them."""
    from module_8.models import BackupRecord

    return int(
        session.execute(
            select(func.count())
            .select_from(BackupRecord)
            .where(BackupRecord.created_by == officer_id)
        ).scalar_one()
    )


def _count_officer_preferences(session: Any, officer_id: str) -> int:
    """A preferences row is personal: it follows the officer and never blocks a delete."""
    return 0


on_config_changed.__qualname__ = "module_8.on_config_changed"
on_reference_changed.__qualname__ = "module_8.on_reference_changed"


def register(bus: EventBus, guards: GuardRegistry) -> None:
    """Install the settings registry, the usage counters and the cache invalidation."""
    from module_8 import registry

    registry.install()

    bus.subscribe(events.CONFIG_CHANGED, on_config_changed)
    bus.subscribe(events.LIST_CHANGED, on_reference_changed)
    bus.subscribe(events.LOCATION_CHANGED, on_reference_changed)

    usage.register_counter(usage.KIND_OFFICER, 8, "Backups", _count_officer_backups)
    _ = guards  # Settings registers no guard: it never blocks another module's action.


__all__ = ["OWNER", "PUBLISHES", "SUBSCRIBES", "register"]
