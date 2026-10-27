"""Fixtures for Module 8 tests.

Everything is driven through the HTTP API, as an administrator would, so the tests
prove the access rules and the audit trail as well as the behaviour.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

S = "/api/v1/settings"
REG = "/api/v1/register"
FB = "/api/v1/fieldbook"

_M = 111_320.0
MULTAN = (30.1575, 71.5249)


def _word(n: int) -> str:
    """A name made of letters only: the validator refuses digits."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[n // 26 % 26] + letters[n % 26]


def square(centre: tuple[float, float] = MULTAN, side_m: float = 200.0) -> dict[str, Any]:
    lat, lng = centre
    dl, dg = side_m / 2 / _M, side_m / 2 / (_M * math.cos(math.radians(lat)))
    w, e, s, n = lng - dg, lng + dg, lat - dl, lat + dl
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


@pytest.fixture
def officer_ids(client: TestClient) -> dict[str, str]:
    rows = client.get("/api/v1/officers").json()["items"]
    return {row["code"]: row["id"] for row in rows}


@pytest.fixture
def as_officer(officer_ids: dict[str, str]) -> Callable[[str], dict[str, str]]:
    def _headers(code: str) -> dict[str, str]:
        return {"X-Officer-Id": officer_ids[code]}

    return _headers


@pytest.fixture
def admin(as_officer: Callable[[str], dict[str, str]]) -> dict[str, str]:
    return as_officer("ADMIN-01")


@pytest.fixture
def staff(as_officer: Callable[[str], dict[str, str]]) -> dict[str, str]:
    return as_officer("STAFF-01")


@pytest.fixture
def field_officer(as_officer: Callable[[str], dict[str, str]]) -> dict[str, str]:
    return as_officer("PK-MUL-01")


@pytest.fixture
def any_list(client: TestClient, admin: dict[str, str]) -> str:
    """The key of a list that exists in the seeded reference data."""
    lists = client.get(f"{S}/lists", headers=admin).json()
    assert lists, "the seed should provide master lists"
    return str(lists[0]["key"])


@pytest.fixture
def cotton_farmer(
    client: TestClient, field_officer: dict[str, str]
) -> Callable[..., dict[str, Any]]:
    """Register one cotton farmer with a mapped field, for the usage counters."""

    counter = {"n": 0}

    def _make(**over: Any) -> dict[str, Any]:
        office = client.get("/api/v1/offices", params={"country": "PK"}).json()["items"][0]
        counter["n"] += 1
        n = counter["n"]
        body: dict[str, Any] = {
            "crop": "cotton",
            "id_number": f"35202-{n:07d}-1",
            "name": f"test farmer {_word(n)}",
            "father_name": "ghulam rasool",
            "phone": "0300-1234567",
            "province_code": "PK-PB",
            "district_code": "PK-PB-MUL",
            "tehsil_code": "PK-PB-MUL-T01",
            "village": "Basti Malook",
            "field_office_id": office["id"],
            "variety": "fh-142",
            "tenure": "owner",
            "previous_crop": "wheat",
            **over,
        }
        created = client.post(f"{REG}/farmers", json=body, headers=field_officer)
        assert created.status_code in (200, 201), created.text
        farmer = created.json()["farmer"]
        centre = (MULTAN[0] + n * 0.02, MULTAN[1])
        field = client.post(
            f"{REG}/farmers/{farmer['id']}/fields",
            json={"geometry": square(centre)},
            headers=field_officer,
        )
        assert field.status_code in (200, 201), field.text
        return {"farmer": farmer, "field": field.json()}

    return _make
