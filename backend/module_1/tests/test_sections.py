"""Every dashboard section against seeded multi-module data."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_1.tests.conftest import DASH, YEAR, cotton_picking, stage


class TestOverview:
    def test_kpis_count_what_was_registered(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        make_farm("cotton", sown=10)
        make_farm("hemp", sown=100)
        body = dashboard("overview", as_officer("ADMIN-01"), scope="all")

        assert body["kpis"]["farmers"] == {"total": 3, "cotton": 2, "hemp": 1}
        assert body["kpis"]["fields"]["total"] == 3
        assert body["kpis"]["fields"]["area"] > 0
        assert body["kpis"]["fieldbooks"]["started"] == 3

    def test_crop_filter_narrows_every_figure(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        make_farm("hemp", sown=100)
        admin = as_officer("ADMIN-01")

        cotton = dashboard("overview", admin, scope="all", crop="cotton")
        hemp = dashboard("overview", admin, scope="all", crop="hemp")

        assert cotton["kpis"]["farmers"]["total"] == 1
        assert cotton["units"] == {"area": "acre", "mass": "maund"}
        assert hemp["kpis"]["farmers"]["total"] == 1
        assert hemp["units"] == {"area": "ha", "mass": "t"}

    def test_maunds_only_for_cotton(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        deliver(make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")), weighbridge=800)
        admin = as_officer("ADMIN-01")

        cotton = dashboard("overview", admin, scope="all", crop="cotton", range="season")
        both = dashboard("overview", admin, scope="all", range="season")

        assert cotton["kpis"]["delivered"]["kg"] == 800
        assert cotton["kpis"]["delivered"]["maunds"] == 20
        assert both["kpis"]["delivered"]["maunds"] is None

    def test_scope_mine_shows_only_the_officers_own_work(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140, officer="PK-MUL-01")
        make_farm("cotton", sown=140, officer="PK-MUL-02")
        headers = as_officer("PK-MUL-01")

        mine = dashboard("overview", headers, scope="mine", crop="cotton")
        every = dashboard("overview", headers, scope="all", crop="cotton")

        assert mine["kpis"]["farmers"]["total"] == 1
        assert every["kpis"]["farmers"]["total"] == 2

    def test_officers_default_to_their_own_work_and_admins_to_all(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01")
        make_farm("cotton", officer="PK-MUL-02")

        assert dashboard("overview", as_officer("PK-MUL-01"))["scope"] == "mine"
        assert dashboard("overview", as_officer("PK-MUL-01"))["kpis"]["farmers"]["total"] == 1
        assert dashboard("overview", as_officer("ADMIN-01"))["scope"] == "all"
        assert dashboard("overview", as_officer("ADMIN-01"))["kpis"]["farmers"]["total"] == 2


class TestPipeline:
    def test_stages_follow_the_chain(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        make_farm("cotton", sown=10)
        delivery = deliver(farm, weighbridge=1000)
        heap_with_bales([delivery], bales=2)

        body = dashboard("pipeline", as_officer("ADMIN-01"), scope="all", crop="cotton")

        assert stage(body, "farmers")["count"] == 2
        assert stage(body, "fields")["count"] == 2
        assert stage(body, "fieldbooks")["count"] == 2
        assert stage(body, "harvest")["count"] == 1
        assert stage(body, "deliveries")["count"] == 1
        assert stage(body, "bales")["count"] == 2

    def test_first_stage_has_no_conversion_and_the_rest_do(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        make_farm("cotton")  # a field but no fieldbook
        body = dashboard("pipeline", as_officer("ADMIN-01"), scope="all", crop="cotton")

        assert stage(body, "farmers")["conversion_pct"] is None
        assert stage(body, "fields")["conversion_pct"] == 100.0
        assert stage(body, "fieldbooks")["conversion_pct"] == 50.0

    def test_every_stage_links_to_a_module(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("pipeline", as_officer("ADMIN-01"), crop="cotton")
        paths = {s["key"]: s["link"]["path"] for s in body["stages"]}

        assert paths == {
            "farmers": "/register",
            "fields": "/register",
            "fieldbooks": "/fieldbook",
            "harvest": "/radar",
            "deliveries": "/deliveries",
            "bales": "/heaps",
            "scans": "/qr",
        }
        harvest = stage(body, "harvest")["link"]["params"]
        assert harvest["status"] == "ready"
        assert harvest["crop"] == "cotton"
        assert harvest["season"] == str(YEAR)

    def test_every_stage_explains_what_it_counts(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("pipeline", as_officer("ADMIN-01"))
        assert all(s["caption"] for s in body["stages"])
        assert len(body["stages"]) == 7


class TestDistribution:
    def test_readiness_buckets_match_the_fields(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)  # ready
        make_farm("cotton", sown=10)  # growing
        body = dashboard("distribution", as_officer("ADMIN-01"), scope="all", crop="cotton")
        buckets = {b["bucket"]: b["fields"] for b in body["readiness"]}

        assert buckets["ready"] == 1
        assert buckets["growing"] == 1
        assert buckets["harvested"] == 0

    def test_funnel_follows_the_crops_own_form(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        cotton = dashboard("distribution", as_officer("ADMIN-01"), scope="all", crop="cotton")
        hemp = dashboard("distribution", as_officer("ADMIN-01"), scope="all", crop="hemp")

        assert [s["step_key"] for s in cotton["fieldbook_funnel"]] == [
            "field_info",
            "land_preparation",
            "sowing",
            "nutrient_management",
            "irrigation",
            "weed_management",
            "pest_disease",
            "energy",
            "labour_social",
            "harvest",
        ]
        assert [s["step_key"] for s in hemp["fieldbook_funnel"]] == [
            "field_info",
            "land_preparation",
            "sowing",
            "nutrient_management",
            "crop_monitoring",
            "weeds_pests",
            "harvest",
            "retting",
            "baling",
        ]
        sowing = next(s for s in cotton["fieldbook_funnel"] if s["step_key"] == "sowing")
        assert sowing["complete"] == 1

    def test_regions_use_the_crops_own_wording(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton")
        make_farm("hemp")
        admin = as_officer("ADMIN-01")

        cotton = dashboard("distribution", admin, scope="all", crop="cotton")
        hemp = dashboard("distribution", admin, scope="all", crop="hemp")

        assert cotton["region_label"] == "District"
        assert cotton["area_unit"] == "acre"
        assert hemp["region_label"] == "County"
        assert hemp["area_unit"] == "ha"
        assert cotton["top_regions"][0]["fields"] == 1

    def test_all_crops_picks_the_bigger_programme_and_says_so(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("hemp")
        make_farm("hemp")
        make_farm("cotton")
        body = dashboard("distribution", as_officer("ADMIN-01"), scope="all", crop="all")

        assert body["focus_crop"] == "hemp"
        assert body["region_label"] == "County"

    def test_heap_utilisation_reports_input_and_bales(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        delivery = deliver(
            make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")), weighbridge=1000
        )
        heap = heap_with_bales([delivery], bales=1)
        body = dashboard("distribution", as_officer("ADMIN-01"), scope="all", crop="cotton")

        row = next(h for h in body["heap_utilisation"] if h["heap_id"] == heap["heap_id"])
        assert row["input_kg"] == 1000
        assert row["bales_made"] == 1
        assert row["expected_output_kg"] == float(heap["totals"]["expected_output_kg"])
        assert row["link"]["path"] == "/heaps"


class TestTimeseries:
    def test_registrations_return_two_series_over_the_range(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton")
        body = dashboard(
            "timeseries", as_officer("ADMIN-01"), scope="all", metric="registrations", range="7d"
        )

        keys = [s["key"] for s in body["series"]]
        assert keys == ["farmers", "fields"]
        assert body["interval"] == "day"
        assert len(body["series"][0]["points"]) == 7
        assert body["series"][0]["total"] == 1
        assert body["series"][1]["total"] == 1

    def test_deliveries_return_quantity_and_moisture(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        deliver(
            make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")),
            weighbridge=500,
            moisture=8.0,
        )
        body = dashboard(
            "timeseries",
            as_officer("ADMIN-01"),
            scope="all",
            crop="cotton",
            metric="deliveries",
            range="7d",
        )

        assert [s["key"] for s in body["series"]] == ["delivered_kg", "average_moisture_pct"]
        assert body["series"][0]["total"] == 500
        today_point = body["series"][1]["points"][-1]
        assert today_point["value"] == 8.0

    def test_interval_can_be_chosen(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        week = dashboard(
            "timeseries",
            as_officer("ADMIN-01"),
            metric="registrations",
            range="30d",
            interval="week",
        )
        assert week["interval"] == "week"
        assert len(week["series"][0]["points"]) <= 6

    def test_unknown_metric_is_refused(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        r = client.get(
            f"{DASH}/timeseries", params={"metric": "nonsense"}, headers=as_officer("ADMIN-01")
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "dashboard_metric_invalid"


class TestMap:
    def test_every_field_is_a_feature_with_its_status(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140)
        body = dashboard("map", as_officer("ADMIN-01"), scope="all", crop="cotton")

        assert body["type"] == "FeatureCollection"
        assert body["total"] == 1
        feature = body["features"][0]
        assert feature["properties"]["field_code"] == farm["field"]["field_id"]
        assert feature["properties"]["status"] == "ready"
        assert feature["properties"]["crop"] == "cotton"
        assert feature["properties"]["area_unit"] == "acre"
        assert feature["geometry"]["type"] == "Polygon"
        assert len(feature["properties"]["centroid"]) == 2

    def test_scope_narrows_the_map(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01")
        make_farm("cotton", officer="PK-MUL-02")
        headers = as_officer("PK-MUL-01")

        assert dashboard("map", headers, scope="mine", crop="cotton")["total"] == 1
        assert dashboard("map", headers, scope="all", crop="cotton")["total"] == 2


class TestActivity:
    def test_feed_names_the_module_and_links_to_the_record(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140)
        body = dashboard("activity", as_officer("ADMIN-01"))

        entities = {i["entity"] for i in body["items"]}
        assert {"farmer", "field", "fieldbook"} <= entities
        farmer_row = next(i for i in body["items"] if i["entity"] == "farmer")
        assert farmer_row["module"] == 2
        assert farmer_row["module_name"] == "Register Farmer"
        assert farmer_row["link"]["path"] == f"/register/farmers/{farm['farmer']['id']}"
        assert farmer_row["officer_name"]
        assert farmer_row["summary"]

    def test_module_filter(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        body = dashboard("activity", as_officer("ADMIN-01"), module=3)

        assert body["items"]
        assert {i["module"] for i in body["items"]} == {3}

    def test_limit_is_respected(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        make_farm("cotton", sown=140)
        assert len(dashboard("activity", as_officer("ADMIN-01"), limit=2)["items"]) == 2

    def test_gate_reception_is_a_filterable_module(
        self,
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        body = dashboard("activity", as_officer("ADMIN-01"), module=9)
        assert {"number": 9, "name": "Gate Reception"} in body["modules"]
        assert body["items"] == []


class TestOfficerOverview:
    def test_rows_count_each_officers_work(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140, officer="PK-MUL-01")
        make_farm("cotton", sown=140, officer="PK-MUL-01")
        make_farm("cotton", officer="PK-MUL-02")
        body = dashboard("officers", as_officer("ADMIN-01"), crop="cotton")

        rows = {r["code"]: r for r in body["items"]}
        assert rows["PK-MUL-01"]["farmers"] == 2
        assert rows["PK-MUL-01"]["fields"] == 2
        assert rows["PK-MUL-02"]["farmers"] == 1
        assert rows["PK-MUL-01"]["area"] > 0
        assert body["area_unit"] == "acre"

    def test_submitted_fieldbooks_are_counted_for_the_submitting_officer(
        self,
        client: TestClient,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140)
        body = dashboard("officers", as_officer("ADMIN-01"), crop="cotton")
        rows = {r["code"]: r for r in body["items"]}
        assert rows["PK-MUL-01"]["fieldbooks_submitted"] == 0
        assert farm["book"] is not None

    def test_only_administrators_may_read_it(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        r = client.get(f"{DASH}/officers", headers=as_officer("PK-MUL-01"))
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "admin_required"


class TestOnboarding:
    def test_empty_database_shows_the_checklist(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("onboarding", as_officer("PK-MUL-01"))

        assert body["is_empty"] is True
        assert [s["key"] for s in body["steps"]] == [
            "register_farmer",
            "map_field",
            "open_fieldbook",
        ]
        assert all(step["done"] is False for step in body["steps"])

    def test_steps_tick_off_as_the_work_happens(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140, officer="PK-MUL-01")
        body = dashboard("onboarding", as_officer("PK-MUL-01"))

        assert body["is_empty"] is False
        assert all(step["done"] for step in body["steps"])
        assert body["counts"] == {"farmers": 1, "fields": 1, "fieldbooks": 1}

    def test_a_farmer_with_no_field_leaves_the_second_step_open(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01", field=False)
        body = dashboard("onboarding", as_officer("PK-MUL-01"))
        steps = {s["key"]: s["done"] for s in body["steps"]}

        assert steps == {"register_farmer": True, "map_field": False, "open_fieldbook": False}

    def test_the_wording_follows_the_role(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        officer = dashboard("onboarding", as_officer("PK-MUL-01"))
        admin = dashboard("onboarding", as_officer("ADMIN-01"))

        assert officer["steps"][0]["title"] == "Register your first farmer"
        assert admin["steps"][0]["title"] == "Register the first farmer"
        assert admin["role"] == "admin"
