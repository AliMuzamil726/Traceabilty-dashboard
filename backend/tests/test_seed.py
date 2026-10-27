from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import Database
from scripts.seed import LOCATION_FILES, _load, needs_seed, run_seed, stable_id
from shared.models import FieldOffice, Location, MasterList, Officer
from shared.models.site import Site


def _counts(session: Session) -> dict[str, int]:
    return {
        m.__tablename__: session.execute(select(func.count()).select_from(m)).scalar_one()
        for m in (Location, FieldOffice, Officer, MasterList, Site)
    }


def _expected_counts() -> dict[str, int]:
    """Row counts taken from the seed files themselves.

    Reference data grows as modules are built (Module 2 added the Pakistan
    administrative hierarchy and three master lists), so the counts are derived
    rather than pinned: the test still proves every row is inserted exactly once.
    """
    locations = {row["code"] for name in LOCATION_FILES for row in _load(name)}
    return {
        "locations": len(locations),
        "field_offices": len(_load("field_offices.json")),
        "officers": len(_load("officers.json")),
        "master_lists": len(_load("master_lists.json")),
        "sites": len(_load("sites.json")),
    }


def test_seed_is_idempotent(database: Database) -> None:
    with database.session_scope() as s:
        assert needs_seed(s)
        first = run_seed(s)
    assert first.inserted == _expected_counts()

    with database.session_scope() as s:
        before = _counts(s)
        assert not needs_seed(s)
        second = run_seed(s)
        assert second.total == 0
        assert _counts(s) == before


def test_seed_shape(database: Database) -> None:
    with database.session_scope() as s:
        run_seed(s)
    with database.session_scope() as s:
        offices = s.execute(select(FieldOffice)).scalars().all()
        assert {o.country for o in offices} == {"PK", "GB"}
        assert all(o.is_dummy for o in offices)
        for office in offices:
            assert len(office.officers) == 2
        admins = s.execute(select(Officer).where(Officer.role == "admin")).scalars().all()
        assert len(admins) == 1
        assert s.get(Officer, stable_id("officer", "PK-MUL-01")) is not None


def test_seed_restores_only_missing_rows(database: Database) -> None:
    with database.session_scope() as s:
        run_seed(s)
    with database.session_scope() as s:
        officer = s.get(Officer, stable_id("officer", "GB-EMD-02"))
        assert officer is not None
        officer.full_name = "Edited Name"
        s.delete(s.get(Officer, stable_id("officer", "GB-EMD-01")))
    with database.session_scope() as s:
        report = run_seed(s)
        assert report.inserted == {"officers": 1}
        assert s.get(Officer, stable_id("officer", "GB-EMD-02")).full_name == "Edited Name"
