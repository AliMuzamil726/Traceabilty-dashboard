"""The attention panel: eight rules over the data the other modules own.

Each rule has a count, a severity, a link into the module that can fix it and a few
named records so an officer can act without hunting for them. The thresholds are not
written here: they all come from :mod:`module_1.config`, which is what Settings will
take over.

Severity is wheat ("needs attention") for everything except the rules listed in
``config.CRITICAL_ALERTS``, which are the only ones drawn in the error red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from module_1 import config, config_api
from module_1.services import links, sources
from module_1.services.filters import DashboardFilters, today
from module_3 import public_api as fieldbooks
from module_4 import public_api as radar


@dataclass(frozen=True)
class Sample:
    """One named record under an alert."""

    label: str
    sublabel: str | None
    link: links.Link

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "sublabel": self.sublabel, "link": self.link.as_dict()}


@dataclass(frozen=True)
class Alert:
    key: str
    title: str
    description: str
    count: int
    severity: str
    link: links.Link
    samples: tuple[Sample, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "count": self.count,
            "severity": self.severity,
            "link": self.link.as_dict(),
            "samples": [s.as_dict() for s in self.samples],
        }


def _severity(key: str, *, critical: bool | None = None) -> str:
    if critical is None:
        critical = key in config.CRITICAL_ALERTS
    return config.SEVERITY_CRITICAL if critical else config.SEVERITY_ATTENTION


def _days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def build_alerts(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Every rule, in a fixed order, whether or not it has anything to report."""
    now = as_of or today()
    rows = sources.readiness_rows(session, f, officer)
    alerts = [
        _ready_without_pickup(f, rows, now),
        _overdue_fields(session, f, rows, now),
        _dispatch_overdue(session, f, officer, now),
        _weight_variance(session, f, officer),
        _idle_heaps(session, f, now),
        _licence_expiry(session, f, rows, now),
        _stale_drafts(session, f, rows, now),
        _farmers_without_field(session, f, officer),
    ]
    return {
        "crop": f.crop,
        "season_year": f.season_year,
        "scope": f.scope,
        "total": sum(a.count for a in alerts),
        "critical": sum(a.count for a in alerts if a.severity == config.SEVERITY_CRITICAL),
        "alerts": [a.as_dict() for a in alerts],
        "generated_at": datetime.now(UTC),
    }


# ------------------------------------------------------------------------ the rules


def _field_sample(row: radar.ReadinessRowDTO, sublabel: str) -> Sample:
    return Sample(
        label=row.field_code,
        sublabel=f"{row.farmer_name}, {sublabel}",
        link=links.farmer(row.farmer_id),
    )


def _ready_without_pickup(
    f: DashboardFilters, rows: list[radar.ReadinessRowDTO], now: date
) -> Alert:
    """Ready for longer than the threshold and nobody has asked for a pickup."""
    limit = config_api.ready_without_pickup_days()
    hits = [
        r
        for r in rows
        if r.status == radar.STATUS_READY
        and r.pickup_state == radar.PICKUP_NOT_REQUESTED
        and r.ready_since is not None
        and (now - r.ready_since).days > limit
    ]
    hits.sort(key=lambda r: r.ready_since or now)
    return Alert(
        key=config.ALERT_READY_WITHOUT_PICKUP,
        title="Ready with no pickup request",
        description=(
            f"Fields ready for more than {_days(limit)} that nobody has requested a pickup for."
        ),
        count=len(hits),
        severity=_severity(config.ALERT_READY_WITHOUT_PICKUP),
        link=links.radar(f, status=radar.STATUS_READY, pickup=radar.PICKUP_NOT_REQUESTED),
        samples=tuple(
            _field_sample(
                r,
                f"ready {_days((now - r.ready_since).days)} ago",  # type: ignore[operator]
            )
            for r in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _overdue_fields(
    session: Session, f: DashboardFilters, rows: list[radar.ReadinessRowDTO], now: date
) -> Alert:
    """Past the end of the harvest window and not harvested: the crop is at risk.

    The radar expresses the same set as ready fields whose expected ready date is on or
    before the cutoff below, which is exactly "days after sowing past the window end"
    (D-103), so the link lands on the same fields that are counted here.
    """
    hits = sorted(
        (r for r in rows if r.overdue),
        key=lambda r: r.expected_ready or now,
    )
    cutoffs = {
        crop: now - timedelta(days=clock.window_end_day - clock.ready_day + 1)
        for crop, clock in fieldbooks.get_crop_clocks(session).items()
        if crop in f.crops
    }
    return Alert(
        key=config.ALERT_OVERDUE_FIELDS,
        title="Overdue fields",
        description="Fields past the end of their harvest window that are not harvested.",
        count=len(hits),
        severity=_severity(config.ALERT_OVERDUE_FIELDS),
        link=links.radar(f, status=radar.STATUS_READY, ready_to=cutoffs.get(f.primary_crop)),
        samples=tuple(
            _field_sample(r, r.next_milestone.lower()) for r in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _dispatch_overdue(
    session: Session, f: DashboardFilters, officer: CurrentOfficer, now: date
) -> Alert:
    """Scheduled for a date that has passed and still at the farm."""
    cutoff = now - timedelta(days=config_api.dispatch_grace_days() + 1)
    count, hits = sources.delivery_alert(
        session, f, officer, statuses=("scheduled",), date_to=cutoff
    )
    hits.sort(key=lambda d: d.scheduled_date)
    return Alert(
        key=config.ALERT_DISPATCH_OVERDUE,
        title="Scheduled but not dispatched",
        description="Deliveries whose scheduled date has passed without a dispatch.",
        count=count,
        severity=_severity(config.ALERT_DISPATCH_OVERDUE),
        link=links.deliveries(f, status="scheduled", date_to=cutoff),
        samples=tuple(
            Sample(
                label=d.delivery_no,
                sublabel=f"{d.field_code}, due {d.scheduled_date.isoformat()}",
                link=links.delivery(d.id, f),
            )
            for d in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _weight_variance(session: Session, f: DashboardFilters, officer: CurrentOfficer) -> Alert:
    """Weighbridge weight far enough from the field weight to be flagged."""
    count, hits = sources.delivery_alert(
        session, f, officer, statuses=("delivered",), variance_level="flag"
    )
    hits.sort(key=lambda d: abs(d.variance_pct or 0), reverse=True)
    return Alert(
        key=config.ALERT_WEIGHT_VARIANCE,
        title="Flagged weight variance",
        description=(
            "Delivered loads whose weighbridge weight is far enough from the field "
            "weight to need a note."
        ),
        count=count,
        severity=_severity(config.ALERT_WEIGHT_VARIANCE),
        link=links.deliveries(f, status="delivered"),
        samples=tuple(
            Sample(
                label=d.delivery_no,
                sublabel=f"{d.field_code}, {d.variance_pct:+.2f}%"
                if d.variance_pct is not None
                else d.field_code,
                link=links.delivery(d.id, f),
            )
            for d in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _idle_heaps(session: Session, f: DashboardFilters, now: date) -> Alert:
    """Open, with nothing added and no bale made for the threshold.

    Heaps are not scoped to an officer: a heap mixes many farmers' crop, so this rule
    reports the whole programme's heaps whatever the scope (D-101).
    """
    limit = config_api.heap_idle_days()
    hits = [
        h
        for h in sources.heap_rows(session, f)
        if h.status == "open" and (now - h.last_activity_at.astimezone(UTC).date()).days >= limit
    ]
    hits.sort(key=lambda h: h.last_activity_at)
    return Alert(
        key=config.ALERT_IDLE_HEAPS,
        title="Idle heaps and batches",
        description=f"Open heaps and batches with no activity for {_days(limit)} or more.",
        count=len(hits),
        severity=_severity(config.ALERT_IDLE_HEAPS),
        link=links.heaps(f, status="open"),
        samples=tuple(
            Sample(
                label=h.heap_id,
                sublabel=(
                    f"{_days((now - h.last_activity_at.astimezone(UTC).date()).days)} "
                    "since the last change"
                ),
                link=links.heap(h.heap_id, crop=h.crop, site_id=h.site_id),
            )
            for h in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _licence_expiry(
    session: Session, f: DashboardFilters, rows: list[radar.ReadinessRowDTO], now: date
) -> Alert:
    """Hemp growing licences that have run out or are about to.

    The expiry date lives on the hemp fieldbook's first step, so a field with no
    fieldbook yet cannot be checked and is not counted. The alert turns critical as
    soon as one licence has actually expired.
    """
    window = config_api.licence_expiry_warning_days()
    mine = {r.field_id for r in rows}
    hits = [
        row
        for row in sources.licence_expiries(session, f)
        if row.expiry is not None and row.field_id in mine and (row.expiry - now).days <= window
    ]
    hits.sort(key=lambda r: r.expiry or now)
    expired = [r for r in hits if r.expiry is not None and r.expiry < now]
    return Alert(
        key=config.ALERT_LICENCE_EXPIRY,
        title="Hemp licences expiring",
        description=(f"Home Office licences that have expired or expire within {_days(window)}."),
        count=len(hits),
        severity=_severity(config.ALERT_LICENCE_EXPIRY, critical=bool(expired)),
        link=links.fieldbook_list(),
        samples=tuple(
            Sample(
                label=r.field_code,
                sublabel=(
                    f"expired {r.expiry.isoformat()}"
                    if r.expiry is not None and r.expiry < now
                    else f"expires {r.expiry.isoformat() if r.expiry else ''}"
                ),
                link=links.fieldbook(r.fieldbook_id),
            )
            for r in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _stale_drafts(
    session: Session, f: DashboardFilters, rows: list[radar.ReadinessRowDTO], now: date
) -> Alert:
    """Drafts nobody has touched for the threshold."""
    limit = config_api.draft_fieldbook_idle_days()
    cutoff = datetime.combine(now - timedelta(days=limit), datetime.min.time(), tzinfo=UTC)
    mine = {r.field_id for r in rows}
    hits = [
        d for d in sources.stale_drafts(session, f, updated_before=cutoff) if d.field_id in mine
    ]
    hits.sort(key=lambda d: d.updated_at)
    return Alert(
        key=config.ALERT_STALE_DRAFTS,
        title="Forgotten fieldbook drafts",
        description=f"Draft fieldbooks nobody has changed for {_days(limit)} or more.",
        count=len(hits),
        severity=_severity(config.ALERT_STALE_DRAFTS),
        link=links.fieldbook_list(),
        samples=tuple(
            Sample(
                label=d.field_code,
                sublabel=f"{d.steps_complete} of {d.steps_total} steps done",
                link=links.fieldbook(d.fieldbook_id),
            )
            for d in hits[: config.ALERT_SAMPLE_LIMIT]
        ),
    )


def _farmers_without_field(session: Session, f: DashboardFilters, officer: CurrentOfficer) -> Alert:
    """Registered, but nothing downstream can use them until a field is mapped."""
    count, samples = sources.farmers_without_field(session, f, officer)
    return Alert(
        key=config.ALERT_FARMERS_WITHOUT_FIELD,
        title="Farmers with no mapped field",
        description=(
            "Registered farmers whose boundary has not been drawn, so Fieldbook cannot start."
        ),
        count=count,
        severity=_severity(config.ALERT_FARMERS_WITHOUT_FIELD),
        link=links.register(f),
        samples=tuple(
            Sample(
                label=str(s.sawie_id),
                sublabel=s.name,
                link=links.farmer(s.id),
            )
            for s in samples
        ),
    )


__all__ = ["Alert", "Sample", "build_alerts"]
