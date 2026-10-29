"""HTTP routes for Module 1 (Dashboard / Home), mounted at ``/api/v1/dashboard``.

Every section of the screen is its own endpoint, so the page can load them in
parallel, show a skeleton for each and retry one that failed without reloading the
rest. They all take the same filter parameters, which is what keeps the pipeline, the
KPIs, the charts, the map and the alerts describing the same slice of the programme.

The dashboard only reads. There is no POST, PUT or DELETE here, and it owns no tables.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core import permissions
from core.deps import CurrentOfficer, get_current_officer, get_db
from module_1 import config, meta, services
from module_1.schemas import (
    ActivityOut,
    AlertsOut,
    DistributionOut,
    OfficerOverviewOut,
    OnboardingOut,
    OverviewOut,
    PipelineOut,
    TimeseriesOut,
)
from module_1.services import DashboardFilters, DashboardService
from module_1.services.charts import INTERVALS, METRICS
from shared.schemas import ModuleMetaOut

router = APIRouter(prefix=meta.API_PREFIX, tags=[f"module_{meta.NUMBER}"])

CROP_PATTERN = r"^(all|cotton|hemp)$"
RANGE_PATTERN = r"^(7d|30d|season|custom)$"
SCOPE_PATTERN = r"^(mine|all)$"


def dashboard_filters(
    officer: CurrentOfficer = Depends(get_current_officer),
    crop: str = Query(config.CROP_ALL, pattern=CROP_PATTERN),
    season_year: int | None = Query(None, ge=2000, le=2100),
    range_: str = Query(config.RANGE_30D, alias="range", pattern=RANGE_PATTERN),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    scope: str | None = Query(None, pattern=SCOPE_PATTERN),
) -> DashboardFilters:
    """The header's controls. Officers default to their own work, administrators to all."""
    return DashboardFilters(
        crop=crop,
        season_year=season_year or services.today().year,
        range_key=range_,
        date_from=date_from,
        date_to=date_to,
        scope=scope or services.default_scope(officer),
    ).validate()


def get_dashboard(session: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(session)


# --------------------------------------------------------------------------- routes


@router.get("/meta", response_model=ModuleMetaOut, summary="Module identity and build status")
def get_meta() -> ModuleMetaOut:
    return services.get_meta()


@router.get("/overview", response_model=OverviewOut, summary="Greeting block and the KPI row")
def overview(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> OverviewOut:
    return OverviewOut.model_validate(dashboard.overview(f, officer))


@router.get(
    "/pipeline",
    response_model=PipelineOut,
    summary="The seven pipeline stages with counts and conversion",
)
def pipeline(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> PipelineOut:
    return PipelineOut.model_validate(dashboard.pipeline(f, officer))


@router.get(
    "/timeseries",
    response_model=TimeseriesOut,
    summary="One chart's series over the selected range",
)
def timeseries(
    metric: str = Query(METRICS[0], description=f"One of {', '.join(METRICS)}"),
    interval: str | None = Query(None, description=f"One of {', '.join(INTERVALS)}"),
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> TimeseriesOut:
    return TimeseriesOut.model_validate(
        dashboard.timeseries(f, officer, metric=metric, interval=interval)
    )


@router.get(
    "/distribution",
    response_model=DistributionOut,
    summary="Readiness, fieldbook funnel, heap utilisation and the top regions",
)
def distribution(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> DistributionOut:
    return DistributionOut.model_validate(dashboard.distribution(f, officer))


@router.get("/alerts", response_model=AlertsOut, summary="The attention panel's rules")
def alerts(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> AlertsOut:
    return AlertsOut.model_validate(dashboard.alerts(f, officer))


@router.get("/activity", response_model=ActivityOut, summary="Recent audited changes")
def activity(
    module: int | None = Query(None, ge=1, le=9, description="Only this module's entries"),
    limit: int = Query(config.ACTIVITY_LIMIT, ge=1, le=config.ACTIVITY_MAX_LIMIT),
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> ActivityOut:
    return ActivityOut.model_validate(dashboard.activity(f, officer, module=module, limit=limit))


@router.get("/map", summary="GeoJSON FeatureCollection of the filtered fields")
def map_features(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> dict[str, object]:
    return dashboard.map(f, officer)


@router.get(
    "/officers",
    response_model=OfficerOverviewOut,
    summary="Per officer registrations and submitted fieldbooks (administrators and staff)",
)
def officer_overview(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> OfficerOverviewOut:
    permissions.require(officer, "dashboard.view_all")
    return OfficerOverviewOut.model_validate(dashboard.officer_overview(f, officer))


@router.get(
    "/onboarding",
    response_model=OnboardingOut,
    summary="The Get started checklist and whether the programme is still empty",
)
def onboarding(
    f: DashboardFilters = Depends(dashboard_filters),
    officer: CurrentOfficer = Depends(get_current_officer),
    dashboard: DashboardService = Depends(get_dashboard),
) -> OnboardingOut:
    return OnboardingOut.model_validate(dashboard.onboarding(f, officer))
