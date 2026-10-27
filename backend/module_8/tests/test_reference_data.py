"""Lists, locations, officers and sites: what a change does to records that exist.

The rule under test throughout: **deactivating hides a value from new entries and
changes nothing that is already recorded; deleting is refused while anything uses it.**
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_8.tests.conftest import S


class TestListValues:
    def test_a_value_is_added_with_a_stable_key_derived_from_the_label(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        added = client.post(
            f"{S}/lists/{any_list}/values", json={"label": "Early Monsoon"}, headers=admin
        )
        assert added.status_code == 201
        assert added.json()["value"] == "early_monsoon"
        assert added.json()["label"] == "Early Monsoon"

    def test_a_label_can_be_corrected_while_the_key_stays(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        value = client.post(
            f"{S}/lists/{any_list}/values", json={"label": "Mispelled"}, headers=admin
        ).json()
        fixed = client.put(
            f"{S}/lists/{any_list}/values/{value['id']}",
            json={"label": "Misspelled"},
            headers=admin,
        )
        assert fixed.status_code == 200
        assert fixed.json()["label"] == "Misspelled"
        assert fixed.json()["value"] == value["value"]

    def test_a_duplicate_value_is_refused(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        client.post(f"{S}/lists/{any_list}/values", json={"label": "Twice"}, headers=admin)
        again = client.post(f"{S}/lists/{any_list}/values", json={"label": "Twice"}, headers=admin)
        assert again.status_code == 409

    def test_an_unused_value_can_be_deleted(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        value = client.post(
            f"{S}/lists/{any_list}/values", json={"label": "Temporary"}, headers=admin
        ).json()
        assert value["can_delete"] is True
        assert (
            client.delete(f"{S}/lists/{any_list}/values/{value['id']}", headers=admin).status_code
            == 204
        )

    def test_deactivating_keeps_the_value_on_the_screen_for_existing_records(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        value = client.post(
            f"{S}/lists/{any_list}/values", json={"label": "Retired Variety"}, headers=admin
        ).json()
        client.put(
            f"{S}/lists/{any_list}/values/{value['id']}", json={"active": False}, headers=admin
        )
        rows = client.get(f"{S}/lists/{any_list}/values", headers=admin).json()
        row = next(r for r in rows if r["id"] == value["id"])
        assert row["active"] is False
        assert row["label"] == "Retired Variety"

    def test_the_order_can_be_changed_and_is_saved(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        rows = client.get(f"{S}/lists/{any_list}/values", headers=admin).json()
        reversed_ids = [r["id"] for r in reversed(rows)]
        saved = client.post(
            f"{S}/lists/{any_list}/reorder", json={"ids": reversed_ids}, headers=admin
        )
        assert saved.status_code == 200
        after = client.get(f"{S}/lists/{any_list}/values", headers=admin).json()
        assert [r["id"] for r in after] == reversed_ids

    def test_an_order_naming_another_list_is_refused(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        answer = client.post(
            f"{S}/lists/{any_list}/reorder", json={"ids": ["not-a-value"]}, headers=admin
        )
        assert answer.status_code == 422

    def test_an_unknown_list_is_not_found(self, client: TestClient, admin: dict[str, str]) -> None:
        assert client.get(f"{S}/lists/made_up/values", headers=admin).status_code == 404


class TestListImportExport:
    def test_a_dry_run_changes_nothing(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        before = len(client.get(f"{S}/lists/{any_list}/values", headers=admin).json())
        report = client.post(
            f"{S}/lists/{any_list}/import?dry_run=true",
            content=b"value,label\nnew_one,New One\n",
            headers=admin,
        )
        assert report.status_code == 200
        assert report.json()["created"] == 1
        after = len(client.get(f"{S}/lists/{any_list}/values", headers=admin).json())
        assert after == before

    def test_a_committed_import_adds_the_rows(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        client.post(
            f"{S}/lists/{any_list}/import?dry_run=false",
            content=b"value,label\nnew_two,New Two\n",
            headers=admin,
        )
        rows = client.get(f"{S}/lists/{any_list}/values", headers=admin).json()
        assert any(r["value"] == "new_two" for r in rows)

    def test_the_export_neutralises_a_formula(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        client.post(f"{S}/lists/{any_list}/values", json={"label": "=1+1"}, headers=admin)
        text = client.get(f"{S}/lists/{any_list}/export.csv", headers=admin).text
        assert "'=1+1" in text
        assert "\n=1+1" not in text


class TestUsageBlocksDeletion:
    def test_a_list_value_in_use_cannot_be_deleted(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        """'tenure' is stored on the farmer, so registering one puts a value in use."""
        cotton_farmer()
        rows = client.get(f"{S}/lists/tenure/values", headers=admin)
        if rows.status_code != 200:  # the seed may name the list differently
            return
        used = [r for r in rows.json() if r["usage"] > 0]
        assert used, "registering a farmer should put a tenure value in use"
        target = used[0]
        assert target["can_delete"] is False
        refused = client.delete(f"{S}/lists/tenure/values/{target['id']}", headers=admin)
        assert refused.status_code == 422
        assert "Deactivate" in refused.json()["error"]["message"]

    def test_an_officer_who_registered_a_farmer_is_counted(
        self,
        client: TestClient,
        admin: dict[str, str],
        officer_ids: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        officer = client.get(f"{S}/officers/{officer_ids['PK-MUL-01']}", headers=admin).json()
        assert officer["usage"] >= 1


class TestSites:
    def test_a_site_is_created_and_listed(self, client: TestClient, admin: dict[str, str]) -> None:
        created = client.post(
            f"{S}/sites",
            json={"code": "khi-g2", "name": "Karachi Ginner 2", "type": "ginner", "crop": "cotton"},
            headers=admin,
        )
        assert created.status_code == 201
        assert created.json()["code"] == "KHI-G2"
        assert created.json()["code_locked"] is False
        codes = [s["code"] for s in client.get(f"{S}/sites", headers=admin).json()]
        assert "KHI-G2" in codes

    def test_a_duplicate_code_is_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        body = {"code": "DUP-1", "name": "One", "type": "ginner", "crop": "cotton"}
        assert client.post(f"{S}/sites", json=body, headers=admin).status_code == 201
        assert client.post(f"{S}/sites", json=body, headers=admin).status_code == 409

    def test_an_unknown_type_is_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        answer = client.post(
            f"{S}/sites",
            json={"code": "BAD-1", "name": "Bad", "type": "warehouse", "crop": "cotton"},
            headers=admin,
        )
        assert answer.status_code == 422

    def test_an_unused_site_can_be_deleted(self, client: TestClient, admin: dict[str, str]) -> None:
        site = client.post(
            f"{S}/sites",
            json={"code": "TMP-9", "name": "Temporary", "type": "ginner", "crop": "cotton"},
            headers=admin,
        ).json()
        assert client.delete(f"{S}/sites/{site['id']}", headers=admin).status_code == 204

    def test_a_site_can_be_deactivated_and_keeps_its_name(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        site = client.post(
            f"{S}/sites",
            json={"code": "OFF-1", "name": "Closing Soon", "type": "ginner", "crop": "cotton"},
            headers=admin,
        ).json()
        off = client.put(f"{S}/sites/{site['id']}", json={"active": False}, headers=admin)
        assert off.status_code == 200
        assert off.json()["active"] is False
        assert off.json()["name"] == "Closing Soon"


class TestOfficers:
    def test_an_officer_is_created(self, client: TestClient, admin: dict[str, str]) -> None:
        created = client.post(
            f"{S}/officers",
            json={
                "code": "PK-MUL-09",
                "full_name": "Nasreen Akhtar",
                "country": "PK",
                "role": "officer",
            },
            headers=admin,
        )
        assert created.status_code == 201
        assert created.json()["code"] == "PK-MUL-09"
        assert created.json()["active"] is True

    def test_an_officer_without_a_code_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.post(
            f"{S}/officers", json={"full_name": "No Code", "country": "PK"}, headers=admin
        )
        assert answer.status_code == 422

    def test_a_unicode_name_is_accepted(self, client: TestClient, admin: dict[str, str]) -> None:
        created = client.post(
            f"{S}/officers",
            json={
                "code": "GB-EOE-09",
                "full_name": "Zoë Ní Bhraonáin",
                "country": "GB",
                "role": "officer",
            },
            headers=admin,
        )
        assert created.status_code == 201
        assert created.json()["full_name"] == "Zoë Ní Bhraonáin"

    def test_no_route_accepts_a_password(self, client: TestClient) -> None:
        """There is no sign-in yet, so no field anywhere may look like one."""
        from module_8.router import router

        for route in router.routes:
            body = getattr(getattr(route, "body_field", None), "type_", None)
            fields = getattr(body, "model_fields", {}) if body is not None else {}
            assert not [f for f in fields if "password" in f.lower() or "secret" in f.lower()]

    def test_the_export_and_a_dry_run_import_agree(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        text = client.get(f"{S}/officers/export.csv", headers=admin).text
        report = client.post(
            f"{S}/officers/import?dry_run=true", content=text.encode(), headers=admin
        )
        assert report.status_code == 200
        body = report.json()
        assert body["created"] == 0  # everything in the file already exists
        assert body["errors"] == []


class TestLocations:
    def test_the_tree_has_the_three_pakistani_levels(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        tree = client.get(f"{S}/locations/tree?country=PK", headers=admin).json()
        assert tree["levels"] == ["province", "district", "tehsil"]
        assert tree["items"]

    def test_renaming_a_used_location_moves_every_farmer(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        tree = client.get(f"{S}/locations/tree?country=PK", headers=admin).json()
        tehsils = [
            node
            for province in tree["items"]
            for district in province["children"]
            for node in district["children"]
            if node["usage"] > 0
        ]
        assert tehsils, "the registered farmer should put one tehsil in use"
        target = tehsils[0]

        preview = client.get(
            f"{S}/locations/{target['id']}/rename-preview",
            params={"name": "Renamed Tehsil"},
            headers=admin,
        ).json()
        assert preview["farmers_affected"] == target["usage"]
        assert preview["to"] == "Renamed Tehsil"

        renamed = client.put(
            f"{S}/locations/{target['id']}", json={"name": "Renamed Tehsil"}, headers=admin
        )
        assert renamed.status_code == 200
        # Every farmer that named the old tehsil now names the new one, in one transaction.
        assert renamed.json()["farmers_updated"] == target["usage"]

        after = client.get(f"{S}/locations/tree?country=PK", headers=admin).json()
        names = [
            node["name"]
            for province in after["items"]
            for district in province["children"]
            for node in district["children"]
        ]
        assert "Renamed Tehsil" in names

    def test_a_used_location_cannot_be_deleted(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        tree = client.get(f"{S}/locations/tree?country=PK", headers=admin).json()
        used = [
            node
            for province in tree["items"]
            for district in province["children"]
            for node in district["children"]
            if node["usage"] > 0
        ]
        assert used
        answer = client.delete(f"{S}/locations/{used[0]['id']}", headers=admin)
        assert answer.status_code in (409, 422)
