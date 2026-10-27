from sqlalchemy import select
from sqlalchemy.orm import Session

from core.audit import ACTION_UPDATE, compute_diff, record
from shared.models import AuditLog


def test_compute_diff_only_changed_keys() -> None:
    diff = compute_diff({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": "x"})
    assert diff == {"b": {"from": 2, "to": 3}, "c": {"from": None, "to": "x"}}
    assert compute_diff(None, None) == {}


def test_record_writes_entry(session: Session) -> None:
    entry = record(
        "farmer",
        "F-1",
        ACTION_UPDATE,
        "officer-1",
        {"name": {"from": "a", "to": "b"}},
        session=session,
    )
    stored = session.execute(select(AuditLog).where(AuditLog.id == entry.id)).scalar_one()
    assert stored.entity == "farmer"
    assert stored.action == "update"
    assert stored.diff["name"]["to"] == "b"
    assert stored.created_at.tzinfo is not None
