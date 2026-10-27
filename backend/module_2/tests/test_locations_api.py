"""The location cascade and the village suggestion endpoint."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

REGISTER = "/api/v1/register"


class TestCascade:
    def test_pakistan_has_seven_provinces(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = client.get(
            f"{REGISTER}/locations/provinces",
            params={"country": "PK"},
            headers=as_officer("PK-MUL-01"),
        ).json()
        labels = [i["label"] for i in body["items"]]
        assert len(labels) == 7
        assert "Punjab" in labels
        assert "Sindh" in labels
        assert "Islamabad Capital Territory" in labels
        assert all(i["level"] == "province" for i in body["items"])

    def test_punjab_has_thirty_six_districts(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = client.get(
            f"{REGISTER}/locations/districts",
            params={"province": "PK-PB"},
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert len(body["items"]) == 36
        labels = [i["label"] for i in body["items"]]
        for district in ("Multan", "Khanewal", "Lodhran", "Vehari", "Bahawalpur", "Rajanpur"):
            assert district in labels
        assert all(i["parent_code"] == "PK-PB" for i in body["items"])

    def test_districts_are_scoped_to_their_province(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        headers = as_officer("PK-MUL-01")
        punjab = client.get(
            f"{REGISTER}/locations/districts", params={"province": "PK-PB"}, headers=headers
        ).json()
        sindh = client.get(
            f"{REGISTER}/locations/districts", params={"province": "PK-SD"}, headers=headers
        ).json()
        punjab_labels = {i["label"] for i in punjab["items"]}
        sindh_labels = {i["label"] for i in sindh["items"]}
        assert "Sanghar" in sindh_labels
        assert "Sanghar" not in punjab_labels
        assert punjab_labels.isdisjoint(sindh_labels)

    def test_cotton_belt_districts_have_tehsils(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = client.get(
            f"{REGISTER}/locations/tehsils",
            params={"district": "PK-PB-MUL"},
            headers=as_officer("PK-MUL-01"),
        ).json()
        labels = [i["label"] for i in body["items"]]
        assert labels == ["Multan City", "Multan Saddar", "Shujabad", "Jalalpur Pirwala"]
        assert body["allow_manual"] is True

    def test_a_district_without_tehsils_still_allows_manual_entry(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        headers = as_officer("PK-MUL-01")
        districts = client.get(
            f"{REGISTER}/locations/districts", params={"province": "PK-PB"}, headers=headers
        ).json()["items"]
        lahore = next(d for d in districts if d["label"] == "Lahore")
        body = client.get(
            f"{REGISTER}/locations/tehsils", params={"district": lahore["value"]}, headers=headers
        ).json()
        assert body["items"] == []
        assert body["allow_manual"] is True

    def test_sindh_cotton_districts_have_tehsils(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        headers = as_officer("PK-MUL-01")
        districts = client.get(
            f"{REGISTER}/locations/districts", params={"province": "PK-SD"}, headers=headers
        ).json()["items"]
        sanghar = next(d for d in districts if d["label"] == "Sanghar")
        body = client.get(
            f"{REGISTER}/locations/tehsils", params={"district": sanghar["value"]}, headers=headers
        ).json()
        assert "Shahdadpur" in [i["label"] for i in body["items"]]

    def test_an_unknown_parent_code_is_a_404(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        response = client.get(
            f"{REGISTER}/locations/districts",
            params={"province": "PK-NOPE"},
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "location_not_found"


class TestVillageSuggestions:
    def test_villages_are_suggested_from_what_officers_already_typed(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_2.tests.conftest import cotton_payload

        headers = as_officer("PK-MUL-01")
        register_cotton(village="Basti Malook")
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(
                pk_office["id"],
                id_number="35202-3333333-3",
                name="Second Farmer",
                village="Basti Nau",
            ),
            headers=headers,
        )

        every = client.get(
            f"{REGISTER}/locations/villages/suggest",
            params={"tehsil": "Multan City"},
            headers=headers,
        ).json()
        assert sorted(every) == ["Basti Malook", "Basti Nau"]

        filtered = client.get(
            f"{REGISTER}/locations/villages/suggest",
            params={"tehsil": "Multan City", "q": "Basti M"},
            headers=headers,
        ).json()
        assert filtered == ["Basti Malook"]

    def test_an_unknown_tehsil_suggests_nothing(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        assert (
            client.get(
                f"{REGISTER}/locations/villages/suggest",
                params={"tehsil": "Nowhere"},
                headers=as_officer("PK-MUL-01"),
            ).json()
            == []
        )
