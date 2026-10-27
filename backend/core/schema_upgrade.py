"""Add columns that a database created by an earlier build does not have yet.

``create_all`` creates missing *tables* but never alters an existing one, so a column
added after a database was first created would be missing until the file was deleted.
Until the move to Supabase (where Alembic takes over, see ``docs/NEXT_STEPS.md``), this
module closes that gap: it compares a short, explicit list of expected columns against
the live table and issues ``ALTER TABLE ... ADD COLUMN`` for the ones that are absent.

Only additive, nullable-or-defaulted columns belong here. Anything that renames, drops
or re-types a column needs a real migration, and this module deliberately cannot do it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("sawie.schema")


@dataclass(frozen=True)
class AddColumn:
    table: str
    column: str
    #: SQL type and default, exactly as the dialect expects it.
    ddl: str


#: Columns added after the first release. Keep the reason in the comment.
ADDITIONS: tuple[AddColumn, ...] = (
    # Module 8 (Settings) shows a site's contact so an officer can call the gate.
    AddColumn("sites", "contact_person", "VARCHAR(120)"),
    AddColumn("sites", "contact_phone", "VARCHAR(32)"),
    # Optimistic concurrency for the per-crop configuration blocks.
    AddColumn("crop_clock_config", "version", "INTEGER NOT NULL DEFAULT 1"),
    AddColumn("delivery_config", "version", "INTEGER NOT NULL DEFAULT 1"),
    AddColumn("heap_config", "version", "INTEGER NOT NULL DEFAULT 1"),
    # Sign-in asks for a password, and a profile carries a photo (D-123).
    AddColumn("officers", "password_hash", "VARCHAR(255)"),
    AddColumn("officers", "photo_path", "VARCHAR(255)"),
)


def apply(engine: Engine, additions: tuple[AddColumn, ...] = ADDITIONS) -> list[str]:
    """Add every missing column. Returns the names applied, for the startup log."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    # Every read happens before the transaction opens: on SQLite an inspector reading
    # from a second connection while an ALTER holds the write lock waits on itself.
    missing = [
        addition
        for addition in additions
        if addition.table in tables  # create_all builds a missing table complete
        and addition.column not in {c["name"] for c in inspector.get_columns(addition.table)}
    ]
    if not missing:
        return []
    applied: list[str] = []
    with engine.begin() as conn:
        for addition in missing:
            conn.execute(
                text(f"ALTER TABLE {addition.table} ADD COLUMN {addition.column} {addition.ddl}")
            )
            applied.append(f"{addition.table}.{addition.column}")
    logger.info("Added missing column(s): %s", ", ".join(applied))
    return applied


__all__ = ["ADDITIONS", "AddColumn", "apply"]
