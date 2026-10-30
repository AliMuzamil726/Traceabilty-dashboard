"""Query counts and latency on a seeded database.

Two different things are measured, and only one of them is a number of milliseconds:

* **Query count.** Every section must take the same number of queries whatever the
  size of the database. The test seeds two sizes and compares, which catches an N+1
  wherever it is added, including inside another module's public API.
* **Latency.** Measured on the seeded database so a regression shows up, with a
  generous ceiling: this runs on whatever machine the suite runs on, and a strict
  millisecond budget in a test only produces flaky failures. The real figures, measured
  on the full 10,000-farmer seed, are in ``docs/TESTING.md``.

The big seed (10,000 farmers) is not loaded here, because it takes a minute of writes
and a hundred megabytes. ``scripts/seed_perf.py`` builds it for a real measurement.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from core.database import Database
from core.events import FIELD_UPDATED, bus
from module_1.tests.conftest import DASH
from scripts.seed_perf import reset as reset_perf
from scripts.seed_perf import run as seed_perf

#: The sections a query count is taken for, with the parameters they are read with.
SECTIONS = (
    "overview",
    "pipeline",
    "distribution",
    "alerts",
    "activity",
    "map",
    "officers",
    "onboarding",
)

#: Ceiling per section. Generous on purpose; see the module docstring.
LATENCY_BUDGET_MS = 3_000


class QueryCounter:
    """Counts every statement the request runs, on the read and the write engine."""

    def __init__(self, database: Database) -> None:
        self.engines = {database.engine, database.read_engine}
        self.count = 0

    def __enter__(self) -> QueryCounter:
        for engine in self.engines:
            event.listen(engine, "before_cursor_execute", self._seen)
        return self

    def __exit__(self, *_: object) -> None:
        for engine in self.engines:
            event.remove(engine, "before_cursor_execute", self._seen)

    def _seen(self, *_: Any, **__: Any) -> None:
        self.count += 1


@pytest.fixture
def seeded(client: TestClient) -> Callable[[float], dict[str, int]]:
    """Load the performance seed at a given scale, replacing whatever was there.

    The reference data (officers, offices, sites, master lists, crop clock) is already
    there: the app seeds it on startup, and the reset only empties the business tables.
    Calling this twice in one test is how the query-count comparison gets two sizes of
    the same database.
    """

    def _seed(scale: float) -> dict[str, int]:
        database: Database = client.app.state.db
        session = database.session_factory()
        try:
            reset_perf(session)
            counts = seed_perf(session, scale=scale)
        finally:
            session.close()
        _invalidate_all()
        return counts

    return _seed


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    page = client.get("/api/v1/officers", params={"page_size": 200}).json()
    return {
        "X-Officer-Id": next(o["id"] for o in page["items"] if o["code"] == "ADMIN-01"),
    }


@pytest.fixture(autouse=True)
def _fresh(client: TestClient) -> Iterator[None]:
    """Clear every cache, so each measurement is the real cost of a section."""
    _invalidate_all()
    yield
    _invalidate_all()


def _invalidate_all() -> None:
    """Empty every cached view, the way a write does.

    Publishing a change is how the caches are really emptied: both the dashboard and
    Harvest Radar subscribe to it. Reaching into another module's cache from here
    would break the import rules the architecture test enforces, and would test
    something the product never does.
    """
    bus.publish(
        FIELD_UPDATED,
        {
            "field_id": "measurement",
            "field_code": "measurement",
            "farmer_id": "measurement",
            "changed": [],
            "geometry_changed": False,
        },
    )


def _queries(client: TestClient, section: str, headers: dict[str, str]) -> int:
    _invalidate_all()
    with QueryCounter(client.app.state.db) as counter:
        r = client.get(f"{DASH}/{section}", params={"crop": "all", "scope": "all"}, headers=headers)
        assert r.status_code == 200, r.text
    return counter.count


class TestQueryCounts:
    def test_no_section_runs_more_queries_as_the_database_grows(
        self,
        client: TestClient,
        admin: dict[str, str],
        seeded: Callable[[float], dict[str, int]],
    ) -> None:
        small = seeded(0.004)
        before = {s: _queries(client, s, admin) for s in SECTIONS}

        bigger = seeded(0.02)
        after = {s: _queries(client, s, admin) for s in SECTIONS}

        assert bigger["farmers"] > small["farmers"]
        grew = {s: (before[s], after[s]) for s in SECTIONS if after[s] > before[s]}
        assert not grew, f"query count grew with the data: {grew}"

    def test_every_section_takes_a_sensible_number_of_queries(
        self,
        client: TestClient,
        admin: dict[str, str],
        seeded: Callable[[float], dict[str, int]],
    ) -> None:
        seeded(0.01)
        counts = {s: _queries(client, s, admin) for s in SECTIONS}

        # A section reads several modules, so a few dozen statements is expected; a
        # hundred would mean something is being read row by row.
        assert all(1 <= n < 100 for n in counts.values()), counts

    def test_a_cached_section_runs_no_queries_at_all(
        self,
        client: TestClient,
        admin: dict[str, str],
        seeded: Callable[[float], dict[str, int]],
    ) -> None:
        seeded(0.004)
        params = {"crop": "cotton", "scope": "all"}
        client.get(f"{DASH}/pipeline", params=params, headers=admin)

        with QueryCounter(client.app.state.db) as counter:
            r = client.get(f"{DASH}/pipeline", params=params, headers=admin)
        assert r.status_code == 200
        # Only the officer lookup for the request itself.
        assert counter.count <= 2, counter.count


class TestLatency:
    def test_every_section_answers_inside_the_budget(
        self,
        client: TestClient,
        admin: dict[str, str],
        seeded: Callable[[float], dict[str, int]],
    ) -> None:
        seeded(0.02)
        slow: dict[str, float] = {}
        for section in SECTIONS:
            _invalidate_all()
            started = time.perf_counter()
            r = client.get(
                f"{DASH}/{section}", params={"crop": "all", "scope": "all"}, headers=admin
            )
            elapsed = (time.perf_counter() - started) * 1000
            assert r.status_code == 200, r.text
            if elapsed > LATENCY_BUDGET_MS:
                slow[section] = round(elapsed, 1)
        assert not slow, f"sections over {LATENCY_BUDGET_MS} ms: {slow}"

    def test_the_cache_makes_a_repeated_read_free(
        self,
        client: TestClient,
        admin: dict[str, str],
        seeded: Callable[[float], dict[str, int]],
    ) -> None:
        seeded(0.02)
        params = {"crop": "all", "scope": "all"}
        client.get(f"{DASH}/alerts", params=params, headers=admin)

        started = time.perf_counter()
        r = client.get(f"{DASH}/alerts", params=params, headers=admin)
        elapsed = (time.perf_counter() - started) * 1000

        assert r.status_code == 200
        assert elapsed < LATENCY_BUDGET_MS / 10
