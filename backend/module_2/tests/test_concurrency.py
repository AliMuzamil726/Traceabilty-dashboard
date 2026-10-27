"""Race safety: the SAWIE ID counter and the zero-overlap rule under concurrent saves.

These tests use real threads against a real SQLite file, because the guarantees being
checked come from the database (``BEGIN IMMEDIATE`` plus ``UPDATE ... RETURNING``,
DECISIONS D-006) rather than from Python.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from core.database import Database
from core.errors import ConflictError
from core.ids import peek_value
from module_2.models import Farmer, Field
from module_2.services import ids
from module_2.services.fields import FieldService
from module_2.tests.conftest import first_office_id, square

THREADS = 50


def _make_farmer(database: Database, office_id: str, sawie_id: int = 1001) -> str:
    """Insert a farmer directly: these tests are about fields and counters, not forms."""
    with database.session_scope() as session:
        farmer = Farmer(
            sawie_id=sawie_id,
            crop="cotton",
            country="PK",
            id_number_norm=f"35202{sawie_id:07d}1",
            id_number_display=f"35202-{sawie_id:07d}-1",
            name="Muhammad Imran",
            father_name="Ghulam Rasool",
            province="Punjab",
            district="Multan",
            tehsil="Multan City",
            village="Basti Malook",
            field_office_id=office_id,
        )
        session.add(farmer)
        session.flush()
        return farmer.id


def test_sawie_ids_are_unique_and_sequential_under_fifty_threads(database: Database) -> None:
    """Fifty officers pressing Register at the same instant get fifty different IDs."""
    allocated: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    start = threading.Barrier(THREADS)

    def worker() -> None:
        try:
            start.wait(timeout=30)
            with database.session_scope() as session:
                value = ids.allocate_sawie_id(session)
            with lock:
                allocated.append(value)
        except BaseException as exc:  # noqa: BLE001 - reported through `errors`
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not errors, errors
    assert len(allocated) == THREADS
    assert len(set(allocated)) == THREADS, "a SAWIE ID was handed out twice"
    assert sorted(allocated) == list(range(1001, 1001 + THREADS))

    with database.session_scope() as session:
        assert peek_value(session, ids.sawie_counter_key()) == THREADS


def test_a_rolled_back_registration_does_not_consume_a_sawie_id(database: Database) -> None:
    session = database.session_factory()
    try:
        assert ids.allocate_sawie_id(session) == 1001
        session.rollback()
    finally:
        session.close()
    with database.session_scope() as session:
        # The number was never committed, so the next farmer still gets 1001.
        assert ids.preview_sawie_id(session) == 1001
        assert ids.allocate_sawie_id(session) == 1001


def test_field_ids_are_unique_per_farmer_under_concurrent_saves(database: Database) -> None:
    """Twenty non-overlapping fields saved at once still get twenty distinct IDs."""
    with database.session_scope() as session:
        office_id = first_office_id(session, "PK")
    farmer_id = _make_farmer(database, office_id)

    count = 20
    saved: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    start = threading.Barrier(count)

    def worker(index: int) -> None:
        try:
            start.wait(timeout=30)
            session = database.session_factory()
            try:
                field = FieldService(session).create(
                    farmer_id,
                    square(side_m=100, offset_east_m=index * 400),
                    pin_lat=None,
                    pin_lng=None,
                    officer_id=None,
                )
                with lock:
                    saved.append(field.field_id)
            finally:
                session.close()
        except BaseException as exc:  # noqa: BLE001 - reported through `errors`
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert not errors, errors
    assert len(set(saved)) == count
    assert sorted(saved) == [f"1001-{n:02d}" for n in range(1, count + 1)]


def test_two_concurrent_overlapping_saves_let_exactly_one_through(database: Database) -> None:
    """The second save re-checks inside its own transaction and loses."""
    with database.session_scope() as session:
        office_id = first_office_id(session, "PK")
    farmer_id = _make_farmer(database, office_id)

    geometry = square(side_m=200)
    results: list[str] = []
    conflicts: list[ConflictError] = []
    others: list[BaseException] = []
    lock = threading.Lock()
    start = threading.Barrier(2)

    def worker(offset_m: float) -> None:
        session = database.session_factory()
        try:
            start.wait(timeout=30)
            field = FieldService(session).create(
                farmer_id,
                square(side_m=200, offset_east_m=offset_m),
                pin_lat=None,
                pin_lng=None,
                officer_id=None,
            )
            with lock:
                results.append(field.field_id)
        except ConflictError as exc:
            session.rollback()
            with lock:
                conflicts.append(exc)
        except BaseException as exc:  # noqa: BLE001 - reported through `others`
            session.rollback()
            with lock:
                others.append(exc)
        finally:
            session.close()

    # Both squares cover the same ground, offset by one percent of the side.
    threads = [
        threading.Thread(target=worker, args=(0.0,)),
        threading.Thread(target=worker, args=(2.0,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert not others, others
    assert len(results) == 1, f"expected one save to succeed, got {results}"
    assert len(conflicts) == 1
    assert conflicts[0].code == "field_overlap"

    with database.session_scope() as session:
        from sqlalchemy import func, select

        stored = session.execute(
            select(func.count()).select_from(Field).where(Field.deleted_at.is_(None))
        ).scalar_one()
        assert stored == 1

    assert geometry["type"] == "Polygon"  # the fixture itself was never mutated


@pytest.mark.parametrize("attempts", [3])
def test_sequential_overlapping_saves_are_rejected_every_time(
    database: Database, attempts: int
) -> None:
    with database.session_scope() as session:
        office_id = first_office_id(session, "PK")
    farmer_id = _make_farmer(database, office_id)

    session = database.session_factory()
    try:
        FieldService(session).create(
            farmer_id, square(side_m=200), pin_lat=None, pin_lng=None, officer_id=None
        )
    finally:
        session.close()

    for _ in range(attempts):
        session = database.session_factory()
        try:
            with pytest.raises(ConflictError):
                FieldService(session).create(
                    farmer_id,
                    square(side_m=200, offset_east_m=198),
                    pin_lat=None,
                    pin_lng=None,
                    officer_id=None,
                )
            session.rollback()
        finally:
            session.close()


def test_a_rejected_field_save_does_not_consume_a_field_id(database: Database) -> None:
    with database.session_scope() as session:
        office_id = first_office_id(session, "PK")
    farmer_id = _make_farmer(database, office_id)

    session = database.session_factory()
    try:
        first = FieldService(session).create(
            farmer_id, square(side_m=200), pin_lat=None, pin_lng=None, officer_id=None
        )
        assert first.field_id == "1001-01"
    finally:
        session.close()

    session = database.session_factory()
    try:
        with pytest.raises(ConflictError):
            FieldService(session).create(
                farmer_id,
                square(side_m=200, offset_east_m=198),
                pin_lat=None,
                pin_lng=None,
                officer_id=None,
            )
        session.rollback()
    finally:
        session.close()

    session = database.session_factory()
    try:
        # The rejected attempt rolled back, so the next real field is 02, not 03.
        second: Any = FieldService(session).create(
            farmer_id,
            square(side_m=200, offset_east_m=400),
            pin_lat=None,
            pin_lng=None,
            officer_id=None,
        )
        assert second.field_id == "1001-02"
    finally:
        session.close()
