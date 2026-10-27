"""The header's controls: crop, season, range and scope.

Every section takes the same parameters, so they are validated in one place and tested
in one place.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from module_1 import config
from module_1.services.filters import DashboardFilters
from module_1.tests.conftest import DASH, YEAR

SECTIONS = (
    "overview",
    "pipeline",
    "distribution",
    "alerts",
    "activity",
    "map",
    "onboarding",
)


class TestValidation:
    @pytest.mark.parametrize(
        ("params", "code"),
        [
            ({"crop": "maize"}, "validation_error"),
            ({"range": "forever"}, "validation_error"),
            ({"scope": "everyone"}, "validation_error"),
            ({"season_year": 1999}, "validation_error"),
            ({"range": "custom"}, "dashboard_range_incomplete"),
            (
                {"range": "custom", "from": "2026-06-01", "to": "2026-05-01"},
                "dashboard_range_invalid",
            ),
            (
                {"range": "custom", "from": "2020-01-01", "to": "2026-01-01"},
                "dashboard_range_too_long",
            ),
        ],
    )
    def test_bad_parameters_are_refused(
        self,
        client: Any,
        as_officer: Callable[[str], dict[str, str]],
        params: dict[str, Any],
        code: str,
    ) -> None:
        r = client.get(f"{DASH}/overview", params=params, headers=as_officer("ADMIN-01"))
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == code

    def test_the_same_parameters_are_accepted_by_every_section(
        self, client: Any, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        params = {
            "crop": "hemp",
            "season_year": YEAR,
            "range": "custom",
            "from": (date.today() - timedelta(days=10)).isoformat(),
            "to": date.today().isoformat(),
            "scope": "all",
        }
        for section in SECTIONS:
            r = client.get(f"{DASH}/{section}", params=params, headers=as_officer("ADMIN-01"))
            assert r.status_code == 200, (section, r.text)


class TestRanges:
    def test_presets_cover_the_days_they_name(self) -> None:
        today = date(2026, 10, 23)
        week = DashboardFilters(range_key=config.RANGE_7D).validate().range(as_of=today)
        month = DashboardFilters(range_key=config.RANGE_30D).validate().range(as_of=today)

        assert (week.start, week.end, week.days) == (date(2026, 10, 17), today, 7)
        assert (month.start, month.end, month.days) == (date(2026, 9, 24), today, 30)

    def test_a_season_ends_today_while_it_is_still_running(self) -> None:
        today = date(2026, 10, 23)
        current = (
            DashboardFilters(range_key=config.RANGE_SEASON, season_year=2026)
            .validate()
            .range(as_of=today)
        )
        past = (
            DashboardFilters(range_key=config.RANGE_SEASON, season_year=2025)
            .validate()
            .range(as_of=today)
        )

        assert (current.start, current.end) == (date(2026, 1, 1), today)
        assert (past.start, past.end) == (date(2025, 1, 1), date(2025, 12, 31))

    def test_a_range_is_whole_utc_days(self) -> None:
        window = (
            DashboardFilters(
                range_key=config.RANGE_CUSTOM,
                date_from=date(2026, 10, 1),
                date_to=date(2026, 10, 2),
            )
            .validate()
            .range()
        )

        assert window.since == datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)
        assert window.until.date() == date(2026, 10, 2)
        assert window.until.hour == 23
        assert window.days == 2

    def test_the_range_is_reported_back(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("overview", as_officer("ADMIN-01"), range="7d")

        assert body["range"]["key"] == "7d"
        assert body["range"]["days"] == 7
        assert body["range"]["to"] == date.today().isoformat()

    def test_a_range_narrows_what_it_should_and_nothing_else(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_1.tests.conftest import cotton_picking

        deliver(make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")), weighbridge=700)
        admin = as_officer("ADMIN-01")
        week = dashboard("overview", admin, crop="cotton", scope="all", range="7d")
        old = dashboard(
            "overview",
            admin,
            crop="cotton",
            scope="all",
            range="custom",
            **{
                "from": (date.today() - timedelta(days=40)).isoformat(),
                "to": (date.today() - timedelta(days=30)).isoformat(),
            },
        )

        # The load was received today, so it is in this week and not in the old window.
        assert week["kpis"]["delivered"]["kg"] == 700
        assert old["kpis"]["delivered"]["kg"] == 0
        # Farmers and fields are a running total, not a figure for the range.
        assert old["kpis"]["farmers"]["total"] == 1


class TestScope:
    def test_an_officer_may_look_at_the_whole_programme(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-02")
        body = dashboard("overview", as_officer("PK-MUL-01"), scope="all", crop="cotton")

        assert body["kpis"]["farmers"]["total"] == 1

    def test_an_administrator_may_look_at_their_own_work(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01")
        body = dashboard("overview", as_officer("ADMIN-01"), scope="mine", crop="cotton")

        assert body["scope"] == "mine"
        assert body["kpis"]["farmers"]["total"] == 0


class TestUnitsAndWording:
    def test_the_area_unit_follows_the_crop(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        admin = as_officer("ADMIN-01")

        assert dashboard("overview", admin, crop="cotton")["units"]["area"] == "acre"
        assert dashboard("overview", admin, crop="hemp")["units"]["area"] == "ha"
        # With both programmes selected, the product's first crop sets the unit.
        assert dashboard("overview", admin, crop="all")["units"]["area"] == "acre"

    def test_the_mass_unit_follows_the_crop(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        admin = as_officer("ADMIN-01")

        assert dashboard("overview", admin, crop="cotton")["units"]["mass"] == "maund"
        assert dashboard("overview", admin, crop="hemp")["units"]["mass"] == "t"

    def test_the_map_labels_each_field_in_its_own_crops_unit(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton")
        make_farm("hemp")
        body = dashboard("map", as_officer("ADMIN-01"), crop="all", scope="all")
        units = {f["properties"]["crop"]: f["properties"]["area_unit"] for f in body["features"]}

        assert units == {"cotton": "acre", "hemp": "ha"}

    def test_heaps_are_batches_for_hemp(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        delivery = deliver(make_farm("hemp", sown=100), site="UK-P1")
        heap_with_bales([delivery], site="UK-P1", officer="GB-EOE-01")
        body = dashboard("distribution", as_officer("ADMIN-01"), crop="hemp", scope="all")

        assert body["heap_utilisation"][0]["kind"] == "batch"
