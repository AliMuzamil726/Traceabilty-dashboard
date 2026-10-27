"""Every write publishes its documented event and leaves an audit entry behind."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from core import events
from core.database import Database
from module_2 import events as module_events
from module_2.tests.conftest import cotton_payload, square
from shared.models.audit_log import AuditLog

REGISTER = "/api/v1/register"


def _audit(database: Database, entity: str) -> list[AuditLog]:
    with database.session_scope() as session:
        return list(
            session.execute(
                select(AuditLog).where(AuditLog.entity == entity).order_by(AuditLog.created_at)
            )
            .scalars()
            .all()
        )


class TestDeclaredEvents:
    def test_every_published_name_is_known_to_the_bus(self) -> None:
        assert set(module_events.PUBLISHES) <= events.KNOWN_EVENTS
        assert set(module_events.PUBLISHES) == {
            events.FARMER_REGISTERED,
            events.FARMER_UPDATED,
            events.FIELD_CREATED,
            events.FIELD_UPDATED,
            events.FIELD_DELETED,
        }


class TestFarmerEvents:
    def test_registering_publishes_farmer_registered(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        with events.bus.capture() as captured:
            client.post(
                f"{REGISTER}/farmers",
                json=cotton_payload(pk_office["id"]),
                headers=as_officer("PK-MUL-01"),
            )
        names = [e.name for e in captured]
        assert events.FARMER_REGISTERED in names
        payload = next(e for e in captured if e.name == events.FARMER_REGISTERED).payload
        assert payload["sawie_id"] == 1001
        assert payload["crop"] == "cotton"
        assert payload["country"] == "PK"
        assert payload["field_office_id"] == pk_office["id"]
        assert payload["farmer_id"]

    def test_changing_a_farmer_publishes_farmer_updated_with_the_changed_keys(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton()
        with events.bus.capture() as captured:
            client.put(
                f"{REGISTER}/farmers/{saved['farmer']['id']}",
                json=cotton_payload(pk_office["id"], name="Imran Ahmed"),
                headers=as_officer("PK-MUL-01"),
            )
        updated = [e for e in captured if e.name == events.FARMER_UPDATED]
        assert len(updated) == 1
        assert updated[0].payload["changed"] == ["name"]
        assert updated[0].payload["sawie_id"] == 1001

    def test_an_update_that_changes_nothing_publishes_nothing(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        saved = register_cotton()
        with events.bus.capture() as captured:
            client.put(
                f"{REGISTER}/farmers/{saved['farmer']['id']}",
                json=cotton_payload(pk_office["id"]),
                headers=as_officer("PK-MUL-01"),
            )
        assert [e for e in captured if e.name == events.FARMER_UPDATED] == []


class TestFieldEvents:
    def test_saving_a_field_publishes_field_created_with_its_bbox(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farmer = register_cotton()["farmer"]
        with events.bus.capture() as captured:
            client.post(
                f"{REGISTER}/farmers/{farmer['id']}/fields",
                json={"geometry": square(side_m=200)},
                headers=as_officer("PK-MUL-01"),
            )
        created = next(e for e in captured if e.name == events.FIELD_CREATED)
        assert created.payload["field_code"] == "1001-01"
        assert created.payload["farmer_id"] == farmer["id"]
        assert created.payload["area_m2"] > 0
        assert len(created.payload["bbox"]) == 4

    def test_reshaping_publishes_field_updated_with_geometry_changed(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        farmer = register_cotton()["farmer"]
        field = client.post(
            f"{REGISTER}/farmers/{farmer['id']}/fields",
            json={"geometry": square(side_m=200)},
            headers=headers,
        ).json()

        with events.bus.capture() as captured:
            client.put(
                f"{REGISTER}/fields/{field['id']}",
                json={"geometry": square(side_m=260)},
                headers=headers,
            )
        updated = next(e for e in captured if e.name == events.FIELD_UPDATED)
        assert updated.payload["geometry_changed"] is True
        assert "area_m2" in updated.payload["changed"]
        assert updated.payload["field_code"] == "1001-01"

    def test_deleting_publishes_field_deleted(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        farmer = register_cotton()["farmer"]
        field = client.post(
            f"{REGISTER}/farmers/{farmer['id']}/fields",
            json={"geometry": square(side_m=200)},
            headers=headers,
        ).json()
        with events.bus.capture() as captured:
            client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers)
        deleted = next(e for e in captured if e.name == events.FIELD_DELETED)
        assert deleted.payload == {
            "field_id": field["id"],
            "field_code": "1001-01",
            "farmer_id": farmer["id"],
        }


class TestAuditTrail:
    def test_registration_is_audited_with_the_acting_officer(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        database: Database,
        officers: dict[str, dict[str, Any]],
    ) -> None:
        register_cotton()
        entries = _audit(database, "farmer")
        assert len(entries) == 1
        assert entries[0].action == "create"
        assert entries[0].officer_id == officers["PK-MUL-01"]["id"]
        assert entries[0].diff["sawie_id"]["to"] == 1001
        assert entries[0].request_id  # correlates the entry with the log lines

    def test_an_update_records_the_before_and_after_of_each_change(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
        database: Database,
    ) -> None:
        saved = register_cotton()
        client.put(
            f"{REGISTER}/farmers/{saved['farmer']['id']}",
            json=cotton_payload(pk_office["id"], name="Imran Ahmed", village="Chak 12"),
            headers=as_officer("ADMIN-01"),
        )
        entries = _audit(database, "farmer")
        update = next(e for e in entries if e.action == "update")
        assert update.diff["name"] == {"from": "Muhammad Imran", "to": "Imran Ahmed"}
        assert update.diff["village"] == {"from": "Basti Malook", "to": "Chak 12"}
        # Edited by a different officer than the one who registered the farmer.
        assert update.officer_id != entries[0].officer_id

    def test_the_season_profile_is_audited_separately(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
        database: Database,
    ) -> None:
        register_cotton(season_year=2026)
        client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], season_year=2026, variety="mnh-886"),
            headers=as_officer("PK-MUL-01"),
        )
        entries = _audit(database, "farmer_season_profile")
        assert [e.action for e in entries] == ["create", "update"]
        assert entries[1].diff["variety"] == {"from": "fh-142", "to": "mnh-886"}

    def test_field_create_update_and_delete_are_all_audited(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
        database: Database,
    ) -> None:
        headers = as_officer("PK-MUL-01")
        farmer = register_cotton()["farmer"]
        field = client.post(
            f"{REGISTER}/farmers/{farmer['id']}/fields",
            json={"geometry": square(side_m=200)},
            headers=headers,
        ).json()
        client.put(
            f"{REGISTER}/fields/{field['id']}",
            json={"geometry": square(side_m=240)},
            headers=headers,
        )
        client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers)

        actions = [e.action for e in _audit(database, "field")]
        assert actions == ["create", "update", "delete"]

    def test_a_write_always_records_who_did_it(
        self,
        client: TestClient,
        register_cotton: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
        database: Database,
        officers: dict[str, dict[str, Any]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        farmer = register_cotton()["farmer"]
        client.post(
            f"{REGISTER}/farmers/{farmer['id']}/fields",
            json={"geometry": square(side_m=200)},
            headers=headers,
        )
        from module_2.models import Farmer, Field

        with database.session_scope() as session:
            stored_farmer = session.execute(select(Farmer)).scalars().one()
            stored_field = session.execute(select(Field)).scalars().one()
        officer_id = officers["PK-MUL-01"]["id"]
        assert stored_farmer.created_by == officer_id
        assert stored_farmer.registered_by == officer_id
        assert stored_field.created_by == officer_id
        assert stored_field.updated_by == officer_id
