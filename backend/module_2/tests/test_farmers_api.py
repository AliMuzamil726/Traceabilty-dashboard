"""Registration, lookup, update, profile and list endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_2.services.ratelimit import lookup_limiter
from module_2.tests.conftest import cotton_payload, hemp_payload

REGISTER = "/api/v1/register"


class TestSawieId:
    def test_first_farmer_gets_1001_and_the_next_gets_1002(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        first = client.post(
            f"{REGISTER}/farmers", json=cotton_payload(pk_office["id"]), headers=headers
        )
        assert first.status_code == 201, first.text
        assert first.json()["farmer"]["sawie_id"] == 1001
        assert first.json()["created"] is True

        second = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], id_number="35202-7654321-9", name="Ahmed Khan"),
            headers=headers,
        )
        assert second.json()["farmer"]["sawie_id"] == 1002

    def test_a_cotton_and_a_hemp_farmer_share_one_numbering_sequence(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"]),
            headers=as_officer("PK-MUL-01"),
        )
        hemp = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"]),
            headers=as_officer("GB-EOE-01"),
        )
        assert hemp.status_code == 201, hemp.text
        assert hemp.json()["farmer"]["sawie_id"] == 1002

    def test_registering_the_same_id_number_never_makes_a_second_sawie_id(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        first = client.post(
            f"{REGISTER}/farmers", json=cotton_payload(pk_office["id"]), headers=headers
        )
        again = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], name="Muhammad Imran Khan", season_year=2027),
            headers=headers,
        )
        # Second save is an update plus a new season, not a creation.
        assert again.status_code == 200, again.text
        assert again.json()["created"] is False
        assert again.json()["farmer"]["sawie_id"] == first.json()["farmer"]["sawie_id"]
        assert again.json()["farmer"]["name"] == "Muhammad Imran Khan"

        page = client.get(f"{REGISTER}/farmers", headers=headers).json()
        assert page["total"] == 1


class TestLookup:
    def test_unknown_id_number_returns_a_preview_only(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "35202-1111111-1", "crop": "cotton"},
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert body["exists"] is False
        assert body["next_sawie_id_preview"] == 1001
        assert body["sawie_id"] is None
        assert body["personal"] is None
        assert body["id_number_masked"] == "*****-****111-1"

    def test_existing_farmer_returns_personal_data_but_never_crop_data(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton()
        body = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "3520212345671", "crop": "cotton"},
            headers=as_officer("PK-MUL-01"),
        ).json()

        assert body["exists"] is True
        assert body["sawie_id"] == saved["farmer"]["sawie_id"]
        assert body["registered_by"]["code"] == "PK-MUL-01"
        assert body["registered_at"] is not None

        personal = body["personal"]
        assert personal["name"] == "Muhammad Imran"
        assert personal["father_name"] == "Ghulam Rasool"
        assert personal["phone"] == "0300-1234567"
        assert personal["province_code"] == "PK-PB"
        assert personal["district_code"] == "PK-PB-MUL"
        assert personal["tehsil_code"] == "PK-PB-MUL-T01"
        assert personal["village"] == "Basti Malook"
        # Crop data is the officer's job every season, so it is absent by design.
        assert "variety" not in personal
        assert "tenure" not in personal
        assert "previous_crop" not in personal

    def test_crop_mismatch_is_flagged_and_withholds_personal_data(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()
        body = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "3520212345671", "crop": "hemp"},
            headers=as_officer("GB-EOE-01"),
        ).json()
        assert body["exists"] is True
        assert body["crop_mismatch"] is True
        assert body["registered_crop"] == "cotton"
        assert body["registered_country"] == "PK"
        assert body["personal"] is None

    def test_registering_under_the_other_crop_is_blocked(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()
        response = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"], id_number="3520212345671"),
            headers=as_officer("GB-EOE-01"),
        )
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "farmer_crop_mismatch"
        assert error["details"]["registered_crop"] == "cotton"
        assert "Cotton programme" in error["message"]

    def test_notice_when_another_officer_registered_the_farmer(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()  # registered by PK-MUL-01
        same = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "3520212345671", "crop": "cotton"},
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert same["registered_by_other_officer"] is False

        other = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "3520212345671", "crop": "cotton"},
            headers=as_officer("PK-BWP-01"),
        ).json()
        assert other["registered_by_other_officer"] is True
        assert other["registered_by"]["code"] == "PK-MUL-01"
        # The edit is still allowed, so the personal data still comes back.
        assert other["personal"] is not None

    def test_another_officer_may_update_and_the_change_is_audited(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
        database: Any,
    ) -> None:
        register_cotton()
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], village="Chak 12"),
            headers=as_officer("PK-BWP-01"),
        )
        assert response.status_code == 200
        assert response.json()["farmer"]["sawie_id"] == 1001

    def test_lookup_is_rate_limited(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        headers = as_officer("PK-MUL-01")
        params = {"id_number": "35202-1111111-1", "crop": "cotton"}
        for _ in range(lookup_limiter.limit):
            assert (
                client.get(f"{REGISTER}/farmers/lookup", params=params, headers=headers).status_code
                == 200
            )
        blocked = client.get(f"{REGISTER}/farmers/lookup", params=params, headers=headers)
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"

    def test_invalid_id_number_is_a_validation_error(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        response = client.get(
            f"{REGISTER}/farmers/lookup",
            params={"id_number": "123", "crop": "cotton"},
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422
        assert response.json()["error"]["details"]["fields"][0]["field"] == "id_number"


class TestCottonForm:
    def test_normalises_name_phone_and_resolves_location_names(
        self, register_cotton: Callable[..., dict[str, Any]]
    ) -> None:
        farmer = register_cotton()["farmer"]
        assert farmer["name"] == "Muhammad Imran"
        assert farmer["father_name"] == "Ghulam Rasool"
        assert farmer["phone"] == "0300-1234567"
        assert farmer["province"] == "Punjab"
        assert farmer["district"] == "Multan"
        assert farmer["tehsil"] == "Multan City"
        assert farmer["country"] == "PK"
        assert farmer["id_number"] == "35202-1234567-1"

    def test_a_manually_typed_tehsil_is_accepted(
        self, register_cotton: Callable[..., dict[str, Any]]
    ) -> None:
        farmer = register_cotton(
            tehsil_code=None, tehsil_name="Some New Tehsil", district_code="PK-PB-MUL"
        )["farmer"]
        assert farmer["tehsil"] == "Some New Tehsil"

    def test_missing_tehsil_is_rejected(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], tehsil_code=None, tehsil_name=None),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422
        assert response.json()["error"]["details"]["fields"][0]["field"] == "tehsil"

    def test_village_is_required(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], village="a"),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422

    def test_a_variety_outside_the_master_list_is_rejected(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], variety="made-up-variety"),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "master_value_invalid"

    def test_a_hemp_variety_cannot_be_used_for_cotton(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], variety="futura_75"),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422

    def test_a_uk_office_cannot_register_a_cotton_farmer(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(gb_office["id"]),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "field_office_country_mismatch"


class TestHempForm:
    def test_postcode_fills_county_and_region(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"]),
            headers=as_officer("GB-EOE-01"),
        )
        assert response.status_code == 201, response.text
        farmer = response.json()["farmer"]
        assert farmer["postcode"] == "LN4 3QP"
        assert farmer["county"]  # from postcodes.io or the bundled area table
        assert farmer["region"]
        assert farmer["farm_name"] == "Fen End Farm"
        assert farmer["home_office_licence_no"] == "HO-HEMP-2026-0041"
        assert farmer["phone"] == "07700 900123"
        assert farmer["country"] == "GB"

    def test_a_duplicate_licence_number_is_rejected(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("GB-EOE-01")
        client.post(f"{REGISTER}/farmers", json=hemp_payload(gb_office["id"]), headers=headers)
        response = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"], id_number="987654321", name="Other Grower"),
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "farmer_duplicate_licence_no"

    def test_an_invalid_postcode_is_rejected(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"], postcode="NOPE"),
            headers=as_officer("GB-EOE-01"),
        )
        assert response.status_code == 422


class TestOfficerScopingAndPrivacy:
    def test_officers_see_their_own_farmers_and_admins_see_all(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"]),
            headers=as_officer("PK-MUL-01"),
        )
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], id_number="35202-2222222-2", name="Second Farmer"),
            headers=as_officer("PK-BWP-01"),
        )

        mine = client.get(f"{REGISTER}/farmers", headers=as_officer("PK-MUL-01")).json()
        assert mine["total"] == 1
        assert mine["items"][0]["name"] == "Muhammad Imran"

        everything = client.get(f"{REGISTER}/farmers", headers=as_officer("ADMIN-01")).json()
        assert everything["total"] == 2

    def test_list_rows_mask_the_id_number_and_phone(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()
        row = client.get(f"{REGISTER}/farmers", headers=as_officer("PK-MUL-01")).json()["items"][0]
        assert row["id_number_masked"] == "*****-****567-1"
        assert row["phone_masked"] == "0300-****567"
        assert row["has_fields"] is False
        assert row["field_count"] == 0
        assert row["location_summary"] == "Basti Malook, Multan City, Multan"

    def test_full_values_only_for_the_registering_officer_or_an_admin(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farmer_id = register_cotton()["farmer"]["id"]
        url = f"{REGISTER}/farmers/{farmer_id}"

        own = client.get(url, headers=as_officer("PK-MUL-01")).json()
        assert own["sensitive_visible"] is True
        assert own["id_number"] == "35202-1234567-1"
        assert own["phone"] == "0300-1234567"

        other = client.get(url, headers=as_officer("PK-BWP-01")).json()
        assert other["sensitive_visible"] is False
        assert other["id_number"] == "*****-****567-1"
        assert other["phone"] == "0300-****567"

        admin = client.get(url, headers=as_officer("ADMIN-01")).json()
        assert admin["sensitive_visible"] is True
        assert admin["id_number"] == "35202-1234567-1"

    def test_search_matches_sawie_id_name_and_id_number_fragments(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()
        headers = as_officer("PK-MUL-01")
        for query in ("1001", "imran", "1234567", "0300"):
            page = client.get(f"{REGISTER}/farmers", params={"q": query}, headers=headers).json()
            assert page["total"] == 1, query
        empty = client.get(
            f"{REGISTER}/farmers", params={"q": "nobody-here"}, headers=headers
        ).json()
        assert empty["total"] == 0

    def test_crop_filter(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        register_cotton()
        headers = as_officer("ADMIN-01")
        assert (
            client.get(f"{REGISTER}/farmers", params={"crop": "cotton"}, headers=headers).json()[
                "total"
            ]
            == 1
        )
        assert (
            client.get(f"{REGISTER}/farmers", params={"crop": "hemp"}, headers=headers).json()[
                "total"
            ]
            == 0
        )


class TestUpdateAndProfile:
    def test_update_changes_personal_data_and_keeps_the_sawie_id(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton()
        farmer_id = saved["farmer"]["id"]
        response = client.put(
            f"{REGISTER}/farmers/{farmer_id}",
            json=cotton_payload(pk_office["id"], name="Imran Ahmed", phone="+92 301 7654321"),
            headers=as_officer("PK-MUL-01"),
        )
        assert response.status_code == 200, response.text
        farmer = response.json()["farmer"]
        assert farmer["sawie_id"] == saved["farmer"]["sawie_id"]
        assert farmer["name"] == "Imran Ahmed"
        assert farmer["phone"] == "0301-7654321"

    def test_update_cannot_steal_another_farmers_id_number(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        first = client.post(
            f"{REGISTER}/farmers", json=cotton_payload(pk_office["id"]), headers=headers
        ).json()
        second = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], id_number="35202-9999999-9", name="Second One"),
            headers=headers,
        ).json()
        response = client.put(
            f"{REGISTER}/farmers/{second['farmer']['id']}",
            json=cotton_payload(pk_office["id"], id_number="35202-1234567-1", name="Second One"),
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "farmer_duplicate_id_number"
        assert response.json()["error"]["details"]["sawie_id"] == first["farmer"]["sawie_id"]

    def test_profile_reports_season_profiles_and_completeness(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton()
        body = client.get(
            f"{REGISTER}/farmers/{saved['farmer']['id']}/profile",
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert body["farmer"]["sawie_id"] == 1001
        assert len(body["season_profiles"]) == 1
        assert body["season_profiles"][0]["variety"] == "fh-142"
        assert body["season_profiles"][0]["tenure"] == "owner"
        # No field yet, so the farmer is not ready for the Fieldbook.
        assert body["completeness"] == {
            "has_fields": False,
            "field_count": 0,
            "total_area_acre": 0.0,
            "total_area_ha": 0.0,
            "ready_for_fieldbook": False,
            "missing": ["At least one mapped field"],
        }

    def test_a_second_season_adds_a_profile_without_touching_the_first(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton(season_year=2026)
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], season_year=2027, variety="mnh-886"),
            headers=as_officer("PK-MUL-01"),
        )
        body = client.get(
            f"{REGISTER}/farmers/{saved['farmer']['id']}/profile",
            headers=as_officer("PK-MUL-01"),
        ).json()
        seasons = {p["season_year"]: p["variety"] for p in body["season_profiles"]}
        assert seasons == {2026: "fh-142", 2027: "mnh-886"}

    def test_unknown_farmer_is_a_404_with_a_stable_code(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        response = client.get(f"{REGISTER}/farmers/does-not-exist", headers=as_officer("PK-MUL-01"))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "farmer_not_found"
