"""Radar reads: rows, buckets, KPIs, filters, scoping, sorting, map, calendar and CSV."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient

from module_4.tests.conftest import RADAR, cotton_picking, row_for

Farm = dict[str, Any]


def test_rows_show_status_and_clock_details(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]]
) -> None:
    growing = make_farm(sown=30)
    approaching = make_farm(sown=125)
    ready = make_farm(sown=140)
    overdue = make_farm(sown=210)
    unsown = make_farm()
    page = radar(growing["headers"])
    assert page["total"] == 5
    assert row_for(page, growing)["status"] == "growing"
    a = row_for(page, approaching)
    assert (a["status"], a["days_after_sowing"], a["next_milestone"]) == (
        "approaching",
        125,
        "Ready in 10 days",
    )
    assert a["expected_ready"] == (date.today() + timedelta(days=10)).isoformat()
    assert row_for(page, ready)["status"] == "ready"
    o = row_for(page, overdue)
    assert (o["status"], o["overdue"], o["next_milestone"]) == ("ready", True, "Overdue by 10 days")
    u = row_for(page, unsown)
    assert (u["status"], u["fieldbook_id"], u["sowing_date"]) == ("no_sowing_data", None, None)
    assert page["buckets"] == {
        "no_sowing_data": 1,
        "growing": 1,
        "approaching": 1,
        "ready": 2,
        "harvested": 0,
    }
    assert page["clock"] == {"approach_day": 120, "ready_day": 135, "window_end_day": 200}
    assert page["area_unit"] == "acre"


def test_harvest_and_ready_flag_come_from_fieldbook(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]]
) -> None:
    harvested = make_farm(sown=150, harvest=cotton_picking(ready="no"))
    flagged = make_farm(sown=150, harvest=cotton_picking(ready="yes"))
    page = radar(harvested["headers"])
    h, f = row_for(page, harvested), row_for(page, flagged)
    assert h["status"] == "harvested"
    assert (f["status"], f["next_milestone"]) == ("ready", "Ready for pickup")


def test_estimates_use_benchmark_until_a_yield_exists(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]], client: TestClient
) -> None:
    farm = make_farm(sown=150)
    row = row_for(radar(farm["headers"]), farm)
    assert row["estimate_is_benchmark"] is True
    assert row["estimated_kg"] == round(800 * row["area_acre"], 1)
    book = farm["book"]
    client.put(
        f"/api/v1/fieldbook/books/{book['id']}/steps/field_info",
        json={
            "data": {
                "crop_season": "kharif",
                "area_sown": 9.5,
                "soil_texture": "loam",
                "drainage_status": "well_drained",
            }
        },
        headers=farm["headers"],
    )
    client.post(
        f"/api/v1/fieldbook/books/{book['id']}/steps/harvest/entries",
        json={"data": cotton_picking()},
        headers=farm["headers"],
    )
    row = row_for(radar(farm["headers"]), farm)
    assert (row["estimated_kg"], row["estimate_is_benchmark"]) == (12 * 9.5 * 40, False)


def test_kpis_and_buckets_agree_with_rows(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]]
) -> None:
    farms = [make_farm(sown=s) for s in (140, 145, 125, 128, 30, 210)]
    page = radar(farms[0]["headers"])
    k = page["kpis"]
    ready_rows = [r for r in page["items"] if r["status"] == "ready"]
    assert k["ready_now"]["fields"] == len(ready_rows) == page["buckets"]["ready"] == 3
    assert k["ready_now"]["area"] == round(sum(r["area_acre"] for r in ready_rows), 2)
    assert k["ready_now"]["estimated_kg"] == round(sum(r["estimated_kg"] for r in ready_rows), 1)
    assert k["approaching_soon"]["fields"] == 2  # ready in 10 and 7 days
    assert k["overdue"]["fields"] == 1
    assert k["pickup_requested"]["fields"] == 0
    only_ready = radar(farms[0]["headers"], status="ready")
    assert only_ready["total"] == 3
    assert only_ready["buckets"] == page["buckets"]  # buckets ignore the status filter


def test_filters(make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]]) -> None:
    multan = make_farm(sown=140)
    bahawalpur = make_farm(sown=30, district="PK-PB-BWP")
    h = multan["headers"]
    assert radar(h, district="Bahawalpur")["total"] == 1
    assert radar(h, district="Multan", tehsil="Multan City")["total"] == 1
    assert radar(h, q=str(multan["farmer"]["sawie_id"]))["total"] == 1
    assert radar(h, q=bahawalpur["field"]["field_id"])["total"] == 1
    assert radar(h, q="farmer")["total"] == 2
    soon = (date.today() + timedelta(days=200)).isoformat()
    assert radar(h, ready_from=date.today().isoformat(), ready_to=soon)["total"] == 1
    assert radar(h, pickup="requested")["total"] == 0
    facets = radar(h)["facets"]
    assert facets["districts"] == ["Bahawalpur", "Multan"]
    assert facets["tehsils"]["Bahawalpur"] == ["Bahawalpur City"]
    assert facets["villages"]["Multan City"] == ["Basti Malook"]


def test_crop_switch_changes_units_and_rows(
    make_farm: Callable[..., Farm],
    radar: Callable[..., dict[str, Any]],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    make_farm(sown=100)
    hemp = make_farm("hemp", sown=100)
    page = radar(as_officer("ADMIN-01"), crop="hemp")
    assert page["total"] == 1
    assert page["area_unit"] == "ha"
    row = row_for(page, hemp)
    assert row["status"] == "ready"
    assert row["location"] != "-"
    assert page["clock"]["ready_day"] == 95


def test_officer_scope(
    make_farm: Callable[..., Farm],
    radar: Callable[..., dict[str, Any]],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    mine = make_farm(sown=140, officer="PK-MUL-01")
    theirs = make_farm(sown=140, officer="PK-BWP-01")
    me = as_officer("PK-MUL-01")
    assert [r["field_id"] for r in radar(me)["items"]] == [mine["field"]["id"]]
    everyone = radar(me, scope="all")
    assert everyone["total"] == 2
    other = row_for(everyone, theirs)
    assert (other["can_act"], other["can_request"]) == (False, False)
    assert row_for(everyone, mine)["can_request"] is True
    admin = radar(as_officer("ADMIN-01"))
    assert admin["total"] == 2
    assert admin["is_admin"] is True


def test_sorting_and_pagination(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]], client: TestClient
) -> None:
    farms = [make_farm(sown=s) for s in (10, 50, 90, 130)]
    h = farms[0]["headers"]
    das = [r["days_after_sowing"] for r in radar(h, sort="-das")["items"]]
    assert das == [130, 90, 50, 10]
    page2 = client.get(
        f"{RADAR}/fields", params={"sort": "das", "page": 2, "page_size": 3}, headers=h
    ).json()
    assert [r["days_after_sowing"] for r in page2["items"]] == [130]
    assert page2["total"] == 4
    bad = client.get(f"{RADAR}/fields", params={"sort": "nope"}, headers=h)
    assert bad.status_code == 422


def test_summary_matches_fields(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]], client: TestClient
) -> None:
    farm = make_farm(sown=140)
    make_farm(sown=20)
    s = client.get(f"{RADAR}/summary", headers=farm["headers"]).json()
    page = radar(farm["headers"])
    assert s["buckets"] == page["buckets"]
    assert s["kpis"] == page["kpis"]
    assert s["total_fields"] == 2


def test_map_features(make_farm: Callable[..., Farm], client: TestClient) -> None:
    ready = make_farm(sown=140)
    make_farm(sown=20)
    body = client.get(f"{RADAR}/map", params={"status": "ready"}, headers=ready["headers"]).json()
    assert body["type"] == "FeatureCollection"
    assert body["total"] == 1
    feat = body["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["status"] == "ready"
    assert feat["properties"]["can_request"] is True
    lng, lat = feat["properties"]["centroid"]
    assert abs(lat - 30.1775) < 0.01
    assert abs(lng - 71.5249) < 0.01


def test_calendar_days_and_weeks(make_farm: Callable[..., Farm], client: TestClient) -> None:
    a = make_farm(sown=130)  # ready in 5 days
    make_farm(sown=130)
    make_farm(sown=125)  # ready in 10 days
    make_farm(sown=140, harvest=cotton_picking())  # harvested: not in the calendar
    target = date.today() + timedelta(days=5)
    body = client.get(
        f"{RADAR}/calendar", params={"month": target.strftime("%Y-%m")}, headers=a["headers"]
    ).json()
    day = next(x for x in body["days"] if x["date"] == target.isoformat())
    assert day["fields"] == 2
    assert day["estimated_kg"] > 0
    assert len(body["weeks"]) == 8
    assert sum(w["fields"] for w in body["weeks"]) == 3
    assert (
        client.get(
            f"{RADAR}/calendar", params={"month": "2026-13"}, headers=a["headers"]
        ).status_code
        == 422
    )


def test_csv_export(make_farm: Callable[..., Farm], client: TestClient) -> None:
    farm = make_farm(sown=140)
    make_farm(sown=20)
    r = client.get(f"{RADAR}/export.csv", headers=farm["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f"radar_cotton_{date.today().isoformat()}.csv" in r.headers["content-disposition"]
    raw = r.content
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM so Excel reads it as UTF-8
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0][:3] == ["SAWIE ID", "Farmer", "Father or farm"]
    assert rows[0][-2:] == ["Centroid latitude", "Centroid longitude"]
    assert len(rows) == 3
    assert raw.count(b"\r\n") == 3
    selected = client.get(
        f"{RADAR}/export.csv", params={"field_ids": farm["field"]["id"]}, headers=farm["headers"]
    )
    chosen = list(csv.reader(io.StringIO(selected.content.decode("utf-8-sig"))))
    assert len(chosen) == 2
    assert chosen[1][5] == farm["field"]["field_id"]
    assert chosen[1][10] == "Ready"


def test_queries_do_not_grow_with_the_number_of_fields(
    make_farm: Callable[..., Farm], client: TestClient
) -> None:
    from sqlalchemy import event

    from module_4.services import cache

    engine = client.app.state.db.engine  # type: ignore[attr-defined]

    def count(headers: dict[str, str]) -> int:
        seen: list[str] = []

        def listener(*args: Any) -> None:
            if str(args[2]).startswith("SELECT"):
                seen.append(str(args[2]))

        cache.invalidate()
        event.listen(engine, "before_cursor_execute", listener)
        try:
            assert client.get(f"{RADAR}/fields", headers=headers).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return len(seen)

    first = make_farm(sown=140)
    small = count(first["headers"])
    for days in range(10, 130, 10):
        make_farm(sown=days)
    assert count(first["headers"]) == small


def test_results_are_cached_and_refreshed_by_fieldbook_events(
    make_farm: Callable[..., Farm], radar: Callable[..., dict[str, Any]], client: TestClient
) -> None:
    farm = make_farm(sown=140)
    assert row_for(radar(farm["headers"]), farm)["status"] == "ready"
    client.post(
        f"/api/v1/fieldbook/books/{farm['book']['id']}/steps/harvest/entries",
        json={"data": cotton_picking()},
        headers=farm["headers"],
    )
    # The fieldbook event dropped the cached view, so the change shows at once.
    assert row_for(radar(farm["headers"]), farm)["status"] == "harvested"
