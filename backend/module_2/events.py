"""Events published by Module 2 (Register Farmer) and handlers it subscribes.

Handlers are registered once at startup by ``app.lifespan`` via :func:`register`.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import events, usage
from core.events import EventBus
from core.guards import GuardRegistry

PUBLISHES: tuple[str, ...] = (
    events.FARMER_REGISTERED,
    events.FARMER_UPDATED,
    events.FIELD_CREATED,
    events.FIELD_UPDATED,
    events.FIELD_DELETED,
)
"""Event names this module publishes (payloads documented in docs/CONTRACTS.md)."""


def _count_list_value(session: Session, key: str) -> int:
    """Farmers whose season profile holds this list value (tenure is the only one)."""
    from module_2.models import FarmerSeasonProfile

    list_key, _, value = key.partition(":")
    if list_key != "tenure":
        return 0
    return int(
        session.execute(
            select(func.count())
            .select_from(FarmerSeasonProfile)
            .where(FarmerSeasonProfile.tenure == value)
        ).scalar_one()
    )


def _count_office(session: Session, office_id: str) -> int:
    from module_2.models import Farmer

    return int(
        session.execute(
            select(func.count()).select_from(Farmer).where(Farmer.field_office_id == office_id)
        ).scalar_one()
    )


def _count_officer(session: Session, officer_id: str) -> int:
    from module_2.models import Farmer

    return int(
        session.execute(
            select(func.count()).select_from(Farmer).where(Farmer.registered_by == officer_id)
        ).scalar_one()
    )


def register(bus: EventBus, guards: GuardRegistry) -> None:
    """Subscribe handlers, register guard checks and the usage counters Settings reads."""
    del bus, guards
    usage.register_counter(usage.KIND_LIST_VALUE, 2, "Farmers", _count_list_value)
    usage.register_counter(usage.KIND_OFFICE, 2, "Farmers", _count_office)
    usage.register_counter(usage.KIND_OFFICER, 2, "Farmers registered", _count_officer)
