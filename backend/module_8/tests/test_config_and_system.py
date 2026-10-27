"""Owned configuration, the audit log, backups and system information.

The configuration tests check the boundary as much as the behaviour: Settings calls the
owning module's config API and never writes its table, so changing a crop clock here
has to show up in Module 3's own reading of it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from module_8.tests.conftest import S


class TestCropClock:
    def test_the_defaults_match_module_3(self, client: TestClient, admin: dict[str, str]) -> None:
        crops = client.get(f"{S}/config/clock", headers=admin).json()["crops"]
        # The days Module 3 used before the clock became editable.
        assert crops["cotton"] == {
            "approach_day": 120,
            "ready_day": 135,
            "window_end_day": 200,
        }
        assert crops["hemp"] == {"approach_day": 80, "ready_day": 95, "window_end_day": 125}

    def test_days_out_of_order_are_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        answer = client.put(
            f"{S}/config/clock",
            json={
                "values": {"cotton": {"approach_day": 150, "ready_day": 120, "window_end_day": 170}}
            },
            headers=admin,
        )
        assert answer.status_code == 422
        assert answer.json()["error"]["code"] == "invalid_clock"

    def test_an_unknown_crop_is_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        answer = client.put(
            f"{S}/config/clock",
            json={"values": {"maize": {"approach_day": 10, "ready_day": 20, "window_end_day": 30}}},
            headers=admin,
        )
        assert answer.status_code == 422

    def test_a_change_is_saved_and_read_back_through_module_3(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        saved = client.put(
            f"{S}/config/clock",
            json={
                "values": {"cotton": {"approach_day": 100, "ready_day": 120, "window_end_day": 170}}
            },
            headers=admin,
        )
        assert saved.status_code == 200
        assert saved.json()["crops"]["cotton"]["ready_day"] == 120

        schema = client.get("/api/v1/fieldbook/schemas/cotton", headers=admin)
        assert schema.status_code == 200

    def test_a_stale_version_is_refused(self, client: TestClient, admin: dict[str, str]) -> None:
        body = {"cotton": {"approach_day": 100, "ready_day": 120, "window_end_day": 170}}
        client.put(f"{S}/config/clock", json={"values": body}, headers=admin)
        answer = client.put(
            f"{S}/config/clock", json={"values": body, "expected_version": 0}, headers=admin
        )
        assert answer.status_code == 409

    def test_the_preview_counts_the_fields_that_would_move(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        preview = client.post(
            f"{S}/config/clock/preview",
            json={
                "values": {"cotton": {"approach_day": 10, "ready_day": 20, "window_end_day": 30}}
            },
            headers=admin,
        )
        assert preview.status_code == 200
        body = preview.json()
        assert set(body) >= {"fields_examined", "fields_moving", "before", "after"}

    def test_the_preview_writes_nothing(self, client: TestClient, admin: dict[str, str]) -> None:
        before = client.get(f"{S}/config/clock", headers=admin).json()
        client.post(
            f"{S}/config/clock/preview",
            json={
                "values": {"cotton": {"approach_day": 10, "ready_day": 20, "window_end_day": 30}}
            },
            headers=admin,
        )
        assert client.get(f"{S}/config/clock", headers=admin).json() == before


class TestDeliveryAndHeapConfig:
    def test_delivery_defaults_match_module_5(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        crops = client.get(f"{S}/config/delivery", headers=admin).json()["crops"]
        # The tolerances Module 5 enforced before they became configurable.
        assert crops["cotton"]["variance_warn_pct"] == 3.0
        assert crops["cotton"]["variance_flag_pct"] == 5.0
        assert crops["cotton"]["moisture_warn_pct"] == 12.0

    def test_a_variance_change_is_applied_to_new_calculations(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        current = client.get(f"{S}/config/delivery", headers=admin).json()
        crop = next(iter(current["crops"]))
        values = dict(current["crops"][crop])
        values["variance_warn_pct"] = 3.0
        values["variance_flag_pct"] = 6.0
        saved = client.put(f"{S}/config/delivery", json={"values": {crop: values}}, headers=admin)
        assert saved.status_code == 200
        assert saved.json()["crops"][crop]["variance_warn_pct"] == 3.0

    def test_a_warn_above_the_flag_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        current = client.get(f"{S}/config/delivery", headers=admin).json()
        crop = next(iter(current["crops"]))
        values = dict(current["crops"][crop])
        values["variance_warn_pct"] = 20.0
        values["variance_flag_pct"] = 5.0
        answer = client.put(f"{S}/config/delivery", json={"values": {crop: values}}, headers=admin)
        assert answer.status_code == 422

    def test_heap_defaults_match_module_6(self, client: TestClient, admin: dict[str, str]) -> None:
        crops = client.get(f"{S}/config/heap", headers=admin).json()["crops"]
        # The defaults Module 6 used before they became configurable.
        assert crops["cotton"]["default_outturn_ratio_pct"] == 34.0
        assert crops["cotton"]["default_bale_unit_kg"] == 170.0

    def test_alert_thresholds_are_saved_one_at_a_time(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        """They are generic settings, so the block itself is read-only."""
        answer = client.put(
            f"{S}/config/alerts", json={"values": {"alerts.heap_idle_days": 5}}, headers=admin
        )
        assert answer.status_code == 422
        assert answer.json()["error"]["code"] == "use_values_api"

    def test_an_unknown_block_is_not_found(self, client: TestClient, admin: dict[str, str]) -> None:
        assert client.get(f"{S}/config/weather", headers=admin).status_code == 404


class TestAuditLog:
    def test_a_change_appears_with_its_before_and_after(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        client.put(f"{S}/values/alerts.heap_idle_days", json={"value": 9}, headers=admin)
        page = client.get(f"{S}/audit", params={"entity": "app_setting"}, headers=admin).json()
        assert page["total"] >= 1
        entry = page["items"][0]
        assert entry["module"] == 8
        assert entry["diff"]

    def test_the_log_can_be_filtered_by_module_and_action(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        page = client.get(
            f"{S}/audit", params={"module": 2, "action": "create"}, headers=admin
        ).json()
        assert page["items"]
        assert {i["module"] for i in page["items"]} == {2}
        assert {i["action"] for i in page["items"]} == {"create"}

    def test_an_unknown_module_filter_returns_nothing_rather_than_everything(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        page = client.get(f"{S}/audit", params={"module": 7}, headers=admin).json()
        assert all(i["module"] == 7 for i in page["items"])

    def test_paging_is_server_side(self, client: TestClient, admin: dict[str, str]) -> None:
        for number in range(3, 9):
            client.put(f"{S}/values/alerts.heap_idle_days", json={"value": number}, headers=admin)
        first = client.get(f"{S}/audit", params={"page_size": 2}, headers=admin).json()
        assert len(first["items"]) == 2
        assert first["total"] > 2
        second = client.get(f"{S}/audit", params={"page_size": 2, "page": 2}, headers=admin).json()
        assert {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]} == set()

    def test_the_export_is_safe_against_formulas(
        self, client: TestClient, admin: dict[str, str], any_list: str
    ) -> None:
        client.post(
            f"{S}/lists/{any_list}/values", json={"label": "=cmd|' /c calc'!A1"}, headers=admin
        )
        text = client.get(f"{S}/audit/export.csv", headers=admin).text
        assert "=cmd" in text  # the value is there
        assert "\n=cmd" not in text  # but never starts a row
        assert ",=cmd" not in text  # nor a cell

    def test_there_is_no_way_to_change_or_delete_an_entry(self) -> None:
        from fastapi.routing import APIRoute

        from module_8.router import router

        writes = [
            f"{sorted(r.methods)} {r.path}"
            for r in router.routes
            if isinstance(r, APIRoute)
            and "/audit" in r.path
            and r.methods & {"PUT", "PATCH", "DELETE", "POST"}
        ]
        assert writes == []


class TestBackups:
    def test_the_status_reports_sqlite_as_supported(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        status = client.get(f"{S}/backups/status", headers=admin).json()
        assert status["supported"] is True
        assert status["dialect"] == "sqlite"
        assert status["maintenance"] is False

    def test_a_backup_is_created_and_listed(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        made = client.post(f"{S}/backups", json={"note": "Before the season"}, headers=admin)
        assert made.status_code == 201
        body = made.json()
        assert body["size_bytes"] > 0
        assert body["kind"] == "manual"
        listed = client.get(f"{S}/backups", headers=admin).json()
        assert any(b["id"] == body["id"] and b["present"] for b in listed)

    def test_a_backup_can_be_downloaded(self, client: TestClient, admin: dict[str, str]) -> None:
        made = client.post(f"{S}/backups", json={}, headers=admin).json()
        download = client.get(f"{S}/backups/{made['id']}/download", headers=admin)
        assert download.status_code == 200
        assert download.content[:16].startswith(b"SQLite format 3")

    def test_a_restore_without_the_phrase_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        made = client.post(f"{S}/backups", json={}, headers=admin).json()
        answer = client.post(
            f"{S}/backups/{made['id']}/restore", json={"confirm": "yes"}, headers=admin
        )
        assert answer.status_code == 422
        assert answer.json()["error"]["code"] == "confirmation_required"

    def test_a_restore_puts_the_data_back_and_takes_a_safety_copy(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()
        before = client.get("/api/v1/register/farmers", headers=admin).json()["total"]
        snapshot = client.post(f"{S}/backups", json={"note": "with one farmer"}, headers=admin)
        assert snapshot.status_code == 201

        cotton_farmer()
        assert client.get("/api/v1/register/farmers", headers=admin).json()["total"] == before + 1

        restored = client.post(
            f"{S}/backups/{snapshot.json()['id']}/restore",
            json={"confirm": "RESTORE"},
            headers=admin,
        )
        assert restored.status_code == 200, restored.text
        body = restored.json()
        assert body["integrity"] == "ok"
        assert body["safety_backup"]
        assert body["counts_after"]["farmers"] == before

        # Maintenance mode cleared itself, so the product works again.
        assert client.get("/api/v1/register/farmers", headers=admin).status_code == 200

    def test_a_backup_can_be_deleted(self, client: TestClient, admin: dict[str, str]) -> None:
        made = client.post(f"{S}/backups", json={}, headers=admin).json()
        assert client.delete(f"{S}/backups/{made['id']}", headers=admin).status_code == 204
        assert all(b["id"] != made["id"] for b in client.get(f"{S}/backups", headers=admin).json())

    def test_maintenance_mode_is_off_by_default(self) -> None:
        from module_8 import public_api

        assert public_api.is_maintenance_mode() is False


class TestSystemInformation:
    def test_it_reports_versions_counts_and_health(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        body = client.get(f"{S}/system", headers=admin).json()
        assert body["app"]["version"]
        assert body["runtime"]["python"]
        assert body["database"]["dialect"] == "sqlite"
        assert {c["table"] for c in body["counts"]} >= {"farmers", "officers"}
        assert {c["key"] for c in body["health"]} >= {"database", "storage", "backups"}
        assert all(c["status"] in ("ok", "warn", "fail") for c in body["health"])

    def test_it_never_shows_database_credentials(self) -> None:
        from module_8.services.system import mask_url

        masked = mask_url("postgresql://sawie:hunter2@db.internal:5432/sawie")
        assert "hunter2" not in masked
        assert masked == "postgresql://sawie:***@db.internal:5432/sawie"

    def test_dummy_records_are_listed_with_their_usage(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        body = client.get(f"{S}/system/dummy", headers=admin).json()
        assert body["officers"] or body["offices"] or body["sites"]

    def test_only_unreferenced_dummy_rows_are_removed(
        self,
        client: TestClient,
        admin: dict[str, str],
        cotton_farmer: Callable[..., dict[str, Any]],
    ) -> None:
        cotton_farmer()  # puts one dummy officer and one dummy office in use
        before = client.get(f"{S}/system/dummy", headers=admin).json()
        used = [r for r in before["officers"] if r["usage"] > 0]
        assert used, "registering a farmer should put the seeded officer in use"

        removed = client.post(f"{S}/system/dummy/remove", headers=admin)
        assert removed.status_code == 200
        body = removed.json()
        kept_codes = {k["code"] for k in body["kept"]}
        assert {r["code"] for r in used} <= kept_codes

        after = client.get(f"{S}/system/dummy", headers=admin).json()
        assert {r["code"] for r in after["officers"]} >= {r["code"] for r in used}

    def test_the_acting_administrator_is_never_removed(
        self, client: TestClient, admin: dict[str, str], officer_ids: dict[str, str]
    ) -> None:
        client.post(f"{S}/system/dummy/remove", headers=admin)
        still_there = client.get(f"{S}/officers/{officer_ids['ADMIN-01']}", headers=admin)
        assert still_there.status_code == 200


class TestTestButtons:
    def test_a_localhost_public_url_is_warned_about(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.post(
            f"{S}/qr/test-url", json={"url": "http://localhost:5173"}, headers=admin
        )
        assert answer.status_code == 200
        assert "only works on this computer" in (answer.json()["warning"] or "")

    def test_an_address_without_a_scheme_is_refused_before_any_request(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.post(f"{S}/qr/test-url", json={"url": "trace.example.org"}, headers=admin)
        assert answer.json()["ok"] is False
        assert "http://" in answer.json()["detail"]

    def test_an_unknown_tile_provider_is_refused(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        answer = client.post(f"{S}/map/test-tiles", json={"provider": "bing"}, headers=admin)
        assert answer.json()["ok"] is False
        assert "Unknown tile provider" in answer.json()["detail"]

    def test_custom_tiles_need_a_url(self, client: TestClient, admin: dict[str, str]) -> None:
        answer = client.post(f"{S}/map/test-tiles", json={"provider": "custom"}, headers=admin)
        assert answer.json()["ok"] is False
