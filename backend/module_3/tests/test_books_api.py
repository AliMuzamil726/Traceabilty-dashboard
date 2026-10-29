"""Fieldbook API: opening, saving, repeatable entries, locking, submit and scoping."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from module_3.tests.conftest import FB, cotton_steps, hemp_steps, vh

Farm = dict[str, Any]


class TestOpening:
    def test_opening_creates_a_draft_with_the_crop_schema(
        self, client: TestClient, make_farm: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        r = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": 2026},
            headers=farm["headers"],
        )
        assert r.status_code == 201
        book = r.json()
        assert book["crop"] == "cotton"
        assert book["status"] == "draft"
        assert book["locked"] is False
        assert book["schema_version"] == "2026.1"
        assert book["field_code"] == farm["field"]["field_id"]
        assert next(s["key"] for s in book["steps"]) == "field_info"
        assert len(book["steps"]) == 11
        assert book["defaults"]["field.area_acre"] == pytest.approx(9.88, rel=0.01)
        assert book["defaults"]["season.variety"] == "fh-142"

    def test_a_second_open_returns_the_same_book(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        first = open_book(farm, 2026)
        r = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": 2026},
            headers=farm["headers"],
        )
        assert r.status_code == 200
        assert r.json()["id"] == first["id"]

    def test_each_field_and_each_season_gets_its_own_book(
        self, client: TestClient, make_farm: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton", fields=2)
        ids = set()
        for field in farm["fields"]:
            for season in (2025, 2026):
                r = client.post(
                    f"{FB}/books",
                    json={"field_id": field["id"], "season_year": season},
                    headers=farm["headers"],
                )
                ids.add(r.json()["id"])
        assert len(ids) == 4

    def test_hemp_farmers_get_the_hemp_schema(
        self, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        book = open_book(make_farm("hemp"))
        assert book["crop"] == "hemp"
        assert len(book["steps"]) == 9
        assert book["defaults"]["farmer.licence"].startswith("HO-TEST-")

    def test_the_crop_cannot_be_overridden(
        self, client: TestClient, make_farm: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        r = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": 2026, "crop": "hemp"},
            headers=farm["headers"],
        )
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "fieldbook_crop_mismatch"

    def test_unknown_field_is_a_404(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        r = client.post(
            f"{FB}/books",
            json={"field_id": "nope", "season_year": 2026},
            headers=as_officer("PK-MUL-01"),
        )
        assert r.status_code == 404


class TestScoping:
    def test_another_officer_cannot_open_or_read(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        other = as_officer("PK-BWP-01")
        r = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": 2026},
            headers=other,
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "fieldbook_forbidden"
        assert client.get(f"{FB}/books/{book['id']}", headers=other).status_code == 403
        assert (
            client.put(
                f"{FB}/books/{book['id']}/steps/energy",
                json={"data": cotton_steps()["energy"]},
                headers=other,
            ).status_code
            == 403
        )

    def test_an_administrator_can_open_any_farmer(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        book = open_book(make_farm("cotton"))
        assert (
            client.get(f"{FB}/books/{book['id']}", headers=as_officer("ADMIN-01")).status_code
            == 200
        )

    def test_officer_selector_lists_only_yourself_unless_admin(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        mine = client.get(f"{FB}/selectors/officers", headers=as_officer("PK-MUL-01")).json()
        assert [o["code"] for o in mine] == ["PK-MUL-01"]
        every = client.get(f"{FB}/selectors/officers", headers=as_officer("ADMIN-01")).json()
        seeded = client.get("/api/v1/officers", params={"page_size": 200}).json()["items"]
        assert {o["code"] for o in every} == {o["code"] for o in seeded}
        assert {"PK-MUL-01", "STAFF-01", "ADMIN-01"} <= {o["code"] for o in every}

    def test_farmer_selector_lists_only_that_officers_farmers(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        officer_ids: dict[str, str],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01")
        make_farm("cotton", officer="PK-BWP-01")
        mine = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-MUL-01"]},
            headers=as_officer("PK-MUL-01"),
        )
        assert len(mine.json()) == 1
        # An ordinary officer cannot browse another officer's farmers.
        peek = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-BWP-01"]},
            headers=as_officer("PK-MUL-01"),
        )
        assert peek.status_code == 403
        admin = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-BWP-01"]},
            headers=as_officer("ADMIN-01"),
        )
        assert len(admin.json()) == 1

    def test_farmer_search_matches_sawie_id_and_name(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        officer_ids: dict[str, str],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton")
        params = {"officer_id": officer_ids["PK-MUL-01"]}
        h = as_officer("PK-MUL-01")
        assert (
            len(
                client.get(
                    f"{FB}/selectors/farmers",
                    params={**params, "q": str(farm["farmer"]["sawie_id"])},
                    headers=h,
                ).json()
            )
            == 1
        )
        assert (
            len(
                client.get(
                    f"{FB}/selectors/farmers", params={**params, "q": "imran"}, headers=h
                ).json()
            )
            == 1
        )
        assert (
            client.get(
                f"{FB}/selectors/farmers", params={**params, "q": "nobody"}, headers=h
            ).json()
            == []
        )

    def test_selectors_report_fieldbook_status(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        officer_ids: dict[str, str],
    ) -> None:
        farm = make_farm("cotton", fields=2)
        before = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-MUL-01"]},
            headers=farm["headers"],
        ).json()[0]
        assert before["fieldbook_status"] == "not_started"
        assert before["field_count"] == 2
        book = open_book(farm)
        after = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-MUL-01"]},
            headers=farm["headers"],
        ).json()[0]
        assert after["fieldbook_status"] == "in_progress"
        fields = client.get(
            f"{FB}/selectors/fields",
            params={"farmer_id": farm["farmer"]["id"]},
            headers=farm["headers"],
        ).json()
        statuses = {f["id"]: f["fieldbook_status"] for f in fields["items"]}
        assert statuses[farm["field"]["id"]] == "draft"
        assert statuses[farm["fields"][1]["id"]] == "none"
        assert fields["farmer"]["crop"] == "cotton"
        assert book["id"] in {f["fieldbook_id"] for f in fields["items"]}

    def test_a_farmer_with_no_field_shows_as_such(
        self, client: TestClient, make_farm: Callable[..., Farm], officer_ids: dict[str, str]
    ) -> None:
        farm = make_farm("cotton", fields=1)
        client.delete(f"/api/v1/register/fields/{farm['field']['id']}", headers=farm["headers"])
        row = client.get(
            f"{FB}/selectors/farmers",
            params={"officer_id": officer_ids["PK-MUL-01"]},
            headers=farm["headers"],
        ).json()[0]
        assert row["fieldbook_status"] == "no_field"


class TestSaving:
    def test_saving_a_single_step_marks_it_complete_and_advances(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        r = client.put(
            f"{FB}/books/{book['id']}/steps/field_info",
            json={"data": cotton_steps()["field_info"]},
            headers=vh(book, farm["headers"]),
        )
        assert r.status_code == 200, r.text
        state = r.json()["book"]
        status = {s["key"]: s["status"] for s in state["steps"]}
        assert status["field_info"] == "complete"
        assert state["current_step"] == "land_preparation"
        assert state["version"] == book["version"] + 1

    def test_validation_errors_come_back_per_field(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        r = client.put(
            f"{FB}/books/{book['id']}/steps/field_info",
            json={"data": {"area_sown": 999}},
            headers=farm["headers"],
        )
        assert r.status_code == 422
        fields = {f["field"] for f in r.json()["error"]["details"]["fields"]}
        assert {"crop_season", "soil_texture", "drainage_status", "area_sown"} <= fields

    def test_area_sown_is_capped_against_the_real_field(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        data = dict(cotton_steps()["field_info"], area_sown=11)  # field is about 9.9 acres
        r = client.put(
            f"{FB}/books/{book['id']}/steps/field_info",
            json={"data": data},
            headers=farm["headers"],
        )
        assert r.status_code == 422

    def test_repeatable_entries_add_update_and_delete(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        url = f"{FB}/books/{book['id']}/steps/irrigation/entries"
        entry = cotton_steps()["irrigation"][0]
        one = client.post(url, json={"data": entry}, headers=farm["headers"]).json()["book"]
        two = client.post(
            url, json={"data": dict(entry, water_applied=60)}, headers=farm["headers"]
        ).json()["book"]
        step = next(s for s in two["steps"] if s["key"] == "irrigation")
        assert [e["entry_index"] for e in step["entries"]] == [0, 1]
        assert step["status"] == "complete"
        assert one["version"] < two["version"]

        upd = client.put(
            f"{url}/1", json={"data": dict(entry, water_applied=90)}, headers=farm["headers"]
        )
        assert upd.status_code == 200
        step = next(s for s in upd.json()["book"]["steps"] if s["key"] == "irrigation")
        assert step["entries"][1]["data"]["water_applied"] == 90

        client.delete(f"{url}/0", headers=farm["headers"])
        last = client.delete(f"{url}/1", headers=farm["headers"]).json()
        step = next(s for s in last["steps"] if s["key"] == "irrigation")
        assert step["entries"] == []
        assert step["status"] == "not_started"

    def test_hidden_fields_are_not_stored(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        entry = dict(cotton_steps()["irrigation"][0], source="canal", electricity_used=5)
        state = client.post(
            f"{FB}/books/{book['id']}/steps/irrigation/entries",
            json={"data": entry},
            headers=farm["headers"],
        ).json()["book"]
        saved = next(s for s in state["steps"] if s["key"] == "irrigation")["entries"][0]["data"]
        assert "diesel_used" not in saved
        assert "electricity_used" not in saved

    def test_single_and_repeatable_endpoints_are_not_interchangeable(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        a = client.put(
            f"{FB}/books/{book['id']}/steps/irrigation", json={"data": {}}, headers=farm["headers"]
        )
        assert a.json()["error"]["code"] == "fieldbook_step_repeatable"
        b = client.post(
            f"{FB}/books/{book['id']}/steps/energy/entries",
            json={"data": {}},
            headers=farm["headers"],
        )
        assert b.json()["error"]["code"] == "fieldbook_step_single"

    def test_steps_of_the_other_crop_are_refused(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        r = client.put(
            f"{FB}/books/{book['id']}/steps/retting", json={"data": {}}, headers=farm["headers"]
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "fieldbook_step_unknown"
        sent = client.put(
            f"{FB}/books/{book['id']}/steps/energy",
            json={"data": cotton_steps()["energy"], "crop": "hemp"},
            headers=farm["headers"],
        )
        assert sent.status_code == 409
        assert sent.json()["error"]["code"] == "fieldbook_crop_mismatch"

    def test_a_stale_version_is_refused(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        stale = vh(book, farm["headers"])
        client.put(
            f"{FB}/books/{book['id']}/steps/energy",
            json={"data": cotton_steps()["energy"]},
            headers=stale,
        )
        # A second officer still holding the old version.
        r = client.put(
            f"{FB}/books/{book['id']}/steps/transport",
            json={"data": cotton_steps()["transport"]},
            headers=stale,
        )
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "fieldbook_stale"
        assert r.json()["error"]["details"]["current"] == book["version"] + 1

    def test_warnings_are_returned_and_listed_on_the_book(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        entry = dict(cotton_steps()["harvest"][0], moisture=15)
        r = client.post(
            f"{FB}/books/{book['id']}/steps/harvest/entries",
            json={"data": entry},
            headers=farm["headers"],
        ).json()
        assert [w["field"] for w in r["warnings"]] == ["moisture"]
        assert any(w["field"] == "moisture" for w in r["book"]["warnings"])

    def test_cross_step_errors_appear_when_a_later_change_breaks_an_earlier_entry(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        client.post(
            f"{FB}/books/{book['id']}/steps/harvest/entries",
            json={"data": cotton_steps()["harvest"][0]},
            headers=farm["headers"],
        )
        # Sowing recorded after the picking already saved: the picking is now invalid.
        sowing = dict(cotton_steps()["sowing"], sowing_date=date.today().isoformat())
        state = client.put(
            f"{FB}/books/{book['id']}/steps/sowing", json={"data": sowing}, headers=farm["headers"]
        ).json()["book"]
        assert any(
            e["step_key"] == "harvest" and e["field"] == "picking_date" for e in state["errors"]
        )

    def test_a_duplicate_picking_number_is_refused(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        url = f"{FB}/books/{book['id']}/steps/harvest/entries"
        client.post(url, json={"data": cotton_steps()["harvest"][0]}, headers=farm["headers"])
        r = client.post(url, json={"data": cotton_steps()["harvest"][0]}, headers=farm["headers"])
        assert r.status_code == 422
        # Re-saving the same entry with its own number is fine.
        assert (
            client.put(
                f"{url}/0", json={"data": cotton_steps()["harvest"][0]}, headers=farm["headers"]
            ).status_code
            == 200
        )

    def test_computed_hemp_values_are_stored(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("hemp")
        book = open_book(farm)
        state = client.put(
            f"{FB}/books/{book['id']}/steps/retting",
            json={"data": hemp_steps()["retting"]},
            headers=farm["headers"],
        ).json()["book"]
        data = next(s for s in state["steps"] if s["key"] == "retting")["entries"][0]["data"]
        assert data["number_of_turns"] == 2
        assert data["days_in_swath"] == 13


class TestNotApplicable:
    def test_only_optional_steps_can_be_marked(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        ok = client.post(
            f"{FB}/books/{book['id']}/steps/weed_management/not-applicable",
            json={"not_applicable": True},
            headers=farm["headers"],
        )
        assert ok.status_code == 200
        assert {s["key"]: s["status"] for s in ok.json()["steps"]}[
            "weed_management"
        ] == "not_applicable"
        no = client.post(
            f"{FB}/books/{book['id']}/steps/irrigation/not-applicable",
            json={"not_applicable": True},
            headers=farm["headers"],
        )
        assert no.json()["error"]["code"] == "fieldbook_step_required"

    def test_a_step_with_entries_cannot_be_marked(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        client.post(
            f"{FB}/books/{book['id']}/steps/weed_management/entries",
            json={"data": cotton_steps()["weed_management"][0]},
            headers=farm["headers"],
        )
        r = client.post(
            f"{FB}/books/{book['id']}/steps/weed_management/not-applicable",
            json={"not_applicable": True},
            headers=farm["headers"],
        )
        assert r.json()["error"]["code"] == "fieldbook_step_has_entries"

    def test_adding_an_entry_after_marking_clears_the_mark(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        client.post(
            f"{FB}/books/{book['id']}/steps/weed_management/not-applicable",
            json={"not_applicable": True},
            headers=farm["headers"],
        )
        state = client.post(
            f"{FB}/books/{book['id']}/steps/weed_management/entries",
            json={"data": cotton_steps()["weed_management"][0]},
            headers=farm["headers"],
        ).json()["book"]
        assert {s["key"]: s["status"] for s in state["steps"]}["weed_management"] == "complete"


class TestSubmitAndLock:
    def test_submit_refuses_an_incomplete_book_and_names_the_steps(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        fill: Callable[..., Farm],
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        state = fill(book, farm["headers"], cotton_steps(), skip=("energy", "pest_disease"))
        r = client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "fieldbook_incomplete"
        assert r.json()["error"]["details"]["missing_steps"] == ["pest_disease", "energy"]
        assert state["missing_steps"] == ["pest_disease", "energy"]

    def test_an_optional_step_must_be_answered_one_way_or_the_other(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        fill: Callable[..., Farm],
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        steps = cotton_steps()
        fill(book, farm["headers"], steps, skip=("pest_disease",))
        client.post(
            f"{FB}/books/{book['id']}/steps/pest_disease/not-applicable",
            json={"not_applicable": True},
            headers=farm["headers"],
        )
        assert (
            client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"]).status_code
            == 200
        )

    def test_blocking_errors_stop_submit(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        fill: Callable[..., Farm],
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        steps = cotton_steps()
        fill(book, farm["headers"], steps)
        late = dict(steps["sowing"], sowing_date=date.today().isoformat())
        client.put(
            f"{FB}/books/{book['id']}/steps/sowing", json={"data": late}, headers=farm["headers"]
        )
        r = client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
        assert r.json()["error"]["code"] == "fieldbook_has_errors"

    @pytest.mark.parametrize("crop", ["cotton", "hemp"])
    def test_a_complete_book_submits_and_locks(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        fill: Callable[..., Farm],
        crop: str,
    ) -> None:
        farm = make_farm(crop)
        book = open_book(farm)
        state = fill(book, farm["headers"], cotton_steps() if crop == "cotton" else hemp_steps())
        assert state["missing_steps"] == []
        r = client.post(f"{FB}/books/{book['id']}/submit", headers=vh(state, farm["headers"]))
        assert r.status_code == 200, r.text
        done = r.json()
        assert done["status"] == "submitted"
        assert done["locked"] is True
        assert done["submitted_at"]

    def test_every_mutation_after_submit_is_refused(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        fill: Callable[..., Farm],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        steps = cotton_steps()
        fill(book, farm["headers"], steps)
        client.post(f"{FB}/books/{book['id']}/submit", headers=farm["headers"])
        base = f"{FB}/books/{book['id']}"
        attempts = [
            client.put(
                f"{base}/steps/energy", json={"data": steps["energy"]}, headers=farm["headers"]
            ),
            client.post(
                f"{base}/steps/irrigation/entries",
                json={"data": steps["irrigation"][0]},
                headers=farm["headers"],
            ),
            client.put(
                f"{base}/steps/irrigation/entries/0",
                json={"data": steps["irrigation"][0]},
                headers=farm["headers"],
            ),
            client.delete(f"{base}/steps/irrigation/entries/0", headers=farm["headers"]),
            client.post(
                f"{base}/steps/weed_management/not-applicable",
                json={"not_applicable": True},
                headers=farm["headers"],
            ),
            client.post(
                f"{base}/photos",
                files={"files": ("a.png", b"x", "image/png")},
                headers=farm["headers"],
            ),
            client.delete(f"{base}/photos/whatever", headers=farm["headers"]),
            client.post(f"{base}/submit", headers=farm["headers"]),
            client.delete(base, headers=farm["headers"]),
            client.delete(base, headers=as_officer("ADMIN-01")),  # not even an administrator
        ]
        for r in attempts:
            assert r.status_code == 409, r.text
            assert r.json()["error"]["code"] == "fieldbook_locked"
        # Reading still works.
        assert client.get(base, headers=farm["headers"]).json()["locked"] is True
        assert client.get(f"{base}/timeline", headers=farm["headers"]).status_code == 200


class TestDeleteDraft:
    def test_the_creator_can_delete_a_draft(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        assert client.delete(f"{FB}/books/{book['id']}", headers=farm["headers"]).status_code == 204
        assert client.get(f"{FB}/books/{book['id']}", headers=farm["headers"]).status_code == 404
        # Opening again starts a fresh draft.
        again = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": date.today().year},
            headers=farm["headers"],
        )
        assert again.status_code == 201

    def test_list_books_is_scoped(
        self,
        client: TestClient,
        make_farm: Callable[..., Farm],
        open_book: Callable[..., Farm],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        open_book(make_farm("cotton", officer="PK-MUL-01"))
        open_book(make_farm("cotton", officer="PK-BWP-01"))
        assert client.get(f"{FB}/books", headers=as_officer("PK-MUL-01")).json()["total"] == 1
        assert client.get(f"{FB}/books", headers=as_officer("ADMIN-01")).json()["total"] == 2
        assert (
            client.get(
                f"{FB}/books", params={"status": "submitted"}, headers=as_officer("ADMIN-01")
            ).json()["total"]
            == 0
        )


class TestTimeline:
    def test_every_saved_entry_appears_newest_first(
        self, client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
    ) -> None:
        farm = make_farm("cotton")
        book = open_book(farm)
        client.put(
            f"{FB}/books/{book['id']}/steps/energy",
            json={"data": cotton_steps()["energy"]},
            headers=farm["headers"],
        )
        client.post(
            f"{FB}/books/{book['id']}/steps/harvest/entries",
            json={"data": cotton_steps()["harvest"][0]},
            headers=farm["headers"],
        )
        items = client.get(f"{FB}/books/{book['id']}/timeline", headers=farm["headers"]).json()[
            "items"
        ]
        assert [i["kind"] for i in items] == ["entry", "entry", "created"]
        assert items[0]["step_key"] == "harvest"
        assert (
            items[0]["summary"]
            == f"1st picking on {cotton_steps()['harvest'][0]['picking_date']}, 12 maunds per acre"
        )
        assert items[0]["officer_name"] == "Muhammad Imran Khan"
        assert items[1]["summary"] == "180 L diesel, 0 kWh"
