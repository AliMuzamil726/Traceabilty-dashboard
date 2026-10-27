"""Explicit list of every module, its router and its event registration.

Adding a module means adding one :class:`ModuleEntry` below (see README, "How to
add a new module"). Nothing is discovered implicitly.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

from fastapi import APIRouter, FastAPI
from sqlalchemy.orm import Session

import module_1.events as m1_events
import module_1.meta as m1_meta
import module_1.router as m1_router
import module_2.events as m2_events
import module_2.meta as m2_meta
import module_2.router as m2_router
import module_3.events as m3_events
import module_3.meta as m3_meta
import module_3.router as m3_router
import module_4.events as m4_events
import module_4.meta as m4_meta
import module_4.router as m4_router
import module_5.events as m5_events
import module_5.meta as m5_meta
import module_5.router as m5_router
import module_6.events as m6_events
import module_6.meta as m6_meta
import module_6.router as m6_router
import module_7.events as m7_events
import module_7.meta as m7_meta
import module_7.router as m7_router
import module_8.events as m8_events
import module_8.meta as m8_meta
import module_8.router as m8_router
from core.events import EventBus
from core.guards import GuardRegistry
from shared.routers import health, master, officers, offices, sites

RegisterFn = Callable[[EventBus, GuardRegistry], None]


@dataclass(frozen=True)
class ModuleEntry:
    number: int
    name: str
    folder: str
    route_prefix: str
    api_prefix: str
    status: str
    build_order: int
    router: APIRouter | None
    register_events: RegisterFn | None

    @classmethod
    def build(
        cls, meta: ModuleType, router: APIRouter | None, register: RegisterFn | None
    ) -> ModuleEntry:
        return cls(
            number=meta.NUMBER,
            name=meta.NAME,
            folder=meta.FOLDER,
            route_prefix=meta.ROUTE_PREFIX,
            api_prefix=meta.API_PREFIX,
            status=meta.STATUS,
            build_order=meta.BUILD_ORDER,
            router=router,
            register_events=register,
        )


MODULES: tuple[ModuleEntry, ...] = (
    ModuleEntry.build(m1_meta, m1_router.router, m1_events.register),
    ModuleEntry.build(m2_meta, m2_router.router, m2_events.register),
    ModuleEntry.build(m3_meta, m3_router.router, m3_events.register),
    ModuleEntry.build(m4_meta, m4_router.router, m4_events.register),
    ModuleEntry.build(m5_meta, m5_router.router, m5_events.register),
    ModuleEntry.build(m6_meta, m6_router.router, m6_events.register),
    ModuleEntry.build(m7_meta, m7_router.router, m7_events.register),
    ModuleEntry.build(m8_meta, m8_router.router, m8_events.register),
)

SHARED_ROUTERS: tuple[APIRouter, ...] = (
    health.router,
    master.router,
    officers.router,
    offices.router,
    sites.router,
)


def import_all_models() -> None:
    """Import every ORM model so ``Base.metadata`` knows every table."""
    importlib.import_module("shared.models")
    for entry in MODULES:
        if entry.router is not None:
            importlib.import_module(f"{entry.folder}.models")


def register_routers(app: FastAPI) -> None:
    for router in SHARED_ROUTERS:
        app.include_router(router)
    for entry in MODULES:
        if entry.router is not None:
            app.include_router(entry.router)


def run_module_seeds(session: Session) -> int:
    """Run ``module_N/seed.py:run(session)`` for every module that has one.

    Module-owned reference data (for example Module 3's crop clock) cannot be seeded by
    ``scripts/seed.py``, which must not import modules. Each seed is idempotent.
    """
    inserted = 0
    for entry in MODULES:
        if entry.router is None:
            continue
        name = f"{entry.folder}.seed"
        if importlib.util.find_spec(name) is None:
            continue
        inserted += int(importlib.import_module(name).run(session) or 0)
    return inserted


def register_event_handlers(bus: EventBus, guards: GuardRegistry) -> None:
    for entry in MODULES:
        if entry.register_events is not None:
            entry.register_events(bus, guards)
