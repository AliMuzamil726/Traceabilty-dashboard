"""Startup and shutdown sequence."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.registry import import_all_models, register_event_handlers, run_module_seeds
from core import schema_upgrade
from core.config import Settings
from core.database import Database
from core.events import bus
from core.guards import guards
from scripts.seed import needs_seed, run_seed

logger = logging.getLogger("sawie.lifespan")


def prepare_storage(settings: Settings) -> None:
    if settings.sqlite_path is not None:
        settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.check_production()
    database: Database = app.state.db
    logger.info(
        "Starting %s %s (env=%s, db=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        database.dialect,
    )
    prepare_storage(settings)
    import_all_models()
    database.create_all()
    # create_all builds missing tables but never alters an existing one, so a column
    # added by a later build is filled in here (core/schema_upgrade.py).
    schema_upgrade.apply(database.engine)

    bus.clear()
    guards.clear()
    register_event_handlers(bus, guards)

    if settings.seed_on_start and settings.is_dev:
        # Demo offices and officers with a known password are development fixtures only;
        # production has already refused SEED_ON_START=true (see Settings.check_production).
        # The seed only inserts rows that are missing and never overwrites edits, so it
        # runs on every start. That way a database created by an earlier build picks up
        # reference data added since (new master lists, locations) without a reset.
        with database.session_scope() as session:
            first_run = needs_seed(session)
            report = run_seed(session)
            module_rows = run_module_seeds(session)
            if report.total or module_rows:
                logger.info(
                    "Startup seed inserted %d shared and %d module row(s)%s",
                    report.total,
                    module_rows,
                    " (new database)" if first_run else "",
                )

    logger.info("Startup complete")
    try:
        yield
    finally:
        logger.info("Shutting down")
        bus.clear()
        guards.clear()
        database.dispose()
        logger.info("Shutdown complete")
