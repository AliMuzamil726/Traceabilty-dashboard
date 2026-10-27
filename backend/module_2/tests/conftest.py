"""Fixtures and factories for Module 2 tests.

The polygon helpers build squares of a known size in metres around a point, so a test
can say "two squares overlapping by one percent" and mean it, instead of hand-writing
coordinates and hoping.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import Database
from module_2.services.ratelimit import lookup_limiter
from shared.models.field_office import FieldOffice
from shared.models.officer import Officer

#: A point in the Multan cotton belt and one in Lincolnshire, for the two programmes.
MULTAN = (30.1575, 71.5249)
LINCOLNSHIRE = (53.2307, -0.5406)

METRES_PER_DEGREE_LAT = 111_320.0


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    """The lookup limiter is process-wide; no test should inherit another's window."""
    lookup_limiter.reset()
    yield
    lookup_limiter.reset()


def square(
    centre: tuple[float, float] = MULTAN,
    side_m: float = 200.0,
    *,
    offset_east_m: float = 0.0,
    offset_north_m: float = 0.0,
) -> dict[str, Any]:
    """A closed square GeoJSON Polygon of ``side_m`` metres, optionally shifted."""
    lat, lng = centre
    d_lat = side_m / 2 / METRES_PER_DEGREE_LAT
    d_lng = side_m / 2 / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    shift_lat = offset_north_m / METRES_PER_DEGREE_LAT
    shift_lng = offset_east_m / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    south, north = lat - d_lat + shift_lat, lat + d_lat + shift_lat
    west, east = lng - d_lng + shift_lng, lng + d_lng + shift_lng
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


def bowtie(centre: tuple[float, float] = MULTAN, side_m: float = 200.0) -> dict[str, Any]:
    """A self-intersecting ring (the two top corners swapped)."""
    ring = square(centre, side_m)["coordinates"][0]
    west_south, east_south, east_north, west_north, _ = ring
    return {
        "type": "Polygon",
        "coordinates": [[west_south, east_south, west_north, east_north, west_south]],
    }


@pytest.fixture
def officers(client: TestClient) -> dict[str, dict[str, Any]]:
    """The seeded officers, keyed by code, so a test can act as a specific one."""
    page = client.get("/api/v1/officers", params={"page_size": 200}).json()
    return {o["code"]: o for o in page["items"]}


@pytest.fixture
def as_officer(officers: dict[str, dict[str, Any]]) -> Callable[[str], dict[str, str]]:
    """``as_officer("PK-MUL-01")`` -> the request headers for that officer."""

    def _headers(code: str) -> dict[str, str]:
        return {"X-Officer-Id": officers[code]["id"]}

    return _headers


@pytest.fixture
def pk_office(client: TestClient) -> dict[str, Any]:
    offices = client.get("/api/v1/offices", params={"country": "PK"}).json()["items"]
    return offices[0]


@pytest.fixture
def gb_office(client: TestClient) -> dict[str, Any]:
    offices = client.get("/api/v1/offices", params={"country": "GB"}).json()["items"]
    return offices[0]


def cotton_payload(office_id: str, **overrides: Any) -> dict[str, Any]:
    """A valid cotton registration, ready to post."""
    payload: dict[str, Any] = {
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
    }
    payload.update(overrides)
    return payload


def hemp_payload(office_id: str, **overrides: Any) -> dict[str, Any]:
    """A valid hemp registration. The postcode resolves through the bundled area table."""
    payload: dict[str, Any] = {
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
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def register_cotton(
    client: TestClient, pk_office: dict[str, Any], as_officer: Callable[[str], dict[str, str]]
) -> Callable[..., dict[str, Any]]:
    """Register a cotton farmer and return the saved payload."""

    def _register(**overrides: Any) -> dict[str, Any]:
        response = client.post(
            "/api/v1/register/farmers",
            json=cotton_payload(pk_office["id"], **overrides),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code in (200, 201), response.text
        return response.json()

    return _register


@pytest.fixture
def seeded_officer_id(database: Database) -> str:
    with database.session_scope() as session:
        officer = session.execute(select(Officer).limit(1)).scalars().first()
        assert officer is not None
        return officer.id


def first_office_id(session: Session, country: str) -> str:
    """A field office id for tests that work against the bare ``database`` fixture.

    That fixture creates the tables but does not seed, so one is inserted on demand.
    """
    office = (
        session.execute(select(FieldOffice).where(FieldOffice.country == country).limit(1))
        .scalars()
        .first()
    )
    if office is None:
        office = FieldOffice(
            code=f"{country}-TEST",
            name=f"{country} Test Field Office",
            country=country,
            is_dummy=True,
        )
        session.add(office)
        session.flush()
    return office.id
