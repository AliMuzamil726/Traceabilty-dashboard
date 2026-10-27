"""Crop clock boundaries: cotton 120/135/200 and hemp 80/95/125 days after sowing."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from module_3.services import clock as c

COTTON = c.Clock("cotton", 120, 135, 200)
HEMP = c.Clock("hemp", 80, 95, 125)
TODAY = date(2026, 10, 1)


def at(clock: c.Clock, das: int) -> c.CropStatus:
    return c.crop_status(clock, TODAY - timedelta(days=das), TODAY)


@pytest.mark.parametrize(
    ("das", "status", "overdue"),
    [
        (119, c.GROWING, False),
        (120, c.APPROACHING, False),
        (134, c.APPROACHING, False),
        (135, c.READY, False),
        (199, c.READY, False),
        (200, c.READY, False),
        (201, c.READY, True),
    ],
)
def test_cotton_boundaries(das: int, status: str, overdue: bool) -> None:
    s = at(COTTON, das)
    assert (s.status, s.overdue, s.days_after_sowing) == (status, overdue, das)


@pytest.mark.parametrize(
    ("das", "status", "overdue"),
    [
        (79, c.GROWING, False),
        (80, c.APPROACHING, False),
        (95, c.READY, False),
        (125, c.READY, False),
        (126, c.READY, True),
    ],
)
def test_hemp_boundaries(das: int, status: str, overdue: bool) -> None:
    s = at(HEMP, das)
    assert (s.status, s.overdue) == (status, overdue)


def test_no_sowing_date_and_harvested() -> None:
    assert c.crop_status(COTTON, None, TODAY).status == c.NO_SOWING
    assert (
        c.crop_status(COTTON, TODAY - timedelta(days=150), TODAY, harvested=True).status
        == c.HARVESTED
    )


def test_milestone_text() -> None:
    assert at(COTTON, 119).next_milestone == "Approaching harvest in 1 day."
    assert at(COTTON, 200).next_milestone == "The harvest window closes today."


def test_the_seeded_clocks_match(client: object) -> None:
    from fastapi.testclient import TestClient

    assert isinstance(client, TestClient)
    assert c.DEFAULT_CLOCKS == {"cotton": (120, 135, 200), "hemp": (80, 95, 125)}
