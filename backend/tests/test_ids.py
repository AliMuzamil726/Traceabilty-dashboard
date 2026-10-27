import threading
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.registry import import_all_models
from core.database import Database
from core.ids import format_id, next_id, next_value, peek_value


def test_counter_starts_at_one_and_increments(session: Session) -> None:
    assert peek_value(session, "farmer.pk") == 0
    assert next_value(session, "farmer.pk") == 1
    assert next_value(session, "farmer.pk") == 2
    assert next_value(session, "other") == 1
    assert peek_value(session, "farmer.pk") == 2


def test_format_and_next_id(session: Session) -> None:
    assert format_id("SAW-PK", 42) == "SAW-PK-000042"
    assert format_id("F", 7, width=3) == "F-007"
    assert next_id(session, "heap", "HP") == "HP-000001"
    with pytest.raises(ValueError, match="negative"):
        format_id("X", -1)
    with pytest.raises(ValueError, match="non-empty"):
        next_value(session, "")


def test_rolled_back_transaction_does_not_consume_numbers(database: Database) -> None:
    with database.session_scope() as s:
        assert next_value(s, "k") == 1
    s2 = database.session_factory()
    assert next_value(s2, "k") == 2
    s2.rollback()
    s2.close()
    with database.session_scope() as s3:
        assert next_value(s3, "k") == 2


@pytest.mark.parametrize("key_prefix", ["fresh", "existing"])
def test_counter_is_race_safe_across_threads(tmp_path: Path, key_prefix: str) -> None:
    import_all_models()
    database = Database(f"sqlite:///{(tmp_path / 'race.db').as_posix()}")
    database.create_all()
    key = f"race.{key_prefix}"
    if key_prefix == "existing":
        with database.session_scope() as s:
            next_value(s, key)

    threads_count, per_thread = 12, 25
    results: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    barrier = threading.Barrier(threads_count)

    def worker() -> None:
        try:
            barrier.wait()
            for _ in range(per_thread):
                with database.session_scope() as s:
                    value = next_value(s, key)
                with lock:
                    results.append(value)
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(threads_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    database.dispose()

    assert not errors, errors
    total = threads_count * per_thread
    assert len(results) == total
    assert len(set(results)) == total, "duplicate counter values were issued"
    start = 2 if key_prefix == "existing" else 1
    assert sorted(results) == list(range(start, start + total))
