"""The generic settings: resolution order, validation, versions, history and caches.

The most important test here is :class:`TestDefaultsAreUnchanged`: making a constant
configurable must not change what the product does until somebody actually changes it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core import app_settings
from module_8 import registry
from module_8.tests.conftest import S


class TestRegistry:
    def test_every_declared_setting_is_listed(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        page = client.get(f"{S}/registry", headers=admin).json()
        assert {item["key"] for item in page["items"]} == {d.key for d in registry.DEFINITIONS}
        assert page["groups"] == list(registry.GROUPS)

    def test_a_setting_reports_its_group_type_and_default(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        item = client.get(f"{S}/values/alerts.heap_idle_days", headers=admin).json()
        assert item["group"] == "alerts"
        assert item["type"] == "int"
        assert item["source"] == "default"
        assert item["is_default"] is True

    def test_an_unknown_key_is_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        answer = client.put(f"{S}/values/made.up.key", json={"value": 1}, headers=admin)
        assert answer.status_code == 404
        assert answer.json()["error"]["code"] == "unknown_setting"


class TestDefaultsAreUnchanged:
    """Nothing is overridden out of the box, so behaviour matches the old constants."""

    def test_no_value_is_overridden_in_the_database_of_a_fresh_install(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        """A value may come from ``.env``; none comes from an administrator's override."""
        items = client.get(f"{S}/registry", headers=admin).json()["items"]
        assert [i["key"] for i in items if i["source"] == "database"] == []

    def test_each_value_equals_its_declared_default(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        declared = {d.key: d.default for d in registry.DEFINITIONS}
        for item in client.get(f"{S}/registry", headers=admin).json()["items"]:
            if item["sensitive"] or item["source"] == "env":
                continue
            assert item["value"] == declared[item["key"]], item["key"]

    def test_the_alert_thresholds_match_module_1_constants(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        from module_1 import public_api as dashboard

        values = client.get(f"{S}/config/alerts", headers=admin).json()["values"]
        # KEYS maps each setting key to the constant it must still equal.
        assert values == dashboard.KEYS

    def test_the_validation_rules_match_module_2_constants(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        page = {
            i["key"]: i["value"] for i in client.get(f"{S}/registry", headers=admin).json()["items"]
        }
        # The numbers Module 2 enforced before any of this became configurable: a hemp
        # grower number is 9 to 13 digits, and a field is between 100 m2 and 500 ha.
        assert page["validation.hemp_id_min_digits"] == 9
        assert page["validation.hemp_id_max_digits"] == 13
        assert page["validation.field_min_area_m2"] == 100.0
        assert page["validation.field_max_area_m2"] == 5_000_000.0


class TestValidation:
    def test_a_number_below_the_minimum_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 0}, headers=admin)
        assert answer.status_code == 422
        assert "cannot be below" in answer.json()["error"]["message"]

    def test_a_number_above_the_maximum_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.put(
            f"{S}/values/alerts.heap_idle_days", json={"value": 100_000}, headers=admin
        )
        assert answer.status_code == 422

    def test_a_value_outside_the_choices_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.put(
            f"{S}/values/map.tile_provider", json={"value": "google"}, headers=admin
        )
        assert answer.status_code == 422

    def test_text_where_a_number_belongs_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.put(
            f"{S}/values/alerts.heap_idle_days", json={"value": "soon"}, headers=admin
        )
        assert answer.status_code == 422

    def test_a_label_grid_missing_a_field_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.put(
            f"{S}/values/qr.label_grid", json={"value": {"columns": 3}}, headers=admin
        )
        assert answer.status_code == 422


class TestSavingAndHistory:
    def test_a_save_takes_effect_and_is_remembered(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        saved = client.put(
            f"{S}/values/alerts.heap_idle_days",
            json={"value": 9, "reason": "Shorter pilot"},
            headers=admin,
        )
        assert saved.status_code == 200
        body = saved.json()
        assert body["value"] == 9
        assert body["source"] == "database"
        assert body["is_default"] is False
        assert body["version"] == 1

        history = client.get(f"{S}/history?key=alerts.heap_idle_days", headers=admin).json()
        assert history[0]["new_value"] == 9
        assert history[0]["reason"] == "Shorter pilot"

    def test_a_stale_version_is_refused_with_the_current_value(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin)
        answer = client.put(
            f"{S}/values/alerts.heap_idle_days",
            json={"value": 12, "expected_version": 0},
            headers=admin,
        )
        assert answer.status_code == 409
        assert answer.json()["error"]["code"] == "stale_version"
        assert client.get(f"{S}/values/alerts.heap_idle_days", headers=admin).json()["value"] == 9

    def test_the_matching_version_is_accepted(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        first = client.put(
            f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin
        ).json()
        second = client.put(
            f"{S}/values/alerts.heap_idle_days",
            json={"value": 10, "expected_version": first["version"]},
            headers=admin,
        )
        assert second.status_code == 200
        assert second.json()["version"] == first["version"] + 1

    def test_a_reset_falls_back_to_the_default(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin)
        back = client.delete(f"{S}/values/alerts.heap_idle_days", headers=admin)
        assert back.status_code == 200
        assert back.json()["source"] == "default"
        assert back.json()["is_default"] is True

    def test_a_previous_value_can_be_restored(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin)
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 20}, headers=admin)
        entry = client.get(f"{S}/history?key=alerts.heap_idle_days", headers=admin).json()[0]
        assert entry["new_value"] == 20

        restored = client.post(f"{S}/history/{entry['id']}/restore", headers=admin)
        assert restored.status_code == 200
        assert restored.json()["value"] == 9

    def test_every_save_is_audited(self, client: TestClient, admin: dict[str, str]) -> None:
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin)
        entries = client.get(f"{S}/audit", params={"entity": "app_setting"}, headers=admin).json()[
            "items"
        ]
        assert entries
        assert entries[0]["action"] in ("update", "create")
        assert entries[0]["officer_name"]


class TestCacheInvalidation:
    def test_a_change_is_seen_by_the_next_read_without_a_restart(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        """Proves ``config.changed`` clears the resolved-value cache."""
        before = client.get(f"{S}/config/alerts", headers=admin).json()["values"]
        assert before["alerts.heap_idle_days"] != 7
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 7}, headers=admin)
        after = client.get(f"{S}/config/alerts", headers=admin).json()["values"]
        assert after["alerts.heap_idle_days"] == 7

    def test_a_map_change_reaches_the_public_config(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        assert "World_Imagery" in client.get(f"{S}/public").json()["map"]["tiles"]["url"]
        client.put(f"{S}/values/map.tile_provider", json={"value": "esri_street"}, headers=admin)
        assert "World_Street_Map" in client.get(f"{S}/public").json()["map"]["tiles"]["url"]

    def test_custom_tiles_cannot_be_chosen_without_an_address(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        """An empty map is worse than a refused save, so the registry refuses it."""
        answer = client.put(
            f"{S}/values/map.tile_provider", json={"value": "custom"}, headers=admin
        )
        assert answer.status_code == 422
        assert "custom tile address" in answer.json()["error"]["message"]

    def test_custom_tiles_work_once_the_address_is_set(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        client.put(
            f"{S}/values/map.custom_tile_url",
            json={"value": "https://tiles.example.com/{z}/{x}/{y}.png"},
            headers=admin,
        )
        client.put(
            f"{S}/values/map.custom_attribution",
            json={"value": "Tiles by Example"},
            headers=admin,
        )
        assert (
            client.put(
                f"{S}/values/map.tile_provider", json={"value": "custom"}, headers=admin
            ).status_code
            == 200
        )
        tiles = client.get(f"{S}/public").json()["map"]["tiles"]
        assert tiles["url"].startswith("https://tiles.example.com/")
        assert tiles["attribution"] == "Tiles by Example"


class TestResolutionOrder:
    def test_the_database_wins_over_the_environment(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        """``qr.public_base_url`` has an ``.env`` field, so the order is visible."""
        from_env = client.get(f"{S}/values/qr.public_base_url", headers=admin).json()
        assert from_env["source"] in ("env", "default")

        client.put(
            f"{S}/values/qr.public_base_url",
            json={"value": "https://trace.example.org"},
            headers=admin,
        )
        after = client.get(f"{S}/values/qr.public_base_url", headers=admin).json()
        assert after["source"] == "database"
        assert after["value"] == "https://trace.example.org"

    def test_setting_or_falls_back_when_the_registry_is_absent(self) -> None:
        """A unit test that never starts the app still gets the old constant."""
        app_settings.clear_registry()
        try:
            assert app_settings.setting_or("alerts.heap_idle_days", 14) == 14
        finally:
            registry.install()
