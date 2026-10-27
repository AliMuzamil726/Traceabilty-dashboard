from __future__ import annotations

from fastapi import APIRouter, Depends

from core.config import Settings
from core.database import Database, utcnow
from core.deps import get_database, get_settings_dep
from shared.schemas import DatabaseHealth, HealthOut

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthOut, summary="Service health")
def health(
    settings: Settings = Depends(get_settings_dep),
    database: Database = Depends(get_database),
) -> HealthOut:
    """Always 200 while the process runs; ``status`` is ``degraded`` if the DB is unreachable."""
    reachable = database.is_reachable()
    return HealthOut(
        status="ok" if reachable else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        database=DatabaseHealth(reachable=reachable, dialect=database.dialect),
        server_time=utcnow(),
    )
