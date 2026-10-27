"""Race-safe sequential counters backed by the ``id_counters`` table.

The increment runs inside the caller's transaction with a single
``UPDATE ... SET value = value + 1 ... RETURNING value`` statement. On SQLite every
transaction starts with ``BEGIN IMMEDIATE`` (see ``core.database``), on Postgres the
UPDATE takes a row lock, so two transactions can never receive the same number.
Numbers are only consumed when the caller's transaction commits.
"""

from __future__ import annotations

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import utcnow
from shared.models.id_counter import IdCounter


def next_value(session: Session, key: str) -> int:
    """Return the next integer for ``key`` (starting at 1)."""
    if not key:
        raise ValueError("Counter key must be a non-empty string.")
    stmt = (
        update(IdCounter)
        .where(IdCounter.key == key)
        .values(value=IdCounter.value + 1, updated_at=utcnow())
        .returning(IdCounter.value)
    )
    value = session.execute(stmt).scalar_one_or_none()
    if value is not None:
        return int(value)

    # First use of this key: create it. A concurrent creator on Postgres hits the
    # primary key; we then fall back to the UPDATE path.
    try:
        with session.begin_nested():
            session.execute(insert(IdCounter).values(key=key, value=1, updated_at=utcnow()))
        return 1
    except IntegrityError:
        return int(session.execute(stmt).scalar_one())


def peek_value(session: Session, key: str) -> int:
    """Current value without incrementing (0 if the key does not exist yet)."""
    value = session.execute(select(IdCounter.value).where(IdCounter.key == key)).scalar()
    return int(value or 0)


def format_id(prefix: str, number: int, width: int = 6) -> str:
    """``format_id("SAW-PK", 42)`` -> ``"SAW-PK-000042"``."""
    if number < 0:
        raise ValueError("Counter values are never negative.")
    return f"{prefix}-{number:0{width}d}"


def next_id(session: Session, key: str, prefix: str, width: int = 6) -> str:
    """Allocate the next formatted business ID (for SAWIE, field, delivery, heap IDs)."""
    return format_id(prefix, next_value(session, key), width)
