"""Load a large, plausible database for performance measurement.

Run from ``backend/``::

    python -m scripts.seed_perf                 # 10,000 farmers (the stated target)
    python -m scripts.seed_perf --scale 0.01    # a hundredth of it, for tests
    python -m scripts.seed_perf --reset         # empty the business tables first

The stated target is 10,000 farmers, 20,000 fields, 50,000 deliveries and 500 heaps.
Every list, the radar and every dashboard section must stay under 400 ms p95 on it.

**This is a measuring tool, not a demo.** It writes rows straight into the tables with
SQLAlchemy Core, so it does not run any business rule: no overlap check, no crop clock,
no status machine, no audit entries and no events. The rows are shaped like real ones
and are consistent enough for every read path to work, but nothing here proves a rule.
Use the HTTP API for that.

Why Core and not the modules' models: ``scripts`` must not depend on any module (see
``backend/tests/test_architecture.py``), and a seed that spans seven modules would
break that rule. The tables are taken from ``Base.metadata`` after the composition root
has imported every model, so a renamed column fails here loudly instead of silently
writing the wrong shape (DECISIONS D-105).
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Table, delete, select
from sqlalchemy.orm import Session

from app.registry import import_all_models
from core.config import get_settings
from core.database import Base, Database

logger = logging.getLogger("sawie.seed_perf")

#: The target size, before ``--scale``.
FARMERS = 10_000
FIELDS_PER_FARMER = 2
DELIVERIES = 50_000
HEAPS = 500
BALES_PER_HEAP = 6
SCANS = 20_000

#: Share of farmers in each programme, and of fields that have a fieldbook.
HEMP_SHARE = 0.2
FIELDBOOK_SHARE = 0.7
SUBMITTED_SHARE = 0.45

#: Rows per insert. Large enough to be fast, small enough for SQLite's parameter limit.
BATCH = 1_000

#: Where the fields sit. Cotton in the Punjab belt, hemp in the east of England.
COTTON_CENTRES = [
    ("Punjab", "Multan", "Multan City", 30.1575, 71.5249),
    ("Punjab", "Bahawalpur", "Bahawalpur City", 29.3956, 71.6836),
    ("Punjab", "Lodhran", "Lodhran", 29.5333, 71.6333),
    ("Punjab", "Vehari", "Vehari", 30.0450, 72.3489),
    ("Sindh", "Sanghar", "Sanghar", 26.0468, 68.9481),
]
HEMP_CENTRES = [
    ("Lincolnshire", "East Midlands", 53.2307, -0.5406),
    ("Norfolk", "East of England", 52.6140, 0.8864),
    ("Suffolk", "East of England", 52.1872, 0.9708),
]

_M = 111_320.0
_SEASON = date.today().year
_NAMESPACE = uuid.UUID("3f1d2c77-91b5-4d0a-8c3e-7b6a5e4d3c21")

#: Tables emptied by ``--reset``, children before parents.
RESET_ORDER = (
    "qr_scan_log",
    "qr_tokens",
    "bales",
    "heaps",
    "delivery_status_history",
    "deliveries",
    "pickup_requests",
    "fieldbook_photos",
    "fieldbook_step_status",
    "fieldbook_entries",
    "fieldbooks",
    "fields",
    "farmer_season_profiles",
    "farmers",
    "audit_log",
)


def _id(kind: str, n: int) -> str:
    """A stable id, so re-running the seed with the same size is idempotent."""
    return str(uuid.uuid5(_NAMESPACE, f"{kind}:{n}"))


def table(name: str) -> Table:
    found = Base.metadata.tables.get(name)
    if found is None:  # pragma: no cover - a renamed table must fail loudly
        raise RuntimeError(f"Table '{name}' is not in the model metadata.")
    return found


def square(lat: float, lng: float, side_m: float = 200.0) -> dict[str, Any]:
    dl = side_m / 2 / _M
    dg = side_m / 2 / (_M * math.cos(math.radians(lat)))
    w, e, s, n = lng - dg, lng + dg, lat - dl, lat + dl
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def batched(rows: Sequence[dict[str, Any]], size: int = BATCH) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield list(rows[i : i + size])


def insert(session: Session, name: str, rows: Sequence[dict[str, Any]]) -> int:
    target = table(name)
    unknown = {k for row in rows[:1] for k in row} - set(target.columns.keys())
    if unknown:  # pragma: no cover - a renamed column must fail loudly
        raise RuntimeError(f"Unknown column(s) for '{name}': {sorted(unknown)}")
    for chunk in batched(rows):
        session.execute(target.insert(), chunk)
    session.commit()
    logger.info("%s: %d rows", name, len(rows))
    return len(rows)


def reset(session: Session) -> None:
    for name in RESET_ORDER:
        found = Base.metadata.tables.get(name)
        if found is not None:
            session.execute(delete(found))
    session.commit()
    logger.info("Business tables emptied")


def _reference(session: Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    officers = [
        dict(row._mapping)
        for row in session.execute(
            select(table("officers").c.id, table("officers").c.country, table("officers").c.role)
        )
    ]
    sites = [
        dict(row._mapping)
        for row in session.execute(
            select(table("sites").c.id, table("sites").c.code, table("sites").c.crop)
        )
    ]
    offices = [
        dict(row._mapping)
        for row in session.execute(
            select(table("field_offices").c.id, table("field_offices").c.country)
        )
    ]
    if not officers or not sites or not offices:
        raise SystemExit(
            "Reference data is missing. Run 'python -m scripts.seed' first, or start the "
            "backend once with SEED_ON_START=true."
        )
    return officers, [*sites], [*offices]  # type: ignore[return-value]


def run(session: Session, *, scale: float = 1.0, seed: int = 20_261_023) -> dict[str, int]:
    """Write the whole set and return how many rows each table got."""
    rng = random.Random(seed)
    officers, sites, offices = _reference(session)  # type: ignore[misc]
    by_country: dict[str, list[str]] = {"PK": [], "GB": []}
    for officer in officers:
        if officer["role"] != "admin" and officer["country"] in by_country:
            by_country[officer["country"]].append(officer["id"])
    office_by_country = {c: [o["id"] for o in offices if o["country"] == c] for c in by_country}
    site_by_crop = {
        "cotton": [s["id"] for s in sites if s["crop"] == "cotton"],
        "hemp": [s["id"] for s in sites if s["crop"] == "hemp"],
    }

    farmers_n = max(1, int(FARMERS * scale))
    deliveries_n = max(1, int(DELIVERIES * scale))
    heaps_n = max(1, int(HEAPS * scale))
    scans_n = max(0, int(SCANS * scale))
    now = datetime.now(UTC)
    counts: dict[str, int] = {}

    # ------------------------------------------------------------------- farmers
    farmer_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    fields_index: list[dict[str, Any]] = []
    for n in range(farmers_n):
        hemp = rng.random() < HEMP_SHARE
        crop = "hemp" if hemp else "cotton"
        country = "GB" if hemp else "PK"
        officer = rng.choice(by_country[country] or [None])
        farmer_id = _id("farmer", n)
        registered = now - timedelta(days=rng.randint(0, 364), minutes=rng.randint(0, 1439))
        # Every row carries the same keys, because one insert covers the whole batch.
        place: dict[str, Any] = dict.fromkeys(
            ("province", "district", "tehsil", "village", "county", "region", "postcode_norm")
        )
        if hemp:
            county, region, lat, lng = HEMP_CENTRES[n % len(HEMP_CENTRES)]
            place |= {"county": county, "region": region, "postcode_norm": f"LN4{n % 10}QP"}
            name = f"grower {n:05d}"
        else:
            province, district, tehsil, lat, lng = COTTON_CENTRES[n % len(COTTON_CENTRES)]
            place |= {
                "province": province,
                "district": district,
                "tehsil": tehsil,
                "village": f"basti {n % 40:02d}",
            }
            name = f"farmer {n:05d}"
        farmer_rows.append(
            {
                "id": farmer_id,
                "sawie_id": 1001 + n,
                "crop": crop,
                "country": country,
                "id_number_norm": f"perf{n:09d}",
                "id_number_display": f"35202-{n:07d}-1" if not hemp else f"{100000000 + n}",
                "name": name,
                "father_name": "ghulam rasool" if not hemp else None,
                "farm_name": "Fen End Farm" if hemp else None,
                "phone_norm": f"+9230012{n % 100000:05d}" if not hemp else None,
                "phone_display": f"0300-12{n % 100000:05d}" if not hemp else None,
                "home_office_licence_no": f"HO-P-{n:06d}" if hemp else None,
                "field_office_id": rng.choice(office_by_country[country]),
                "registered_by": officer,
                "created_at": registered,
                "updated_at": registered,
                **place,
            }
        )
        profile_rows.append(
            {
                "id": _id("profile", n),
                "farmer_id": farmer_id,
                "season_year": _SEASON,
                "variety": "futura_75" if hemp else "fh-142",
                "tenure": "owner_occupier" if hemp else "owner",
                "previous_crop": "winter_wheat" if hemp else "wheat",
                "created_at": registered,
                "updated_at": registered,
            }
        )
        for k in range(FIELDS_PER_FARMER):
            index = n * FIELDS_PER_FARMER + k
            # A grid, so no two boundaries overlap and every bounding box differs.
            flat = lat + (index % 400) * 0.0025
            flng = lng + (index // 400 % 400) * 0.0025
            geometry = square(flat, flng)
            ring = geometry["coordinates"][0]
            lngs = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            field_rows.append(
                {
                    "id": _id("field", index),
                    "field_id": f"{1001 + n}-{k + 1:02d}",
                    "farmer_id": farmer_id,
                    "geometry": geometry,
                    "bbox_min_lng": min(lngs),
                    "bbox_max_lng": max(lngs),
                    "bbox_min_lat": min(lats),
                    "bbox_max_lat": max(lats),
                    "pin_lat": flat,
                    "pin_lng": flng,
                    "vertex_count": 4,
                    "area_m2": 40_000.0,
                    "area_acre": 9.88,
                    "area_ha": 4.0,
                    "created_at": registered + timedelta(hours=1),
                    "updated_at": registered + timedelta(hours=1),
                }
            )
            fields_index.append(
                {
                    "id": _id("field", index),
                    "code": f"{1001 + n}-{k + 1:02d}",
                    "farmer_id": farmer_id,
                    "crop": crop,
                    "officer": officer,
                }
            )
    counts["farmers"] = insert(session, "farmers", farmer_rows)
    counts["farmer_season_profiles"] = insert(session, "farmer_season_profiles", profile_rows)
    counts["fields"] = insert(session, "fields", field_rows)

    # ---------------------------------------------------------------- fieldbooks
    book_rows: list[dict[str, Any]] = []
    entry_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    sown_fields: list[dict[str, Any]] = []
    for index, field in enumerate(fields_index):
        if rng.random() > FIELDBOOK_SHARE:
            continue
        book_id = _id("book", index)
        hemp = field["crop"] == "hemp"
        # Days after sowing spread across the whole crop clock, so every readiness
        # bucket and the overdue flag all appear in the data.
        das = rng.randint(5, 230 if not hemp else 150)
        sowing = date.today() - timedelta(days=das)
        submitted = rng.random() < SUBMITTED_SHARE
        touched = now - timedelta(days=rng.randint(0, 40))
        book_rows.append(
            {
                "id": book_id,
                "field_id": field["id"],
                "field_code": field["code"],
                "farmer_id": field["farmer_id"],
                "crop": field["crop"],
                "season_year": _SEASON,
                "status": "submitted" if submitted else "draft",
                "schema_version": "1",
                "version": 2,
                "locked": submitted,
                "submitted_at": touched if submitted else None,
                "submitted_by": field["officer"] if submitted else None,
                "created_at": touched - timedelta(days=1),
                "updated_at": touched,
                "created_by": field["officer"],
                "updated_by": field["officer"],
            }
        )
        step = "sowing"
        data = (
            {
                "drilling_date": sowing.isoformat(),
                "crop_purpose": "fibre",
                "variety": "futura_75",
                "seed_lot": "LOT-1",
                "seed_rate": 45,
                "drill_type": "combine_drill",
                "row_width": 12.5,
                "drilling_depth": 2.5,
            }
            if hemp
            else {
                "sowing_date": sowing.isoformat(),
                "variety": "fh-142",
                "seed_source": "registered_dealer",
                "seed_rate": 8,
                "sowing_method": "bed_and_furrow",
                "sowing_equipment": "seed_drill",
                "plant_population": 22_000,
            }
        )
        entry_rows.append(
            {
                "id": _id("entry", index),
                "fieldbook_id": book_id,
                "step_key": step,
                "entry_index": 0,
                "data": data,
                "completed": True,
                "updated_by": field["officer"],
                "created_at": touched,
                "updated_at": touched,
            }
        )
        status_rows.append(
            {
                "fieldbook_id": book_id,
                "step_key": step,
                "status": "complete",
                "updated_at": touched,
                "updated_by": field["officer"],
            }
        )
        if hemp:
            entry_rows.append(
                {
                    "id": _id("entry-licence", index),
                    "fieldbook_id": book_id,
                    "step_key": "field_info",
                    "entry_index": 0,
                    "data": {
                        "licence_no": f"HO-P-{index:06d}",
                        # A fifth of the licences are inside the warning window.
                        "licence_expiry": (
                            date.today() + timedelta(days=rng.choice([-5, 12, 200, 300, 400]))
                        ).isoformat(),
                        "area_drilled": 3.8,
                        "season": str(_SEASON),
                    },
                    "completed": True,
                    "updated_by": field["officer"],
                    "created_at": touched,
                    "updated_at": touched,
                }
            )
            status_rows.append(
                {
                    "fieldbook_id": book_id,
                    "step_key": "field_info",
                    "status": "complete",
                    "updated_at": touched,
                    "updated_by": field["officer"],
                }
            )
        sown_fields.append({**field, "book_id": book_id, "das": das})
    counts["fieldbooks"] = insert(session, "fieldbooks", book_rows)
    counts["fieldbook_entries"] = insert(session, "fieldbook_entries", entry_rows)
    counts["fieldbook_step_status"] = insert(
        session, "fieldbook_step_status", status_rows
    )

    # ------------------------------------------------- pickup requests, deliveries
    pickup_rows: list[dict[str, Any]] = []
    delivery_rows: list[dict[str, Any]] = []
    pool = [f for f in sown_fields if f["das"] > 90] or sown_fields
    for n in range(deliveries_n):
        field = pool[n % len(pool)]
        crop = field["crop"]
        request_id = _id("pickup", n)
        delivered = rng.random() < 0.75
        # A field may have only one pickup request per season, so once every eligible
        # field has one the rest of the deliveries fall into earlier seasons. That is
        # how a real database looks after a few years, and it exercises the season
        # filter as well as the volume.
        season_back = n // len(pool)
        season = _SEASON - season_back
        scheduled = date.today() - timedelta(days=rng.randint(0, 120) + 365 * season_back)
        received = datetime.combine(scheduled, datetime.min.time(), tzinfo=UTC) + timedelta(
            hours=rng.randint(7, 18)
        )
        weighbridge = round(rng.uniform(600, 2_400), 1)
        pickup_rows.append(
            {
                "id": request_id,
                "request_no": f"PR-{n + 1:06d}",
                "field_id": field["id"],
                "field_code": field["code"],
                "farmer_id": field["farmer_id"],
                "crop": crop,
                "season_year": season,
                "status": "fulfilled" if delivered else "scheduled",
                "estimated_quantity_kg": weighbridge,
                "quantity_is_estimate": True,
                "requested_by": field["officer"],
                "requested_at": received - timedelta(days=2),
                "updated_at": received,
            }
        )
        delivery_rows.append(
            {
                "id": _id("delivery", n),
                "delivery_no": f"DL-{n + 1:06d}",
                "pickup_request_id": request_id,
                "farmer_id": field["farmer_id"],
                "field_id": field["id"],
                "field_code": field["code"],
                "crop": crop,
                "season_year": season,
                "status": "delivered" if delivered else "scheduled",
                "site_id": rng.choice(site_by_crop[crop]),
                "scheduled_date": scheduled,
                "driver_name": "Akram Ali",
                "driver_phone": "0301 7654321" if crop == "cotton" else "07700 900456",
                "vehicle_no": f"mna-{n % 9000 + 1000}",
                "dispatched_at": received - timedelta(hours=3) if delivered else None,
                "delivered_at": received if delivered else None,
                "estimated_quantity_kg": weighbridge,
                "weighbridge_weight_kg": weighbridge if delivered else None,
                "moisture_pct": round(rng.uniform(6.0, 14.0), 1) if delivered else None,
                "variance_pct": 0.0 if delivered else None,
                # A twentieth are flagged, so the attention panel has something to find.
                "variance_level": (
                    rng.choice(["ok", "ok", "ok", "ok", "warn", "flag"]) if delivered else None
                ),
                "created_at": received - timedelta(days=2),
                "updated_at": received,
                "created_by": field["officer"],
                "updated_by": field["officer"],
            }
        )
    counts["pickup_requests"] = insert(session, "pickup_requests", pickup_rows)
    counts["deliveries"] = insert(session, "deliveries", delivery_rows)

    # ------------------------------------------------------------ heaps and bales
    heap_rows: list[dict[str, Any]] = []
    bale_rows: list[dict[str, Any]] = []
    token_rows: list[dict[str, Any]] = []
    assignments: list[tuple[str, str]] = []
    delivered_ids = [
        (d["id"], d["crop"], d["site_id"])
        for d in delivery_rows
        if d["status"] == "delivered"
    ]
    per_heap = max(1, len(delivered_ids) // heaps_n)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for n in range(heaps_n):
        members = delivered_ids[n * per_heap : (n + 1) * per_heap]
        if not members:
            break
        crop = members[0][1]
        site_id = members[0][2]
        members = [m for m in members if m[2] == site_id]
        heap_pk = _id("heap", n)
        heap_id = f"{'BWP-G1' if crop == 'cotton' else 'UK-P1'}-H{n + 1:03d}"
        opened = now - timedelta(days=rng.randint(0, 90))
        closed = rng.random() < 0.5
        unit = 170.0 if crop == "cotton" else 250.0
        heap_rows.append(
            {
                "id": heap_pk,
                "heap_id": heap_id,
                "site_id": site_id,
                "crop": crop,
                "status": "closed" if closed else "open",
                "opened_at": opened,
                "closed_at": opened + timedelta(days=5) if closed else None,
                "outturn_ratio_pct": 34.0 if crop == "cotton" else 25.0,
                "bale_unit_kg": unit,
                "shiv_pct": None if crop == "cotton" else 48.0,
                "dust_pct": None if crop == "cotton" else 7.0,
                "created_at": opened,
                "updated_at": opened,
            }
        )
        for member_id, _crop, _site in members:
            assignments.append((member_id, heap_id))
        for seq in range(1, max(1, int(BALES_PER_HEAP * min(1.0, scale * 10))) + 1):
            bale_id = _id(f"bale-{n}", seq)
            serial = f"{heap_id}-{seq:03d}"
            bale_rows.append(
                {
                    "id": bale_id,
                    "bale_serial": serial,
                    "heap_pk": heap_pk,
                    "seq": seq,
                    "weight_kg": unit,
                    "status": "active",
                    "created_at": opened + timedelta(days=1, minutes=seq),
                }
            )
            token_rows.append(
                {
                    "id": _id(f"token-{n}", seq),
                    "token": "".join(rng.choice(alphabet) for _ in range(12)),
                    "token_type": "bale",
                    "bale_serial": serial,
                    "heap_id": heap_id,
                    "status": "active",
                    "created_at": opened + timedelta(days=1, minutes=seq),
                    "label_print_count": 0,
                }
            )
    counts["heaps"] = insert(session, "heaps", heap_rows)
    counts["bales"] = insert(session, "bales", bale_rows)
    counts["qr_tokens"] = insert(session, "qr_tokens", token_rows)

    # Link the delivered loads to their heap. One statement per heap and chunk, so a
    # few hundred updates rather than one per delivery.
    deliveries_table = table("deliveries")
    by_heap: dict[str, list[str]] = {}
    for delivery_id, heap_id in assignments:
        by_heap.setdefault(heap_id, []).append(delivery_id)
    for heap_id, ids in by_heap.items():
        for chunk in batched([{"id": i} for i in ids], 400):
            session.execute(
                deliveries_table.update()
                .where(deliveries_table.c.id.in_([c["id"] for c in chunk]))
                .values(heap_id=heap_id)
            )
    session.commit()
    counts["delivery_heap_links"] = len(assignments)

    # -------------------------------------------------------------------- scans
    scan_rows: list[dict[str, Any]] = []
    if token_rows and scans_n:
        for n in range(scans_n):
            token = token_rows[n % len(token_rows)]
            scan_rows.append(
                {
                    "id": _id("scan", n),
                    "token_id": token["id"],
                    "scanned_at": now - timedelta(minutes=rng.randint(0, 60 * 24 * 60)),
                    "channel": "public" if n % 3 else "internal",
                    "ip_hash": f"{n:064d}"[:64],
                    "user_agent_family": "mobile",
                }
            )
    counts["qr_scan_log"] = insert(session, "qr_scan_log", scan_rows) if scan_rows else 0
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale", type=float, default=1.0, help="Fraction of the target size (default 1.0)"
    )
    parser.add_argument(
        "--reset", action="store_true", help="Empty the business tables before writing"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    import_all_models()
    database = Database(settings.resolved_database_url)
    database.create_all()
    session = database.session_factory()
    try:
        if args.reset:
            reset(session)
        counts = run(session, scale=args.scale)
    finally:
        session.close()
        database.dispose()
    logger.info("Done: %s", ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":  # pragma: no cover - console entry point
    raise SystemExit(main())
