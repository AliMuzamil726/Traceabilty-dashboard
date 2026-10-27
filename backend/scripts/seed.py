"""Idempotent seed for reference data.

Run manually from ``backend/``::

    python -m scripts.seed

It also runs on startup when ``SEED_ON_START=true`` and any seeded table is empty.
Rows are matched by their natural key (``code`` or ``list_key/value/country/crop``)
and only missing rows are inserted, so running it any number of times creates no
duplicates and never overwrites edits. Seeded offices and officers are flagged
``is_dummy=True`` so they can be replaced by real ones later. Seeded rows get
deterministic UUIDs (UUID5 of their natural key) so IDs survive a database reset.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.passwords import DEFAULT_PASSWORD, hash_password
from shared.models.field_office import FieldOffice
from shared.models.location import Location
from shared.models.master_list import MasterList
from shared.models.officer import Officer
from shared.models.site import Site
from shared.repositories import (
    FieldOfficeRepository,
    LocationRepository,
    MasterListRepository,
    OfficerRepository,
    SiteRepository,
)

logger = logging.getLogger("sawie.seed")

SEED_DIR = Path(__file__).resolve().parent / "seed_data"
_NAMESPACE = uuid.UUID("6b1d6a0e-7c43-4b8a-9c1e-5a3a2f0e9d11")


def stable_id(kind: str, natural_key: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{kind}:{natural_key}"))


def _load(name: str) -> list[dict[str, Any]]:
    """Read a seed file.

    Two shapes are accepted: a plain list of rows, and an object with a ``_meta``
    block plus ``items``. The second form is used by the larger reference datasets so
    that the file itself records where the data came from and that it still needs
    verifying, which a JSON list cannot say.
    """
    document: Any = json.loads((SEED_DIR / name).read_text(encoding="utf-8"))
    if isinstance(document, dict):
        rows: list[dict[str, Any]] = document.get("items", [])
        return rows
    return list(document)


@dataclass
class SeedReport:
    inserted: dict[str, int] = field(default_factory=dict)

    def bump(self, table: str) -> None:
        self.inserted[table] = self.inserted.get(table, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.inserted.values())


def needs_seed(session: Session) -> bool:
    """True when any seeded table is empty."""
    return any(
        repo.count() == 0
        for repo in (
            LocationRepository(session),
            FieldOfficeRepository(session),
            OfficerRepository(session),
            MasterListRepository(session),
        )
    )


#: Location files, in order: parents must exist before their children are inserted.
LOCATION_FILES = ("locations.json", "locations_pk.json")


def _seed_locations(session: Session, report: SeedReport) -> None:
    repo = LocationRepository(session)
    rows = [row for name in LOCATION_FILES for row in _load(name)]
    # Provinces first, then districts, then tehsils, so a parent is always resolvable.
    order = {"province": 0, "district": 1, "tehsil": 2}
    for row in sorted(rows, key=lambda r: order.get(r["level"], 9)):
        if repo.get_by_code(row["code"]):
            continue
        parent = repo.get_by_code(row["parent"]) if row.get("parent") else None
        repo.add(
            Location(
                id=stable_id("location", row["code"]),
                code=row["code"],
                country=row["country"],
                level=row["level"],
                name=row["name"],
                parent_id=parent.id if parent else None,
                sort_order=row.get("sort_order", 0),
            )
        )
        report.bump("locations")


def _seed_offices(session: Session, report: SeedReport) -> None:
    repo = FieldOfficeRepository(session)
    locations = LocationRepository(session)
    for row in _load("field_offices.json"):
        if repo.get_by_code(row["code"]):
            continue
        location = locations.get_by_code(row["location"]) if row.get("location") else None
        repo.add(
            FieldOffice(
                id=stable_id("field_office", row["code"]),
                code=row["code"],
                name=row["name"],
                country=row["country"],
                province=row.get("province"),
                district=row.get("district"),
                location_id=location.id if location else None,
                is_dummy=True,
            )
        )
        report.bump("field_offices")


def _seed_officers(session: Session, report: SeedReport) -> None:
    repo = OfficerRepository(session)
    offices = FieldOfficeRepository(session)
    for row in _load("officers.json"):
        existing = repo.get_by_code(row["code"])
        if existing is not None:
            # Filling an empty password is not an edit: without it the account from an
            # earlier build could not sign in at all. Everything else is left alone.
            if not existing.password_hash:
                existing.password_hash = hash_password(DEFAULT_PASSWORD)
            continue
        office = offices.get_by_code(row["office"]) if row.get("office") else None
        repo.add(
            Officer(
                id=stable_id("officer", row["code"]),
                code=row["code"],
                full_name=row["full_name"],
                email=row.get("email"),
                phone=row.get("phone"),
                role=row["role"],
                country=row["country"],
                field_office_id=office.id if office else None,
                password_hash=hash_password(DEFAULT_PASSWORD),
                is_dummy=True,
            )
        )
        report.bump("officers")


def _seed_master_lists(session: Session, report: SeedReport) -> None:
    repo = MasterListRepository(session)
    for row in _load("master_lists.json"):
        country, crop = row.get("country"), row.get("crop")
        if repo.find_exact(row["list_key"], row["value"], country, crop):
            continue
        natural = f"{row['list_key']}:{row['value']}:{country or '*'}:{crop or '*'}"
        repo.add(
            MasterList(
                id=stable_id("master_list", natural),
                list_key=row["list_key"],
                value=row["value"],
                label=row["label"],
                sort_order=row.get("sort_order", 0),
                country=country,
                crop=crop,
            )
        )
        report.bump("master_lists")


def _seed_sites(session: Session, report: SeedReport) -> None:
    repo = SiteRepository(session)
    for row in _load("sites.json"):
        if repo.get_by_code(row["code"]):
            continue
        repo.add(
            Site(
                id=stable_id("site", row["code"]),
                code=row["code"],
                name=row["name"],
                type=row["type"],
                crop=row["crop"],
                country=row["country"],
                address=row.get("address"),
                region=row.get("region"),
                is_dummy=True,
            )
        )
        report.bump("sites")


def run_seed(session: Session) -> SeedReport:
    """Insert missing reference rows. Commits nothing; the caller owns the transaction."""
    report = SeedReport()
    _seed_locations(session, report)
    _seed_offices(session, report)
    _seed_officers(session, report)
    _seed_master_lists(session, report)
    _seed_sites(session, report)
    logger.info("Seed complete: %s", report.inserted or "nothing to insert")
    return report


def main() -> None:
    from app.registry import import_all_models
    from core.config import get_settings
    from core.database import Database
    from core.logging import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sqlite_path is not None:
        settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    import_all_models()
    database = Database(settings.resolved_database_url)
    database.create_all()
    with database.session_scope() as session:
        report = run_seed(session)
    database.dispose()
    print(f"Seed finished. Inserted {report.total} row(s): {report.inserted}")


if __name__ == "__main__":
    main()
