"""Module 3's public API, as other modules will call it."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from module_3 import public_api as api
from module_3.tests.conftest import FB, SOWING_DAYS_AGO, cotton_steps, hemp_steps

Farm = dict[str, Any]


@pytest.fixture
def db(client: TestClient) -> Iterator[Session]:
    """A read session that ends its transaction after each call, so API writes are not blocked."""
    s = client.app.state.db.session_factory()  # type: ignore[attr-defined]

    try:
        yield s
    finally:
        s.close()


def q(db: Session, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(db, *args, **kwargs)
    finally:
        db.rollback()


def test_cotton_book_through_the_public_api(
    client: TestClient,
    db: Session,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    fill: Callable[..., Farm],
) -> None:
    farm = make_farm("cotton")
    fid = farm["field"]["id"]
    year = date.today().year
    assert q(db, api.has_fieldbook, fid, year) is False
    assert q(db, api.get_fieldbook_summary, fid, year) is None
    book = open_book(farm)
    fill(book, farm["headers"], cotton_steps())
    summary = q(db, api.get_fieldbook_summary, fid, year)
    assert summary is not None
    assert summary.steps_complete == summary.steps_total == 11
    assert q(db, api.get_sowing_date, fid, year) == date.today() - timedelta(days=SOWING_DAYS_AGO)
    assert q(db, api.get_crop_status, fid, year).status == "harvested"  # type: ignore[union-attr]
    assert q(db, api.get_crop_clock, "cotton").ready_day == 135  # type: ignore[union-attr]
    ready = q(db, api.list_ready_for_pickup, crop="cotton")
    assert [(r.field_id, r.picking_number) for r in ready] == [(fid, "1st")]
    assert q(db, api.get_estimated_yield, fid, year).estimated_kg == 12 * 9.5 * 40  # type: ignore[union-attr]
    assert len(q(db, api.get_activity_timeline, fid, year)) >= 11
    assert q(db, api.is_submitted, fid) is False
    client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
    assert q(db, api.is_submitted, fid) is True


def test_hemp_yield_and_pickup(
    client: TestClient,
    db: Session,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    fill: Callable[..., Farm],
) -> None:
    farm = make_farm("hemp")
    fill(open_book(farm), farm["headers"], hemp_steps())
    fid = farm["field"]["id"]
    y = q(db, api.get_estimated_yield, fid, date.today().year)
    assert y is not None
    assert y.straw_kg == 20 * 450
    assert [r.picking_number for r in q(db, api.list_ready_for_pickup, crop="hemp")] == [1]
