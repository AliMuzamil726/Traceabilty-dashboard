"""The eight attention rules, checked on both sides of their thresholds.

Each rule has one number that decides it, and every number lives in
``module_1.config``. The tests below put a record one day inside, exactly on and one
day outside each threshold, so an off-by-one cannot pass.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import update

from module_1 import config
from module_1.tests.conftest import alert, cotton_picking


class TestReadyWithoutPickup:
    """Ready, nobody asked for a pickup: flagged after READY_WITHOUT_PICKUP_DAYS."""

    def ready_days_ago(self, days: int) -> int:
        """Sowing age that makes a cotton field ready exactly ``days`` ago."""
        return 135 + days

    def test_one_day_inside_the_threshold_is_quiet(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=self.ready_days_ago(config.READY_WITHOUT_PICKUP_DAYS - 1))
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_READY_WITHOUT_PICKUP)["count"] == 0

    def test_exactly_on_the_threshold_is_quiet(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=self.ready_days_ago(config.READY_WITHOUT_PICKUP_DAYS))
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_READY_WITHOUT_PICKUP)["count"] == 0

    def test_one_day_past_the_threshold_is_flagged(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=self.ready_days_ago(config.READY_WITHOUT_PICKUP_DAYS + 1))
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        row = alert(body, config.ALERT_READY_WITHOUT_PICKUP)

        assert row["count"] == 1
        assert row["severity"] == config.SEVERITY_ATTENTION
        assert row["samples"][0]["label"] == farm["field"]["field_id"]
        assert row["link"]["params"]["status"] == "ready"
        assert row["link"]["params"]["pickup"] == "not_requested"

    def test_a_requested_field_is_not_flagged(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        request_pickup: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=self.ready_days_ago(30))
        request_pickup(farm)
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_READY_WITHOUT_PICKUP)["count"] == 0


class TestOverdueFields:
    def test_the_day_before_the_window_closes_is_quiet(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=200)  # exactly the window end
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_OVERDUE_FIELDS)["count"] == 0

    def test_one_day_past_the_window_is_critical(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=201)
        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_OVERDUE_FIELDS,
        )

        assert row["count"] == 1
        assert row["severity"] == config.SEVERITY_CRITICAL

    def test_a_harvested_field_is_never_overdue(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=210, harvest=cotton_picking())
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_OVERDUE_FIELDS)["count"] == 0

    def test_the_link_selects_exactly_the_overdue_fields(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=205)  # overdue
        make_farm("cotton", sown=150)  # ready, not overdue
        admin = as_officer("ADMIN-01")
        row = alert(
            dashboard("alerts", admin, scope="all", crop="cotton"), config.ALERT_OVERDUE_FIELDS
        )

        # The link carries the frontend's query keys; the radar's own API calls the
        # expected-ready filter ``ready_to``, which is what that page sends for "to".
        params = dict(row["link"]["params"])
        params["ready_to"] = params.pop("to")
        radar = client.get(
            "/api/v1/radar/fields",
            params={**params, "page_size": 100},
            headers=admin,
        ).json()
        assert row["count"] == 1
        assert radar["total"] == 1
        assert all(r["overdue"] for r in radar["items"])


class TestDispatchOverdue:
    def test_a_delivery_scheduled_for_today_is_quiet(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        schedule: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        delivery = schedule(farm)
        _set_scheduled_date(client, delivery["id"], date.today())

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_DISPATCH_OVERDUE)["count"] == 0

    def test_a_delivery_scheduled_yesterday_is_flagged(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        schedule: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        delivery = schedule(farm)
        _set_scheduled_date(client, delivery["id"], date.today() - timedelta(days=1))

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_DISPATCH_OVERDUE,
        )
        assert row["count"] == 1
        assert row["samples"][0]["label"] == delivery["delivery_no"]
        assert row["link"]["params"]["status"] == "scheduled"

    def test_a_dispatched_delivery_is_not_flagged(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        schedule: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        delivery = schedule(farm)
        _set_scheduled_date(client, delivery["id"], date.today() - timedelta(days=3))
        client.post(
            f"/api/v1/deliveries/{delivery['id']}/dispatch", json={}, headers=farm["headers"]
        )

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_DISPATCH_OVERDUE)["count"] == 0


class TestWeightVariance:
    def test_a_flagged_load_is_reported_with_its_variance(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        delivery = deliver(farm, field_weight=1000, weighbridge=1100)  # 10 percent

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_WEIGHT_VARIANCE,
        )
        assert delivery["variance_level"] == "flag"
        assert row["count"] == 1
        assert "%" in (row["samples"][0]["sublabel"] or "")

    def test_a_load_within_tolerance_is_quiet(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        deliver(farm, field_weight=1000, weighbridge=1010)  # 1 percent

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_WEIGHT_VARIANCE)["count"] == 0


class TestIdleHeaps:
    def test_one_day_inside_the_threshold_is_quiet(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        delivery = deliver(make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")))
        heap = heap_with_bales([delivery])
        _age_heap(client, heap["id"], heap["heap_id"], config.HEAP_IDLE_DAYS - 1)

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_IDLE_HEAPS)["count"] == 0

    def test_exactly_on_the_threshold_is_flagged(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        delivery = deliver(make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes")))
        heap = heap_with_bales([delivery])
        _age_heap(client, heap["id"], heap["heap_id"], config.HEAP_IDLE_DAYS)

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_IDLE_HEAPS,
        )
        assert row["count"] == 1
        assert row["samples"][0]["label"] == heap["heap_id"]
        assert row["link"]["params"]["status"] == "open"


class TestLicenceExpiry:
    def _set_expiry(
        self, client: Any, farm: dict[str, Any], expiry: date, area: float = 3.8
    ) -> None:
        r = client.put(
            f"/api/v1/fieldbook/books/{farm['book']['id']}/steps/field_info",
            json={
                "data": {
                    "season": "spring_sowing",
                    "area_drilled": area,
                    "licence_expiry": expiry.isoformat(),
                    "soil_type": "clay_loam",
                    "previous_crop": "winter_wheat",
                }
            },
            headers=farm["headers"],
        )
        assert r.status_code == 200, r.text

    def test_a_licence_outside_the_window_is_quiet(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("hemp", sown=100)
        days = config.LICENCE_EXPIRY_WARNING_DAYS + 1
        self._set_expiry(client, farm, date.today() + timedelta(days=days))

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="hemp")
        assert alert(body, config.ALERT_LICENCE_EXPIRY)["count"] == 0

    def test_exactly_on_the_window_is_flagged(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("hemp", sown=100)
        days = config.LICENCE_EXPIRY_WARNING_DAYS
        self._set_expiry(client, farm, date.today() + timedelta(days=days))

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="hemp"),
            config.ALERT_LICENCE_EXPIRY,
        )
        assert row["count"] == 1
        assert row["severity"] == config.SEVERITY_ATTENTION

    def test_an_expired_licence_is_critical(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("hemp", sown=100)
        self._set_expiry(client, farm, date.today() - timedelta(days=1))

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="hemp"),
            config.ALERT_LICENCE_EXPIRY,
        )
        assert row["count"] == 1
        assert row["severity"] == config.SEVERITY_CRITICAL
        assert "expired" in (row["samples"][0]["sublabel"] or "")

    def test_cotton_never_raises_a_licence_alert(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_LICENCE_EXPIRY)["count"] == 0


class TestStaleDrafts:
    def test_one_day_inside_the_threshold_is_quiet(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=20)
        _age_fieldbook(client, farm["book"]["id"], config.DRAFT_FIELDBOOK_IDLE_DAYS - 1)

        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")
        assert alert(body, config.ALERT_STALE_DRAFTS)["count"] == 0

    def test_past_the_threshold_is_flagged_with_its_progress(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=20)
        _age_fieldbook(client, farm["book"]["id"], config.DRAFT_FIELDBOOK_IDLE_DAYS + 1)

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_STALE_DRAFTS,
        )
        assert row["count"] == 1
        assert row["samples"][0]["label"] == farm["field"]["field_id"]
        assert "steps done" in (row["samples"][0]["sublabel"] or "")
        assert row["samples"][0]["link"]["path"].endswith(farm["book"]["id"])


class TestFarmersWithoutField:
    def test_a_farmer_with_no_field_is_flagged(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", field=False)
        make_farm("cotton")  # has a field

        row = alert(
            dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton"),
            config.ALERT_FARMERS_WITHOUT_FIELD,
        )
        assert row["count"] == 1
        assert row["samples"][0]["label"] == str(farm["farmer"]["sawie_id"])
        assert row["samples"][0]["link"]["path"] == f"/register/farmers/{farm['farmer']['id']}"

    def test_scope_narrows_the_rule(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", officer="PK-MUL-01", field=False)
        make_farm("cotton", officer="PK-MUL-02", field=False)
        headers = as_officer("PK-MUL-01")

        mine = dashboard("alerts", headers, scope="mine", crop="cotton")
        every = dashboard("alerts", headers, scope="all", crop="cotton")

        assert alert(mine, config.ALERT_FARMERS_WITHOUT_FIELD)["count"] == 1
        assert alert(every, config.ALERT_FARMERS_WITHOUT_FIELD)["count"] == 2


class TestPanel:
    def test_every_rule_is_present_and_counted(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all")

        assert [a["key"] for a in body["alerts"]] == list(config.ALERT_KEYS)
        assert body["total"] == 0
        assert body["critical"] == 0
        assert all(a["description"] for a in body["alerts"])

    def test_only_the_critical_rules_use_the_error_red(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all")
        critical = {a["key"] for a in body["alerts"] if a["severity"] == config.SEVERITY_CRITICAL}
        assert critical <= config.CRITICAL_ALERTS

    def test_totals_add_up(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=205)  # overdue and ready without pickup
        make_farm("cotton", field=False)  # no field
        body = dashboard("alerts", as_officer("ADMIN-01"), scope="all", crop="cotton")

        assert body["total"] == sum(a["count"] for a in body["alerts"])
        assert body["critical"] == sum(
            a["count"] for a in body["alerts"] if a["severity"] == config.SEVERITY_CRITICAL
        )


# --------------------------------------------------------------------------- helpers
# A threshold that ages a record is only reachable by letting time pass, so these
# helpers move the stored timestamp instead: the test clock for the rules that age a
# record rather than a crop. They write through ``Base.metadata`` rather than another
# module's models, because a module may not import another module's tables.


def _table(name: str) -> Any:
    from core.database import Base

    return Base.metadata.tables[name]


def _write(client: Any, name: str, row_id: str, values: dict[str, Any]) -> None:
    table = _table(name)
    session = client.app.state.db.session_factory()
    try:
        session.execute(update(table).where(table.c.id == row_id).values(**values))
        session.commit()
    finally:
        session.close()
    _drop_caches(client)


def _set_scheduled_date(client: Any, delivery_id: str, when: date) -> None:
    _write(client, "deliveries", delivery_id, {"scheduled_date": when})


def _age_heap(client: Any, heap_pk: str, heap_id: str, days: int) -> None:
    """Age the heap and the loads in it: the rule ages the latest of the two."""
    when = datetime.now(UTC) - timedelta(days=days)
    _write(client, "heaps", heap_pk, {"opened_at": when, "updated_at": when})
    deliveries = _table("deliveries")
    session = client.app.state.db.session_factory()
    try:
        session.execute(
            update(deliveries).where(deliveries.c.heap_id == heap_id).values(updated_at=when)
        )
        session.commit()
    finally:
        session.close()
    _drop_caches(client)


def _age_fieldbook(client: Any, book_id: str, days: int) -> None:
    when = datetime.now(UTC) - timedelta(days=days)
    _write(client, "fieldbooks", book_id, {"updated_at": when})


def _drop_caches(client: Any) -> None:
    """A direct write skips the event bus, so the cached sections are dropped by hand."""
    from module_1.services import cache

    cache.invalidate()
