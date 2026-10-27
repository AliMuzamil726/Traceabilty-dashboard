"""``get_crop_status_bulk``: correct per pair, and a fixed number of queries for any N."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from core.database import Database
from module_3 import public_api as api
from module_3.models import Fieldbook, FieldbookEntry
from module_3.seed import run as seed_clock
from module_3.tests.conftest import cotton_steps, hemp_steps

TODAY = date(2026, 10, 1)


@contextmanager
def count_queries(session: Session) -> Iterator[list[str]]:
    seen: list[str] = []
    engine = session.get_bind()

    def listener(*args: Any) -> None:
        statement = str(args[2])
        if not statement.startswith(("BEGIN", "COMMIT", "ROLLBACK")):
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", listener)


def _book(session: Session, i: int, crop: str, entries: dict[str, Any]) -> None:
    book = Fieldbook(
        field_id=f"field-{i}",
        field_code=f"{1000 + i}-01",
        farmer_id=f"farmer-{i}",
        crop=crop,
        season_year=2026,
        status="draft",
        schema_version="2026.1",
        version=1,
    )
    session.add(book)
    session.flush()
    for step, value in entries.items():
        rows = value if isinstance(value, list) else [value]
        for n, data in enumerate(rows):
            session.add(
                FieldbookEntry(fieldbook_id=book.id, step_key=step, entry_index=n, data=data)
            )


def test_a_thousand_fields_take_the_same_few_queries(database: Database, session: Session) -> None:
    seed_clock(session)
    sowing = {"sowing_date": (TODAY - timedelta(days=125)).isoformat()}
    for i in range(1000):
        _book(session, i, "cotton", {"sowing": sowing} if i % 2 else {})
    session.commit()
    pairs = [(f"field-{i}", 2026) for i in range(1000)] + [("no-book", 2026)]

    with count_queries(session) as small:
        api.get_crop_status_bulk(session, pairs[:10], today=TODAY)
    with count_queries(session) as large:
        result = api.get_crop_status_bulk(session, pairs, today=TODAY)

    assert len(result) == 1001
    # Books and entries in chunks of 500, plus the clocks: never one query per field.
    assert len(large) <= 6, large
    assert len(small) <= 3
    assert result[("field-1", 2026)].days_after_sowing == 125
    assert result[("field-1", 2026)].status == "approaching"
    assert result[("field-0", 2026)].status == "no_sowing_data"
    assert result[("no-book", 2026)].fieldbook_id is None


def test_bulk_agrees_with_the_single_functions(
    client: TestClient,
    make_farm: Callable[..., dict[str, Any]],
    open_book: Callable[..., dict[str, Any]],
    fill: Callable[..., dict[str, Any]],
) -> None:
    cotton, hemp = make_farm("cotton"), make_farm("hemp")
    fill(open_book(cotton), cotton["headers"], cotton_steps())
    hemp_book = open_book(hemp)
    steps = hemp_steps()
    fill(hemp_book, hemp["headers"], {k: steps[k] for k in ("field_info", "sowing")})
    year = date.today().year
    s = client.app.state.db.session_factory()  # type: ignore[attr-defined]
    try:
        pairs = [(cotton["field"]["id"], year), (hemp["field"]["id"], year)]
        bulk = api.get_crop_status_bulk(s, pairs)
        for field_id, y in pairs:
            single = api.get_crop_status(s, field_id, y)
            assert single is not None
            assert bulk[(field_id, y)].status == single.status
            assert bulk[(field_id, y)].sowing_date == single.sowing_date
            yield_ = api.get_estimated_yield(s, field_id, y)
            assert bulk[(field_id, y)].estimated_kg == (yield_.estimated_kg if yield_ else None)
        c = bulk[pairs[0]]
        assert (c.harvested, c.ready_for_pickup, c.estimated_kg) == (True, True, 12 * 9.5 * 40)
        h = bulk[pairs[1]]
        assert (h.harvested, h.ready_for_pickup, h.status) == (
            False,
            False,
            "ready",
        )  # drilled 100 days ago
        assert api.get_crop_clocks(s)["hemp"].ready_day == 95
    finally:
        s.close()
