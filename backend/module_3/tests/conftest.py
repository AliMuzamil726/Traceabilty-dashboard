"""Fixtures for Module 3 tests.

Farmers and fields are created through Module 2's HTTP API, exactly as an officer
would, so these tests never reach into Module 2's tables. ``valid_steps`` holds a
complete, valid answer for every step of both crops, dated relative to today.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

FB = "/api/v1/fieldbook"
REG = "/api/v1/register"

# Registration payloads and field shapes. Module 3 may not import Module 2's tests,
# so these are its own copies of what an officer would type.
MULTAN = (30.1575, 71.5249)
LINCOLNSHIRE = (53.2307, -0.5406)
_M_PER_DEG = 111_320.0


def square(
    centre: tuple[float, float], side_m: float = 200.0, *, offset_east_m: float = 0.0
) -> dict[str, Any]:
    lat, lng = centre
    d_lat = side_m / 2 / _M_PER_DEG
    scale = _M_PER_DEG * math.cos(math.radians(lat))
    d_lng = side_m / 2 / scale
    lng += offset_east_m / scale
    w, e, s, n = lng - d_lng, lng + d_lng, lat - d_lat, lat + d_lat
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def cotton_payload(office_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "crop": "cotton",
        "id_number": "35202-1234567-1",
        "name": "muhammad imran",
        "father_name": "ghulam rasool",
        "phone": "0300-1234567",
        "province_code": "PK-PB",
        "district_code": "PK-PB-MUL",
        "tehsil_code": "PK-PB-MUL-T01",
        "village": "Basti Malook",
        "field_office_id": office_id,
        "variety": "fh-142",
        "tenure": "owner",
        "previous_crop": "wheat",
        **overrides,
    }


def hemp_payload(office_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "crop": "hemp",
        "id_number": "123456789",
        "name": "sarah whitfield",
        "farm_name": "Fen End Farm",
        "phone": "07700 900123",
        "home_office_licence_no": "HO-HEMP-2026-0041",
        "postcode": "ln4 3qp",
        "field_office_id": office_id,
        "variety": "futura_75",
        "tenure": "owner_occupier",
        "previous_crop": "winter_wheat",
        **overrides,
    }


def d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


#: Sowing 150 days ago keeps every other date in the past and after sowing.
SOWING_DAYS_AGO = 150


def cotton_steps() -> dict[str, Any]:
    """A valid answer for each cotton step. Repeatable steps hold a list of entries."""
    return {
        "field_info": {
            "crop_season": "kharif",
            "area_sown": 9.5,
            "soil_texture": "loam",
            "drainage_status": "well_drained",
        },
        "land_preparation": [
            {
                "operation_date": d(160),
                "operation_type": "deep_ploughing",
                "machinery_type": "tractor_owned",
                "passes": 2,
                "tillage_depth": 25,
                "area_covered": 9.5,
                "diesel_per_pass": 6,
                "residue_handling": "incorporated",
                "cover_crop": "none",
            }
        ],
        "sowing": {
            "sowing_date": d(SOWING_DAYS_AGO),
            "variety": "fh-142",
            "seed_source": "registered_dealer",
            "seed_rate": 8,
            "sowing_method": "bed_and_furrow",
            "sowing_equipment": "seed_drill",
            "plant_population": 22000,
        },
        "nutrient_management": [
            {
                "application_date": d(140),
                "product": "urea",
                "n_content": 46,
                "pk_content": {"p2o5": 0, "k2o": 0},
                "quantity": 50,
                "crop_stage": "seedling",
            }
        ],
        "irrigation": [
            {
                "irrigation_date": d(130),
                "source": "tubewell_diesel",
                "method": "furrow",
                "duration": 6,
                "water_applied": 75,
                "diesel_used": 20,
                "pumping_head": 18,
                "pump_efficiency": 55,
            }
        ],
        "weed_management": [{"weed_date": d(120), "method": "manual_weeding"}],
        "pest_disease": [
            {
                "product_applied": "Imidacloprid",
                "product_type": "insecticide",
                "ai_content": 20,
                "dose": 250,
                "area_sprayed": 9.5,
                "pheromone_traps": 4,
                "beneficial_insects": ["lacewing", "spiders"],
            }
        ],
        "harvest": [
            {
                "picking_date": d(20),
                "picking_number": "1st",
                "harvest_method": "manual_picking",
                "yield": 12,
                "moisture": 9,
                "storage_material": "cotton_cloth",
                "ready_for_pickup": "yes",
            }
        ],
        "energy": {"total_diesel": 180, "grid_electricity": 0},
        "transport": {"transport_distance": 35, "transport_mode": "tractor_trolley"},
        "labour_social": {
            "family_labour": 3,
            "hired_labour": 10,
            "women_pickers": 8,
            "picking_wage": 1200,
            "training_attended": "yes",
            "training_name": "Better Cotton field school",
        },
    }


def hemp_steps() -> dict[str, Any]:
    return {
        "field_info": {
            "season": "spring_sowing",
            "licence_expiry": (date.today() + timedelta(days=200)).isoformat(),
            "area_drilled": 3.9,
            "soil_type": "clay_loam",
            "previous_crop": "winter_wheat",
        },
        "land_preparation": [
            {
                "operation_date": d(105),
                "operation_type": "plough",
                "passes": 1,
                "seedbed_condition": "fine_and_firm",
                "soil_temperature": 11,
            }
        ],
        "sowing": {
            "drilling_date": d(100),
            "crop_purpose": "fibre",
            "variety": "futura_75",
            "seed_lot": "LOT-2026-17",
            "seed_rate": 45,
            "drill_type": "combine_drill",
            "row_width": 12.5,
            "drilling_depth": 2.5,
        },
        "nutrient_management": [
            {
                "application_date": d(98),
                "product": "ammonium_nitrate",
                "rate": 250,
                "rate_unit": "kg_per_ha",
                "nutrient_content": {"n": 85, "p2o5": 0, "k2o": 0},
                "method": "broadcast",
            }
        ],
        "crop_monitoring": [
            {
                "visit_date": d(60),
                "growth_stage": "vegetative",
                "plant_height": 120,
                "plants_per_m2": 180,
                "canopy_closure": "closed",
            }
        ],
        "weeds_pests": [
            {
                "issue_date": d(70),
                "issue": "Fat hen",
                "severity": "low",
                "action_taken": "None needed",
            }
        ],
        "harvest": {
            "cutting_date": d(15),
            "growth_stage_at_cutting": "early_flowering",
            "cutting_method": "mower_conditioner",
            "stem_length": 190,
            "area_cut": 3.9,
        },
        "retting": {
            "retting_start": d(15),
            "turning_dates": [d(10), d(5)],
            "retting_end": d(2),
            "location": "Field headland",
        },
        "baling": [
            {
                "baling_date": d(1),
                "bale_type": "large_square",
                "number_of_bales": 20,
                "avg_bale_weight": 450,
                "straw_moisture": 14,
                "storage_location": "Barn 2",
                "ready_for_pickup": "yes",
            }
        ],
    }


@pytest.fixture
def officer_ids(client: TestClient) -> dict[str, str]:
    page = client.get("/api/v1/officers", params={"page_size": 200}).json()
    return {o["code"]: o["id"] for o in page["items"]}


@pytest.fixture
def as_officer(officer_ids: dict[str, str]) -> Callable[[str], dict[str, str]]:
    return lambda code: {"X-Officer-Id": officer_ids[code]}


@pytest.fixture
def make_farm(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """Register a farmer with one field. Returns ``{farmer, field, headers}``."""
    counter = {"n": 0}

    def _make(crop: str = "cotton", officer: str | None = None, fields: int = 1) -> dict[str, Any]:
        counter["n"] += 1
        n = counter["n"]
        code = officer or ("PK-MUL-01" if crop == "cotton" else "GB-EOE-01")
        headers = as_officer(code)
        country = "PK" if crop == "cotton" else "GB"
        office = client.get("/api/v1/offices", params={"country": country}).json()["items"][0]
        if crop == "cotton":
            body = cotton_payload(office["id"], id_number=f"35202-{n:07d}-1")
            centre = (MULTAN[0] + n * 0.02, MULTAN[1])
        else:
            body = hemp_payload(
                office["id"],
                id_number=f"{100000000 + n}",
                home_office_licence_no=f"HO-TEST-{n:04d}",
            )
            centre = (LINCOLNSHIRE[0] + n * 0.02, LINCOLNSHIRE[1])
        r = client.post(f"{REG}/farmers", json=body, headers=headers)
        assert r.status_code in (200, 201), r.text
        farmer = r.json()["farmer"]
        made = []
        for i in range(fields):
            fr = client.post(
                f"{REG}/farmers/{farmer['id']}/fields",
                json={"geometry": square(centre, 200, offset_east_m=400 * i)},
                headers=headers,
            )
            assert fr.status_code == 201, fr.text
            made.append(fr.json())
        return {"farmer": farmer, "field": made[0], "fields": made, "headers": headers}

    return _make


@pytest.fixture
def open_book(client: TestClient) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _open(farm: dict[str, Any], season_year: int | None = None) -> dict[str, Any]:
        r = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": season_year or date.today().year},
            headers=farm["headers"],
        )
        assert r.status_code in (200, 201), r.text
        return r.json()

    return _open


@pytest.fixture
def fill(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Save every step of a book from a steps dict. Returns the final book state."""

    def _fill(
        book: dict[str, Any],
        headers: dict[str, str],
        steps: dict[str, Any],
        *,
        skip: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        state = book
        order = {
            s["key"]: i
            for i, s in enumerate(
                client.get(f"{FB}/schemas/{book['crop']}", headers=headers).json()["steps"]
            )
        }
        for key in sorted(steps, key=lambda k: order[k]):
            if key in skip:
                continue
            value = steps[key]
            h = {**headers, "X-Fieldbook-Version": str(state["version"])}
            if isinstance(value, list):
                for entry in value:
                    r = client.post(
                        f"{FB}/books/{book['id']}/steps/{key}/entries",
                        json={"data": entry},
                        headers=h,
                    )
                    assert r.status_code == 201, (key, r.text)
                    state = r.json()["book"]
                    h = {**headers, "X-Fieldbook-Version": str(state["version"])}
            else:
                r = client.put(
                    f"{FB}/books/{book['id']}/steps/{key}", json={"data": value}, headers=h
                )
                assert r.status_code == 200, (key, r.text)
                state = r.json()["book"]
        return state

    return _fill


def vh(book: dict[str, Any], headers: dict[str, str]) -> dict[str, str]:
    """Headers carrying the book's current version."""
    return {**headers, "X-Fieldbook-Version": str(book["version"])}
