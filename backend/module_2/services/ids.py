"""Allocation of the two business identifiers Module 2 owns.

Both come from the shared ``id_counters`` table through :mod:`core.ids`, so they are
allocated inside the caller's transaction and are race-safe (see DECISIONS D-006).
A number is only consumed when that transaction commits.

**SAWIE ID** is a plain number starting at 1001, with no country or crop in it: one
farmer keeps it for life and may in principle move programme, so nothing in the ID
can go stale. The counter itself starts at 1, so :data:`SAWIE_ID_BASE` is added to it.

**Field ID** is ``{sawie_id}-{nn}``, counted per farmer, so an officer reads a field
ID and immediately knows whose field it is. The counter is never rewound, so a number
is not reused after a field is deleted.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.ids import next_value, peek_value

#: The SAWIE ID counter starts at 1; farmers start at 1001.
SAWIE_ID_BASE = 1000
SAWIE_ID_COUNTER = "sawie_id"

FIELD_SEQUENCE_WIDTH = 2


def sawie_counter_key() -> str:
    return SAWIE_ID_COUNTER


def field_counter_key(sawie_id: int) -> str:
    return f"field_id:{sawie_id}"


def allocate_sawie_id(session: Session) -> int:
    """Allocate the next SAWIE ID. Consumed only when the transaction commits."""
    return SAWIE_ID_BASE + next_value(session, SAWIE_ID_COUNTER)


def preview_sawie_id(session: Session) -> int:
    """The SAWIE ID a new farmer would most likely get, without consuming it.

    Only ever shown as a preview: another officer may save first, so the final ID is
    whatever :func:`allocate_sawie_id` returns inside the saving transaction.
    """
    return SAWIE_ID_BASE + peek_value(session, SAWIE_ID_COUNTER) + 1


def allocate_field_id(session: Session, sawie_id: int) -> str:
    """Allocate the next field ID for one farmer, for example ``1001-03``."""
    sequence = next_value(session, field_counter_key(sawie_id))
    return format_field_id(sawie_id, sequence)


def preview_field_id(session: Session, sawie_id: int) -> str:
    sequence = peek_value(session, field_counter_key(sawie_id)) + 1
    return format_field_id(sawie_id, sequence)


def format_field_id(sawie_id: int, sequence: int) -> str:
    return f"{sawie_id}-{sequence:0{FIELD_SEQUENCE_WIDTH}d}"
