"""The filter set every dashboard section is read with, and the time range it means.

One frozen :class:`DashboardFilters` is built from the query string by the router and
passed to every section, so the pipeline, the KPIs, the charts, the map, the alerts and
the activity feed always describe the same slice of the programme.

Dates and times: a range is whole days in UTC. ``from`` and ``to`` are dates, and they
become the first and last instant of those days, so a record created at 23:50 UTC on
the last day is inside the range and one at 00:05 UTC the next day is not (D-100).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from core.deps import CurrentOfficer
from core.errors import ValidationAppError
from module_1 import config


def today() -> date:
    return datetime.now(UTC).date()


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def end_of(day: date) -> datetime:
    return datetime.combine(day, time.max, tzinfo=UTC)


@dataclass(frozen=True)
class DateRange:
    key: str
    start: date
    end: date

    @property
    def since(self) -> datetime:
        return start_of(self.start)

    @property
    def until(self) -> datetime:
        return end_of(self.end)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class DashboardFilters:
    """What the header's controls select. ``crop`` is ``all``, ``cotton`` or ``hemp``."""

    crop: str = config.CROP_ALL
    season_year: int = field(default_factory=lambda: today().year)
    range_key: str = config.RANGE_30D
    date_from: date | None = None
    date_to: date | None = None
    scope: str = config.SCOPE_MINE

    def validate(self) -> DashboardFilters:
        if self.crop not in (config.CROP_ALL, *config.CROPS):
            raise ValidationAppError(
                "Choose all crops, cotton or hemp.", code="dashboard_crop_invalid"
            )
        if self.range_key not in config.RANGES:
            raise ValidationAppError(
                "Range is 7d, 30d, season or custom.", code="dashboard_range_invalid"
            )
        if self.scope not in (config.SCOPE_MINE, config.SCOPE_ALL):
            raise ValidationAppError("Scope is mine or all.", code="dashboard_scope_invalid")
        if self.range_key == config.RANGE_CUSTOM:
            if self.date_from is None or self.date_to is None:
                raise ValidationAppError(
                    "A custom range needs both from and to.", code="dashboard_range_incomplete"
                )
            if self.date_from > self.date_to:
                raise ValidationAppError(
                    "The range starts after it ends.", code="dashboard_range_invalid"
                )
            if (self.date_to - self.date_from).days + 1 > config.MAX_CUSTOM_RANGE_DAYS:
                raise ValidationAppError(
                    "A custom range covers at most two years.", code="dashboard_range_too_long"
                )
        return self

    # ----------------------------------------------------------------- derived view

    @property
    def crops(self) -> tuple[str, ...]:
        """The crop programmes this filter covers, in the product's own order."""
        return config.CROPS if self.crop == config.CROP_ALL else (self.crop,)

    @property
    def primary_crop(self) -> str:
        """The crop whose units and wording a single-crop section uses."""
        return config.CROPS[0] if self.crop == config.CROP_ALL else self.crop

    def area_unit(self, crop: str | None = None) -> str:
        return config.AREA_UNIT[crop or self.primary_crop]

    def mass_unit(self, crop: str | None = None) -> str:
        return config.MASS_UNIT[crop or self.primary_crop]

    def range(self, *, as_of: date | None = None) -> DateRange:
        """The range as whole days, never reaching past today."""
        now = as_of or today()
        if self.range_key == config.RANGE_CUSTOM:
            # Both are present: validate() refuses a custom range without them.
            assert self.date_from is not None
            assert self.date_to is not None
            return DateRange(self.range_key, self.date_from, self.date_to)
        if self.range_key == config.RANGE_SEASON:
            start = date(self.season_year, 1, 1)
            end = date(self.season_year, 12, 31)
            return DateRange(self.range_key, start, min(end, now) if now >= start else end)
        days = config.RANGE_DAYS[self.range_key]
        return DateRange(self.range_key, now - timedelta(days=days - 1), now)

    def officer_filter(self, officer: CurrentOfficer) -> str | None:
        """The officer whose own work to show, or None for the whole programme.

        Scope is a choice, not a permission: the dashboard only reads, and Harvest
        Radar already lets any officer see the whole programme read only.
        """
        return officer.id if self.scope == config.SCOPE_MINE else None

    def key(self, officer: CurrentOfficer, *, as_of: date | None = None) -> tuple[Any, ...]:
        """Cache key: the filters, the acting officer and the day."""
        day = as_of or today()
        return (day, officer.id, officer.sees_all, *sorted(asdict(self).items()))


def default_scope(officer: CurrentOfficer) -> str:
    """Officers land on their own work, administrators on the whole programme."""
    return config.SCOPE_ALL if officer.sees_all else config.SCOPE_MINE


__all__ = [
    "DashboardFilters",
    "DateRange",
    "default_scope",
    "end_of",
    "start_of",
    "today",
]
