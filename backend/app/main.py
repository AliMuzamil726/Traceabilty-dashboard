"""FastAPI application factory. Started by ``uvicorn app.main:app`` from ``backend/``."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.lifespan import lifespan, prepare_storage
from app.registry import register_routers
from core.config import Settings, get_settings
from core.database import Database
from core.deps import OFFICER_HEADER
from core.errors import register_exception_handlers
from core.logging import REQUEST_ID_HEADER, configure_logging, request_id_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    prepare_storage(settings)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description="Fibre-crop traceability platform (cotton and hemp).",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database(settings.resolved_database_url)

    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, OFFICER_HEADER],
    )
    register_exception_handlers(app)
    register_routers(app)
    return app


app = create_app()
