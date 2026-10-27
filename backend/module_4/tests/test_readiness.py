"""The readiness rules at every boundary, for both crops."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from module_3 import public_api as fieldbooks
from module_4.services import readiness as rd

TODAY = date(2026, 10, 1)


_CLOCKS: dict[str, rd.ClockDays] = {}


@pytest.fixture(autouse=True)
def _clocks(session: Session) -> None:
    """The clock days come from Module 3's public API, never from this module."""
    for crop, c in fieldbooks.get_crop_clocks(session).items():
        _CLOCKS[crop] = rd.ClockDays(c.approach_day, c.ready_day, c.window_end_day)


def clock(crop: str) -> rd.ClockDays:
    return _CLOCKS[crop]


def at(crop: str, das: int, **kw: bool) -> rd.Readiness:
    return rd.assess(clock(crop), TODAY - timedelta(days=das), TODAY, **kw)


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_boundaries(crop: str) -> None:
    c = clock(crop)
    expected = [
        (c.approach_day - 1, rd.GROWING, False),
        (c.approach_day, rd.APPROACHING, False),
        (c.ready_day - 1, rd.APPROACHING, False),
        (c.ready_day, rd.READY, False),
        (c.window_end_day, rd.READY, False),
        (c.window_end_day + 1, rd.READY, True),
    ]
    for das, bucket, overdue in expected:
        r = at(crop, das)
        assert (r.bucket, r.overdue, r.days_after_sowing) == (bucket, overdue, das), das


def test_the_clock_days_are_the_seeded_ones() -> None:
    assert clock("cotton") == rd.ClockDays(120, 135, 200)
    assert clock("hemp") == rd.ClockDays(80, 95, 125)


def test_no_sowing_date() -> None:
    r = rd.assess(clock("cotton"), None, TODAY)
    assert (r.bucket, r.days_after_sowing, r.expected_ready, r.overdue) == (
        rd.NO_SOWING,
        None,
        None,
        False,
    )
    assert r.next_milestone == "Record the sowing date in Fieldbook"


def test_harvested_beats_the_clock_and_clears_overdue() -> None:
    r = at("cotton", 250, harvested=True)
    assert (r.bucket, r.overdue, r.next_milestone) == (rd.HARVESTED, False, "Harvested")
    assert at("cotton", 30, harvested=True).bucket == rd.HARVESTED


def test_the_ready_flag_beats_everything() -> None:
    assert at("cotton", 10, ready_flag=True).bucket == rd.READY
    assert at("cotton", 150, harvested=True, ready_flag=True).bucket == rd.READY
    assert rd.assess(clock("hemp"), None, TODAY, ready_flag=True).bucket == rd.READY


def test_expected_ready_and_milestones() -> None:
    r = at("cotton", 123)
    assert r.expected_ready == TODAY - timedelta(days=123) + timedelta(days=135)
    assert r.next_milestone == "Ready in 12 days"
    assert at("cotton", 209).next_milestone == "Overdue by 9 days"
    assert at("cotton", 134).next_milestone == "Ready in 1 day"
    assert at("cotton", 200).next_milestone == "Harvest window closes today"
    assert at("hemp", 100).next_milestone == "Harvest window closes in 25 days"


def test_progress_runs_from_sowing_to_window_end() -> None:
    assert at("cotton", 0).progress == 0
    assert at("cotton", 100).progress == pytest.approx(0.5)
    assert at("cotton", 400).progress == 1
