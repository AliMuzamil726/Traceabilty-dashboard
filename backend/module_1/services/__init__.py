"""Business logic for Module 1 (Dashboard / Home).

The dashboard owns no tables. Every figure is read from another module's
``public_api`` by :mod:`module_1.services.sources`, shaped by one of the section
builders here, and kept for 30 seconds by :mod:`module_1.services.cache`.

:class:`DashboardService` is the one object the router depends on. Each of its methods
is one section of the screen, so a section can load, fail and retry on its own without
the rest of the page waiting for it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1 import config, meta
from module_1.services import (
    activity,
    alerts,
    cache,
    charts,
    filters,
    links,
    mapview,
    officers,
    overview,
    sources,
)
from module_1.services.filters import DashboardFilters, DateRange, default_scope, today
from shared.schemas import ModuleMetaOut

Section = dict[str, Any]


def get_meta() -> ModuleMetaOut:
    return ModuleMetaOut(
        number=meta.NUMBER,
        name=meta.NAME,
        route_prefix=meta.ROUTE_PREFIX,
        api_prefix=meta.API_PREFIX,
        status=meta.STATUS,
        build_order=meta.BUILD_ORDER,
        purpose=meta.PURPOSE,
    )


class DashboardService:
    """Reads every section, each cached by its own name and parameters."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------- caching

    def _db_key(self) -> str:
        return str(self.session.get_bind().url)

    def _cached(
        self,
        name: str,
        f: DashboardFilters,
        officer: CurrentOfficer,
        compute: Callable[[], Section],
        *extra: Any,
    ) -> Section:
        return cache.get_or_compute((name, self._db_key(), *f.key(officer), *extra), compute)

    # ------------------------------------------------------------------ sections

    def overview(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached(
            "overview", f, officer, lambda: overview.build_overview(self.session, f, officer)
        )

    def pipeline(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached(
            "pipeline", f, officer, lambda: overview.build_pipeline(self.session, f, officer)
        )

    def timeseries(
        self,
        f: DashboardFilters,
        officer: CurrentOfficer,
        *,
        metric: str,
        interval: str | None,
    ) -> Section:
        return self._cached(
            "timeseries",
            f,
            officer,
            lambda: charts.build_timeseries(
                self.session, f, officer, metric=metric, interval=interval
            ),
            metric,
            interval,
        )

    def distribution(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached(
            "distribution",
            f,
            officer,
            lambda: charts.build_distribution(self.session, f, officer),
        )

    def alerts(
        self, f: DashboardFilters, officer: CurrentOfficer, *, as_of: date | None = None
    ) -> Section:
        return self._cached(
            "alerts",
            f,
            officer,
            lambda: alerts.build_alerts(self.session, f, officer, as_of=as_of),
            as_of,
        )

    def activity(
        self,
        f: DashboardFilters,
        officer: CurrentOfficer,
        *,
        module: int | None = None,
        limit: int = config.ACTIVITY_LIMIT,
    ) -> Section:
        return self._cached(
            "activity",
            f,
            officer,
            lambda: activity.build_activity(self.session, f, module=module, limit=limit),
            module,
            limit,
        )

    def map(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached("map", f, officer, lambda: mapview.build_map(self.session, f, officer))

    def officer_overview(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached(
            "officers", f, officer, lambda: officers.build_officer_overview(self.session, f)
        )

    def onboarding(self, f: DashboardFilters, officer: CurrentOfficer) -> Section:
        return self._cached(
            "onboarding",
            f,
            officer,
            lambda: officers.build_onboarding(self.session, f, officer),
        )


__all__ = [
    "DashboardFilters",
    "DashboardService",
    "DateRange",
    "Section",
    "activity",
    "alerts",
    "cache",
    "charts",
    "config",
    "default_scope",
    "filters",
    "get_meta",
    "links",
    "mapview",
    "officers",
    "overview",
    "sources",
    "today",
]
