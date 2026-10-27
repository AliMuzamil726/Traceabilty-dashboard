"""The dashboard's charts: a time series and four distributions.

Time buckets are worked out here rather than in SQL, because truncating a timestamp to
a day, week or month is written differently on SQLite and on Postgres and the dashboard
must read the same on both (D-097). The owning module returns the timestamps inside the
range, which is bounded, and the grouping happens once in Python.

A week starts on Monday, in UTC, like the rest of the product.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from core.deps import CurrentOfficer
from core.errors import ValidationAppError
from module_1 import config
from module_1.services import links, sources
from module_1.services.filters import DashboardFilters, DateRange
from module_4 import public_api as radar

INTERVAL_DAY = "day"
INTERVAL_WEEK = "week"
INTERVAL_MONTH = "month"
INTERVALS = (INTERVAL_DAY, INTERVAL_WEEK, INTERVAL_MONTH)

METRIC_REGISTRATIONS = "registrations"
METRIC_DELIVERIES = "deliveries"
METRICS = (METRIC_REGISTRATIONS, METRIC_DELIVERIES)


# --------------------------------------------------------------------- bucketing


def period_start(day: date, interval: str) -> date:
    if interval == INTERVAL_WEEK:
        return day - timedelta(days=day.weekday())
    if interval == INTERVAL_MONTH:
        return day.replace(day=1)
    return day


def next_period(start: date, interval: str) -> date:
    if interval == INTERVAL_WEEK:
        return start + timedelta(days=7)
    if interval == INTERVAL_MONTH:
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def periods(window: DateRange, interval: str) -> list[date]:
    """Every bucket the range touches, including the empty ones, oldest first."""
    out: list[date] = []
    cursor = period_start(window.start, interval)
    while cursor <= window.end and len(out) < config.TIMESERIES_MAX_POINTS:
        out.append(cursor)
        cursor = next_period(cursor, interval)
    return out


def default_interval(window: DateRange) -> str:
    """Days for a short range, weeks for a season, months for anything longer."""
    if window.days <= 31:
        return INTERVAL_DAY
    if window.days <= 370:
        return INTERVAL_WEEK
    return INTERVAL_MONTH


def _bucket_counts(times: Iterable[datetime], window: DateRange, interval: str) -> dict[date, int]:
    counts = dict.fromkeys(periods(window, interval), 0)
    for moment in times:
        key = period_start(moment.astimezone(UTC).date(), interval)
        if key in counts:
            counts[key] += 1
    return counts


# ------------------------------------------------------------------- time series


def build_timeseries(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    *,
    metric: str,
    interval: str | None = None,
) -> dict[str, Any]:
    """One chart's worth of series over the range.

    A metric is a chart, not a single line: ``registrations`` returns farmers and
    fields together, because they are read side by side, and ``deliveries`` returns the
    delivered quantity with the average moisture of the same loads.
    """
    if metric not in METRICS:
        raise ValidationAppError(
            "Metric is registrations or deliveries.", code="dashboard_metric_invalid"
        )
    if interval is not None and interval not in INTERVALS:
        raise ValidationAppError(
            "Interval is day, week or month.", code="dashboard_interval_invalid"
        )
    window = f.range()
    step = interval or default_interval(window)
    buckets = periods(window, step)

    if metric == METRIC_REGISTRATIONS:
        series = _registration_series(session, f, officer, window, step, buckets)
    else:
        series = _delivery_series(session, f, officer, window, step, buckets)

    return {
        "metric": metric,
        "interval": step,
        "crop": f.crop,
        "season_year": f.season_year,
        "scope": f.scope,
        "from": window.start,
        "to": window.end,
        "truncated": len(buckets) >= config.TIMESERIES_MAX_POINTS,
        "series": series,
        "generated_at": datetime.now(UTC),
    }


def _registration_series(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    window: DateRange,
    step: str,
    buckets: list[date],
) -> list[dict[str, Any]]:
    farmers: dict[date, int] = dict.fromkeys(buckets, 0)
    fields: dict[date, int] = dict.fromkeys(buckets, 0)
    for crop in f.crops:
        for key, count in _bucket_counts(
            sources.registration_times(session, f, officer, crop=crop, window=window),
            window,
            step,
        ).items():
            farmers[key] += count
        for key, count in _bucket_counts(
            sources.field_mapped_times(session, f, officer, crop=crop, window=window),
            window,
            step,
        ).items():
            fields[key] += count
    return [
        {
            "key": "farmers",
            "label": "Farmers registered",
            "unit": "farmers",
            "total": sum(farmers.values()),
            "points": [{"period_start": d, "value": farmers[d]} for d in buckets],
        },
        {
            "key": "fields",
            "label": "Fields mapped",
            "unit": "fields",
            "total": sum(fields.values()),
            "points": [{"period_start": d, "value": fields[d]} for d in buckets],
        },
    ]


def _delivery_series(
    session: Session,
    f: DashboardFilters,
    officer: CurrentOfficer,
    window: DateRange,
    step: str,
    buckets: list[date],
) -> list[dict[str, Any]]:
    rows = sources.delivered_rows(session, f, officer, window)
    kg: dict[date, float] = dict.fromkeys(buckets, 0.0)
    moisture_sum: dict[date, float] = dict.fromkeys(buckets, 0.0)
    moisture_n: dict[date, int] = dict.fromkeys(buckets, 0)
    for moment, weight, moisture in rows:
        key = period_start(moment.astimezone(UTC).date(), step)
        if key not in kg:
            continue
        kg[key] += weight
        if moisture is not None:
            moisture_sum[key] += moisture
            moisture_n[key] += 1
    return [
        {
            "key": "delivered_kg",
            "label": "Delivered",
            "unit": "kg",
            "total": round(sum(kg.values()), 1),
            "points": [{"period_start": d, "value": round(kg[d], 1)} for d in buckets],
        },
        {
            "key": "average_moisture_pct",
            "label": "Average moisture",
            "unit": "%",
            "total": None,
            "points": [
                {
                    "period_start": d,
                    "value": (
                        None if moisture_n[d] == 0 else round(moisture_sum[d] / moisture_n[d], 2)
                    ),
                }
                for d in buckets
            ],
        },
    ]


# ------------------------------------------------------------------ distributions


def build_distribution(
    session: Session, f: DashboardFilters, officer: CurrentOfficer
) -> dict[str, Any]:
    """Readiness buckets, the fieldbook funnel, heap utilisation and the top regions.

    The funnel and the top regions describe one crop at a time: the steps of the form
    and the kind of region both differ between cotton and hemp. With every crop
    selected, the crop with the most mapped fields is used and named in the response
    (``focus_crop``), so the chart can say which programme it is showing (D-102).
    """
    rows = sources.readiness_rows(session, f, officer)
    focus = _focus_crop(f, rows)
    unit = f.area_unit(focus)

    buckets: dict[str, dict[str, Any]] = {
        status: {
            "bucket": status,
            "label": radar.STATUS_LABELS[status],
            "fields": 0,
            "area": 0.0,
            "estimated_kg": 0.0,
        }
        for status in radar.STATUSES
    }
    for row in rows:
        entry = buckets[row.status]
        entry["fields"] += 1
        entry["area"] += row.area_acre if f.area_unit(row.crop) == "acre" else row.area_ha
        entry["estimated_kg"] += row.estimated_kg or 0.0
    for entry in buckets.values():
        entry["area"] = round(entry["area"], 2)
        entry["estimated_kg"] = round(entry["estimated_kg"], 1)

    steps = sources.step_completion(session, f, focus)
    books = sum(1 for r in rows if r.crop == focus and r.fieldbook_id is not None)
    funnel = [
        {
            "step_key": step.step_key,
            "title": step.title,
            "order": step.order,
            "complete": step.complete,
            "pct": round(step.complete / books * 100, 1) if books else 0.0,
        }
        for step in steps
    ]

    heaps = sorted(sources.heap_rows(session, f), key=lambda h: -float(h.input_kg))
    utilisation = [
        {
            "heap_id": h.heap_id,
            "kind": h.kind,
            "crop": h.crop,
            "status": h.status,
            "input_kg": float(h.input_kg),
            "expected_output_kg": float(h.expected_output_kg),
            "bales_made": h.bales_made,
            "max_bales": h.max_bales,
            "link": links.heap(h.heap_id, crop=h.crop, site_id=h.site_id).as_dict(),
        }
        for h in heaps[: config.HEAP_CHART_LIMIT]
    ]

    regions = sources.region_areas(session, f, officer, crop=focus)
    top_regions = [
        {
            "region": r.region,
            "fields": r.fields,
            "area": r.area_acre if unit == "acre" else r.area_ha,
        }
        for r in regions
    ]

    return {
        "crop": f.crop,
        "focus_crop": focus,
        "season_year": f.season_year,
        "scope": f.scope,
        "area_unit": unit,
        "region_label": "District" if focus == "cotton" else "County",
        "readiness": [buckets[s] for s in radar.STATUSES],
        "fieldbook_funnel": funnel,
        "fieldbooks_started": books,
        "heap_utilisation": utilisation,
        "top_regions": top_regions,
        "generated_at": datetime.now(UTC),
    }


def _focus_crop(f: DashboardFilters, rows: list[radar.ReadinessRowDTO]) -> str:
    if f.crop != config.CROP_ALL:
        return f.crop
    counts = {crop: sum(1 for r in rows if r.crop == crop) for crop in f.crops}
    best = max(counts.values(), default=0)
    # Ties and an empty database both fall back to the product's first crop.
    return next((c for c in f.crops if counts[c] == best and best > 0), f.primary_crop)


__all__ = [
    "INTERVALS",
    "METRICS",
    "build_distribution",
    "build_timeseries",
    "default_interval",
    "period_start",
    "periods",
]
