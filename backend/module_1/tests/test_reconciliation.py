"""The dashboard's numbers against the screens they summarise.

This is the test that matters most: a management overview that disagrees with the
module it summarises is worse than no overview. Every figure below is read twice, once
from the dashboard and once from the module that owns it, and the two must be equal.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from module_1.tests.conftest import DASH, YEAR, cotton_picking, stage


@pytest.fixture
def chain(
    make_farm: Callable[..., dict[str, Any]],
    deliver: Callable[..., dict[str, Any]],
    heap_with_bales: Callable[..., dict[str, Any]],
    request_pickup: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """A programme with fields in several states and one load all the way to a bale."""
    ready = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
    growing = make_farm("cotton", sown=10)
    overdue = make_farm("cotton", sown=205)
    requested = make_farm("cotton", sown=150, harvest=cotton_picking(ready="yes"))
    request_pickup(requested)
    hemp = make_farm("hemp", sown=100)
    delivery = heap = None
    delivery = deliver(ready, weighbridge=1200)
    heap = heap_with_bales([delivery], bales=2)
    return {
        "ready": ready,
        "growing": growing,
        "overdue": overdue,
        "requested": requested,
        "hemp": hemp,
        "delivery": delivery,
        "heap": heap,
    }


class TestAgainstHarvestRadar:
    def test_readiness_buckets_are_the_radars_own(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        params = {"crop": "cotton", "season_year": YEAR, "scope": "all"}
        radar = client.get("/api/v1/radar/summary", params=params, headers=admin).json()
        board = dashboard("distribution", admin, crop="cotton", scope="all")

        dashboard_buckets = {b["bucket"]: b["fields"] for b in board["readiness"]}
        assert dashboard_buckets == radar["buckets"]

    def test_ready_now_matches_the_radars_kpi(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        params = {"crop": "cotton", "season_year": YEAR, "scope": "all"}
        radar = client.get("/api/v1/radar/summary", params=params, headers=admin).json()
        board = dashboard("overview", admin, crop="cotton", scope="all")

        assert board["kpis"]["ready_now"]["fields"] == radar["kpis"]["ready_now"]["fields"]
        assert (
            board["kpis"]["ready_now"]["estimated_kg"] == radar["kpis"]["ready_now"]["estimated_kg"]
        )

    def test_the_overdue_alert_matches_the_radars_overdue_kpi(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        params = {"crop": "cotton", "season_year": YEAR, "scope": "all"}
        radar = client.get("/api/v1/radar/summary", params=params, headers=admin).json()
        alerts = dashboard("alerts", admin, crop="cotton", scope="all")
        overdue = next(a for a in alerts["alerts"] if a["key"] == "overdue_fields")

        assert overdue["count"] == radar["kpis"]["overdue"]["fields"]

    def test_the_map_shows_the_same_fields_as_the_radars_map(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        params = {"crop": "cotton", "season_year": YEAR, "scope": "all"}
        radar = client.get("/api/v1/radar/map", params=params, headers=admin).json()
        board = dashboard("map", admin, crop="cotton", scope="all")

        assert board["total"] == radar["total"]
        assert {f["id"] for f in board["features"]} == {f["id"] for f in radar["features"]}
        for feature in board["features"]:
            match = next(f for f in radar["features"] if f["id"] == feature["id"])
            assert feature["properties"]["status"] == match["properties"]["status"]
            assert feature["properties"]["overdue"] == match["properties"]["overdue"]


class TestAgainstDeliveries:
    def test_delivered_quantity_matches_the_delivery_stats(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        listed = client.get(
            "/api/v1/deliveries/",
            params={"crop": "cotton", "status": "delivered", "scope": "all", "page_size": 200},
            headers=admin,
        ).json()
        board = dashboard("overview", admin, crop="cotton", scope="all", range="season")
        weighed = round(sum(d["weighbridge_weight_kg"] or 0 for d in listed["items"]), 1)

        assert board["kpis"]["delivered"]["deliveries"] == listed["total"]
        assert board["kpis"]["delivered"]["kg"] == weighed

    def test_the_delivered_stage_matches_the_delivery_list(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        listed = client.get(
            "/api/v1/deliveries/",
            params={"crop": "cotton", "status": "delivered", "scope": "all", "page_size": 100},
            headers=admin,
        ).json()
        board = dashboard("pipeline", admin, crop="cotton", scope="all")

        assert stage(board, "deliveries")["count"] == listed["total"]


class TestAgainstHeapAndCodes:
    def test_bales_and_input_match_the_heap_screen(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        heap = client.get(f"/api/v1/heaps/{chain['heap']['heap_id']}", headers=admin).json()
        board = dashboard("distribution", admin, crop="cotton", scope="all")
        row = next(h for h in board["heap_utilisation"] if h["heap_id"] == heap["heap_id"])

        assert row["input_kg"] == float(heap["totals"]["input_kg"])
        assert row["expected_output_kg"] == float(heap["totals"]["expected_output_kg"])
        assert row["bales_made"] == heap["totals"]["bales_made"]
        assert row["max_bales"] == heap["totals"]["max_bales"]

    def test_the_bale_stage_matches_the_heaps_bale_count(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        heaps = client.get("/api/v1/heaps/", params={"crop": "cotton"}, headers=admin).json()
        board = dashboard("pipeline", admin, crop="cotton", scope="all")

        assert stage(board, "bales")["count"] == sum(h["bales_made"] for h in heaps)

    def test_scan_counts_match_the_qr_screen(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        heap_id = chain["heap"]["heap_id"]
        overview = client.get(f"/api/v1/qr/lots/{heap_id}/overview", headers=admin).json()
        # Open the public page once, so there is a scan to count.
        token = overview["token"]
        client.get(f"/api/v1/qr/public/{token}")
        summary = client.get(
            "/api/v1/qr/scans/summary", params={"heap_id": heap_id}, headers=admin
        ).json()
        board = dashboard("overview", admin, crop="cotton", scope="all")

        assert board["kpis"]["scans"]["total"] == summary["total"]
        assert board["kpis"]["scans"]["public"] == summary["public"]
        assert board["kpis"]["scans"]["active_codes"] == summary["active_tokens"]


class TestAgainstRegisterFarmer:
    def test_farmer_and_field_counts_match_the_farmer_list(
        self,
        client: Any,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        listed = client.get(
            "/api/v1/register/farmers",
            params={"crop": "cotton", "page_size": 200},
            headers=admin,
        ).json()
        board = dashboard("overview", admin, crop="cotton", scope="all")

        assert board["kpis"]["farmers"]["total"] == listed["total"]
        assert board["kpis"]["fields"]["total"] == sum(f["field_count"] for f in listed["items"])

    def test_the_officer_table_matches_each_officers_own_dashboard(
        self,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        table = dashboard("officers", as_officer("ADMIN-01"), crop="cotton")
        row = next(r for r in table["items"] if r["code"] == "PK-MUL-01")
        theirs = dashboard("overview", as_officer("PK-MUL-01"), crop="cotton", scope="mine")

        assert row["farmers"] == theirs["kpis"]["farmers"]["total"]
        assert row["fields"] == theirs["kpis"]["fields"]["total"]


class TestInternalConsistency:
    def test_the_pipeline_and_the_kpis_agree(
        self,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        pipeline = dashboard("pipeline", admin, crop="cotton", scope="all")
        overview = dashboard("overview", admin, crop="cotton", scope="all", range="season")

        assert stage(pipeline, "farmers")["count"] == overview["kpis"]["farmers"]["total"]
        assert stage(pipeline, "fields")["count"] == overview["kpis"]["fields"]["total"]
        assert stage(pipeline, "fieldbooks")["count"] == overview["kpis"]["fieldbooks"]["started"]
        assert stage(pipeline, "deliveries")["count"] == overview["kpis"]["delivered"]["deliveries"]
        assert stage(pipeline, "bales")["count"] == overview["kpis"]["bales"]["made"]
        assert stage(pipeline, "scans")["count"] == overview["kpis"]["scans"]["total"]

    def test_the_readiness_chart_and_the_pipeline_agree(
        self,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        pipeline = dashboard("pipeline", admin, crop="cotton", scope="all")
        distribution = dashboard("distribution", admin, crop="cotton", scope="all")
        buckets = {b["bucket"]: b["fields"] for b in distribution["readiness"]}

        assert stage(pipeline, "fields")["count"] == sum(buckets.values())
        assert stage(pipeline, "harvest")["count"] == buckets["ready"] + buckets["harvested"]

    def test_the_onboarding_counts_and_the_kpis_agree(
        self,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        onboarding = dashboard("onboarding", admin, crop="cotton", scope="all")
        overview = dashboard("overview", admin, crop="cotton", scope="all")

        assert onboarding["counts"]["farmers"] == overview["kpis"]["farmers"]["total"]
        assert onboarding["counts"]["fields"] == overview["kpis"]["fields"]["total"]

    def test_a_crop_filter_splits_the_total(
        self,
        chain: dict[str, Any],
        dashboard: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        both = dashboard("overview", admin, crop="all", scope="all")
        cotton = dashboard("overview", admin, crop="cotton", scope="all")
        hemp = dashboard("overview", admin, crop="hemp", scope="all")

        assert both["kpis"]["farmers"]["total"] == (
            cotton["kpis"]["farmers"]["total"] + hemp["kpis"]["farmers"]["total"]
        )
        assert both["kpis"]["fields"]["total"] == (
            cotton["kpis"]["fields"]["total"] + hemp["kpis"]["fields"]["total"]
        )

    def test_every_section_reports_the_filters_it_used(
        self,
        chain: dict[str, Any],
        client: Any,
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        for section in ("overview", "pipeline", "distribution", "alerts"):
            body = client.get(
                f"{DASH}/{section}",
                params={"crop": "hemp", "scope": "all", "season_year": YEAR},
                headers=admin,
            ).json()
            assert body["crop"] == "hemp"
            assert body["scope"] == "all"
            assert body["season_year"] == YEAR
