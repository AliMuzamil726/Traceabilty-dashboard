"""Who may open Settings, and the two rules that stop an administrator locking everyone out."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from module_8.tests.conftest import S

ADMIN_ONLY_READS = [
    "/registry",
    "/officers",
    "/offices",
    "/sites",
    "/lists",
    "/locations/tree?country=PK",
    "/permissions",
    "/audit",
    "/audit/facets",
    "/system",
    "/system/dummy",
    "/backups",
    "/backups/status",
    "/config/clock",
    "/config/delivery",
    "/config/heap",
    "/config/alerts",
    "/history",
]


class TestAdminOnly:
    @pytest.mark.parametrize("path", ADMIN_ONLY_READS)
    def test_an_officer_is_refused(
        self, client: TestClient, field_officer: dict[str, str], path: str
    ) -> None:
        answer = client.get(S + path, headers=field_officer)
        assert answer.status_code == 403, path
        assert answer.json()["error"]["code"] == "admin_required"

    @pytest.mark.parametrize("path", ADMIN_ONLY_READS)
    def test_staff_are_refused(
        self, client: TestClient, staff: dict[str, str], path: str
    ) -> None:
        """Staff work on every officer's records but never open Settings."""
        answer = client.get(S + path, headers=staff)
        assert answer.status_code == 403, path
        assert answer.json()["error"]["code"] == "admin_required"

    def test_staff_see_every_officers_farmers(
        self, client: TestClient, staff: dict[str, str], field_officer: dict[str, str]
    ) -> None:
        me = client.get("/api/v1/officers/me", headers=staff).json()
        assert me["role"] == "staff"
        assert me["sees_all"] is True
        assert me["is_admin"] is False
        overview = client.get("/api/v1/dashboard/officers", headers=staff)
        assert overview.status_code == 200
        refused = client.get("/api/v1/dashboard/officers", headers=field_officer)
        assert refused.status_code == 403

    @pytest.mark.parametrize("path", ADMIN_ONLY_READS)
    def test_an_administrator_is_allowed(
        self, client: TestClient, admin: dict[str, str], path: str
    ) -> None:
        assert client.get(S + path, headers=admin).status_code == 200, path

    def test_no_admin_route_is_left_unguarded(self, client: TestClient) -> None:
        """Walk the router so a route added later cannot quietly miss the admin check.

        With no header the development default officer acts, and that officer is not an
        administrator, so every administrative route must refuse. ``/public`` is open by
        design and ``/me/preferences`` belongs to every officer.
        """
        from fastapi.routing import APIRoute

        from module_8.router import router

        public = {f"{S}/public", f"{S}/meta", f"{S}/me/preferences"}
        paths = sorted(
            {
                route.path
                for route in router.routes
                if isinstance(route, APIRoute)
                and "{" not in route.path
                and "GET" in route.methods
                and route.path not in public
            }
        )
        assert len(paths) > 5, paths
        for path in paths:
            assert client.get(path).status_code in (401, 403), path

    def test_the_public_config_needs_no_officer(self, client: TestClient) -> None:
        answer = client.get(f"{S}/public")
        assert answer.status_code == 200
        assert answer.json()["map"]["tiles"]["url"]

    def test_the_public_config_hides_sensitive_and_private_settings(
        self, client: TestClient, admin: dict[str, str]
    ) -> None:
        public = set(client.get(f"{S}/public").json()["settings"])
        declared = client.get(f"{S}/registry", headers=admin).json()["items"]
        for item in declared:
            if item["sensitive"] or not item["public"]:
                assert item["key"] not in public, item["key"]


class TestPreferencesAreNotAdminOnly:
    def test_any_officer_reads_and_writes_their_own(
        self, client: TestClient, field_officer: dict[str, str]
    ) -> None:
        assert client.get(f"{S}/me/preferences", headers=field_officer).status_code == 200
        saved = client.put(
            f"{S}/me/preferences",
            json={"table_density": "compact", "sidebar_collapsed": True},
            headers=field_officer,
        )
        assert saved.status_code == 200
        assert saved.json()["table_density"] == "compact"

    def test_preferences_are_per_officer(
        self, client: TestClient, field_officer: dict[str, str], admin: dict[str, str]
    ) -> None:
        client.put(f"{S}/me/preferences", json={"table_density": "compact"}, headers=field_officer)
        assert client.get(f"{S}/me/preferences", headers=admin).json()["table_density"] == (
            "comfortable"
        )

    def test_a_density_outside_the_list_is_refused(
        self, client: TestClient, field_officer: dict[str, str]
    ) -> None:
        answer = client.put(
            f"{S}/me/preferences", json={"table_density": "tiny"}, headers=field_officer
        )
        assert answer.status_code == 422


class TestLockoutProtection:
    def test_an_administrator_cannot_deactivate_themselves(
        self, client: TestClient, admin: dict[str, str], officer_ids: dict[str, str]
    ) -> None:
        answer = client.post(f"{S}/officers/{officer_ids['ADMIN-01']}/deactivate", headers=admin)
        assert answer.status_code == 422
        assert answer.json()["error"]["code"] == "self_deactivation"

    def test_the_last_administrator_cannot_be_demoted_or_deactivated(
        self,
        client: TestClient,
        admin: dict[str, str],
        officer_ids: dict[str, str],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        # A second administrator, so the first one is not the last.
        second = client.post(
            f"{S}/officers",
            json={
                "code": "ADMIN-02",
                "full_name": "Second Administrator",
                "role": "admin",
                "country": "PK",
            },
            headers=admin,
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["id"]
        other = {"X-Officer-Id": second_id}

        # The second administrator may now deactivate the first.
        assert (
            client.post(
                f"{S}/officers/{officer_ids['ADMIN-01']}/deactivate", headers=other
            ).status_code
            == 200
        )
        # ...which leaves one, who can no longer be demoted.
        demote = client.put(f"{S}/officers/{second_id}", json={"role": "officer"}, headers=other)
        assert demote.status_code == 422
        assert demote.json()["error"]["code"] in ("last_admin", "self_deactivation")
