"""Field mapping endpoints: save, validate, reshape, soft delete, guards and the map layer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.guards import FIELD_CAN_DELETE, FIELD_CAN_EDIT_GEOMETRY, GuardResult
from core.guards import guards as guard_registry
from module_2.services.fields import GEOMETRY_ZOOM
from module_2.tests.conftest import LINCOLNSHIRE, MULTAN, bowtie, cotton_payload, square

REGISTER = "/api/v1/register"


@pytest.fixture
def farmer(register_cotton: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    return register_cotton()["farmer"]


def save_field(
    client: TestClient,
    farmer_id: str,
    geometry: dict[str, Any],
    headers: dict[str, str],
    **extra: Any,
) -> Any:
    return client.post(
        f"{REGISTER}/farmers/{farmer_id}/fields",
        json={"geometry": geometry, **extra},
        headers=headers,
    )


class TestSavingFields:
    def test_first_field_is_numbered_after_the_farmer(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        response = save_field(client, farmer["id"], square(side_m=200), as_officer("PK-MUL-01"))
        assert response.status_code == 201, response.text
        field = response.json()
        assert field["field_id"] == f"{farmer['sawie_id']}-01"
        assert field["area_m2"] == pytest.approx(40_000, rel=0.01)
        assert field["area_acre"] == pytest.approx(9.88, rel=0.01)
        assert field["area_ha"] == pytest.approx(4.0, rel=0.01)
        assert field["vertex_count"] == 4
        assert len(field["bbox"]) == 4

    def test_field_ids_run_in_sequence_for_one_farmer(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        codes = [
            save_field(
                client, farmer["id"], square(side_m=150, offset_east_m=300 * i), headers
            ).json()["field_id"]
            for i in range(3)
        ]
        assert codes == [f"{farmer['sawie_id']}-0{n}" for n in (1, 2, 3)]

    def test_each_farmer_has_its_own_field_sequence(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        other = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], id_number="35202-5555555-5", name="Other Farmer"),
            headers=headers,
        ).json()["farmer"]

        first = save_field(client, farmer["id"], square(side_m=150), headers).json()
        second = save_field(
            client, other["id"], square(side_m=150, offset_east_m=500), headers
        ).json()
        assert first["field_id"] == "1001-01"
        assert second["field_id"] == "1002-01"

    def test_a_deleted_field_number_is_not_reused(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        first = save_field(client, farmer["id"], square(side_m=150), headers).json()
        assert client.delete(f"{REGISTER}/fields/{first['id']}", headers=headers).status_code == 204
        replacement = save_field(client, farmer["id"], square(side_m=150), headers).json()
        assert replacement["field_id"] == "1001-02"

    def test_the_next_field_id_is_previewed_for_the_map_page(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        body = client.get(f"{REGISTER}/farmers/{farmer['id']}/fields", headers=headers).json()
        assert body["total"] == 0
        assert body["next_field_id_preview"] == "1001-01"
        save_field(client, farmer["id"], square(side_m=150), headers)
        body = client.get(f"{REGISTER}/farmers/{farmer['id']}/fields", headers=headers).json()
        assert body["total"] == 1
        assert body["next_field_id_preview"] == "1001-02"

    def test_a_pin_is_stored_and_defaults_inside_the_polygon(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        default = save_field(client, farmer["id"], square(side_m=200), headers).json()
        assert default["pin_lat"] == pytest.approx(MULTAN[0], abs=0.002)

        placed = save_field(
            client,
            farmer["id"],
            square(side_m=200, offset_east_m=600),
            headers,
            pin_lat=MULTAN[0],
            pin_lng=MULTAN[1] + 0.0062,
        ).json()
        assert placed["pin_lat"] == pytest.approx(MULTAN[0])

    def test_a_hemp_field_cannot_be_drawn_in_pakistan(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_2.tests.conftest import hemp_payload

        headers = as_officer("GB-EOE-01")
        hemp_farmer = client.post(
            f"{REGISTER}/farmers", json=hemp_payload(gb_office["id"]), headers=headers
        ).json()["farmer"]

        wrong = save_field(client, hemp_farmer["id"], square(MULTAN, 200), headers)
        assert wrong.status_code == 422
        assert wrong.json()["error"]["code"] == "field_outside_country"

        right = save_field(client, hemp_farmer["id"], square(LINCOLNSHIRE, 200), headers)
        assert right.status_code == 201, right.text

    @pytest.mark.parametrize(
        ("geometry_factory", "expected_code"),
        [
            (lambda: bowtie(), "field_self_intersection"),
            (lambda: square(side_m=5), "field_area_too_small"),
            (lambda: square(side_m=3000), "field_area_too_large"),
            (lambda: square(LINCOLNSHIRE, 200), "field_outside_country"),
        ],
    )
    def test_invalid_geometry_is_rejected_at_save(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
        geometry_factory: Callable[[], dict[str, Any]],
        expected_code: str,
    ) -> None:
        response = save_field(client, farmer["id"], geometry_factory(), as_officer("PK-MUL-01"))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == expected_code


class TestOverlapAtSave:
    def test_a_one_percent_overlap_is_rejected_at_save(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        side = 200.0
        first = save_field(client, farmer["id"], square(side_m=side), headers).json()

        overlapping = save_field(
            client, farmer["id"], square(side_m=side, offset_east_m=side * 0.99), headers
        )
        assert overlapping.status_code == 409
        error = overlapping.json()["error"]
        assert error["code"] == "field_overlap"
        conflict = error["details"]["conflicts"][0]
        assert conflict["field_code"] == first["field_id"]
        assert conflict["farmer_name"] == "Muhammad Imran"
        assert conflict["sawie_id"] == 1001
        assert conflict["overlap_percent_of_new_field"] == pytest.approx(1.0, abs=0.2)

    def test_the_same_farmers_own_fields_may_not_overlap_either(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        again = save_field(client, farmer["id"], square(side_m=100), headers)
        assert again.status_code == 409

    def test_fields_that_touch_along_an_edge_are_accepted(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        side = 200.0
        assert save_field(client, farmer["id"], square(side_m=side), headers).status_code == 201
        neighbour = save_field(
            client, farmer["id"], square(side_m=side, offset_east_m=side), headers
        )
        assert neighbour.status_code == 201, neighbour.text

    def test_another_farmers_field_also_blocks(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        other = client.post(
            f"{REGISTER}/farmers",
            json=cotton_payload(pk_office["id"], id_number="35202-6666666-6", name="Neighbour"),
            headers=headers,
        ).json()["farmer"]
        response = save_field(client, other["id"], square(side_m=200), headers)
        assert response.status_code == 409
        assert response.json()["error"]["details"]["conflicts"][0]["sawie_id"] == 1001


class TestValidateGeometryEndpoint:
    def test_a_clean_polygon_reports_its_measurements(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        body = client.post(
            f"{REGISTER}/fields/validate-geometry",
            json={"geometry": square(side_m=200), "farmer_id": farmer["id"]},
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert body["valid"] is True
        assert body["area_acre"] == pytest.approx(9.88, rel=0.01)
        assert body["area_ha"] == pytest.approx(4.0, rel=0.01)
        assert body["vertex_count"] == 4
        assert body["conflicts"] == []

    def test_overlap_is_reported_live_without_failing_the_request(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        response = client.post(
            f"{REGISTER}/fields/validate-geometry",
            json={
                "geometry": square(side_m=200, offset_east_m=198),
                "farmer_id": farmer["id"],
            },
            headers=headers,
        )
        # A half-drawn or overlapping shape is an expected state of the map, not a
        # failed request, so the endpoint always answers 200.
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["error_code"] == "field_overlap"
        assert body["conflicts"][0]["field_code"] == "1001-01"

    def test_broken_geometry_is_reported_as_invalid_not_as_an_error(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        body = client.post(
            f"{REGISTER}/fields/validate-geometry",
            json={"geometry": bowtie(), "farmer_id": farmer["id"]},
            headers=as_officer("PK-MUL-01"),
        ).json()
        assert body["valid"] is False
        assert body["error_code"] == "field_self_intersection"
        assert body["message"]

    def test_editing_a_field_excludes_it_from_its_own_overlap_check(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        geometry = square(side_m=200)
        field = save_field(client, farmer["id"], geometry, headers).json()

        without = client.post(
            f"{REGISTER}/fields/validate-geometry",
            json={"geometry": geometry, "farmer_id": farmer["id"]},
            headers=headers,
        ).json()
        assert without["valid"] is False

        excluded = client.post(
            f"{REGISTER}/fields/validate-geometry",
            json={
                "geometry": geometry,
                "farmer_id": farmer["id"],
                "exclude_field_id": field["id"],
            },
            headers=headers,
        ).json()
        assert excluded["valid"] is True


class TestEditingAndDeleting:
    def test_reshaping_recomputes_the_area(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()
        response = client.put(
            f"{REGISTER}/fields/{field['id']}",
            json={"geometry": square(side_m=300)},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["area_m2"] == pytest.approx(90_000, rel=0.01)
        assert response.json()["field_id"] == field["field_id"]  # the ID never changes

    def test_a_field_does_not_conflict_with_its_own_previous_shape(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()
        nudged = client.put(
            f"{REGISTER}/fields/{field['id']}",
            json={"geometry": square(side_m=200, offset_east_m=10)},
            headers=headers,
        )
        assert nudged.status_code == 200, nudged.text

    def test_reshaping_onto_another_field_is_still_blocked(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        side = 200.0
        first = save_field(client, farmer["id"], square(side_m=side), headers).json()
        save_field(client, farmer["id"], square(side_m=side, offset_east_m=side * 2), headers)
        response = client.put(
            f"{REGISTER}/fields/{first['id']}",
            json={"geometry": square(side_m=side, offset_east_m=side * 2)},
            headers=headers,
        )
        assert response.status_code == 409

    def test_delete_is_soft_and_hides_the_field_everywhere(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
        database: Any,
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()
        assert client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers).status_code == 204

        assert client.get(f"{REGISTER}/fields/{field['id']}", headers=headers).status_code == 404
        assert (
            client.get(f"{REGISTER}/farmers/{farmer['id']}/fields", headers=headers).json()["total"]
            == 0
        )
        assert client.get(f"{REGISTER}/fields/map", headers=headers).json()["total"] == 0
        # The row itself survives, with who removed it and when.
        from sqlalchemy import select

        from module_2.models import Field

        with database.session_scope() as session:
            row = session.execute(select(Field).where(Field.id == field["id"])).scalars().one()
            assert row.deleted_at is not None
            assert row.deleted_by is not None

    def test_the_space_of_a_deleted_field_becomes_free_again(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()
        client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers)
        again = save_field(client, farmer["id"], square(side_m=200), headers)
        assert again.status_code == 201


class TestGuards:
    def test_a_registered_guard_blocks_deletion_with_every_reason(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()

        guard_registry.register(
            FIELD_CAN_DELETE,
            lambda **_: GuardResult.deny("field_has_fieldbook", "This field has a fieldbook."),
            owner="module_3_test",
        )
        try:
            response = client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers)
            assert response.status_code == 409
            error = response.json()["error"]
            assert error["code"] == "field_has_fieldbook"
            assert error["details"]["reasons"][0]["reason"] == "This field has a fieldbook."
        finally:
            guard_registry.clear()

    def test_a_registered_guard_blocks_a_reshape_but_not_a_re_pin(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()

        guard_registry.register(
            FIELD_CAN_EDIT_GEOMETRY,
            lambda **_: GuardResult.deny("field_has_delivery", "This field has a delivery."),
            owner="module_5_test",
        )
        try:
            blocked = client.put(
                f"{REGISTER}/fields/{field['id']}",
                json={"geometry": square(side_m=250)},
                headers=headers,
            )
            assert blocked.status_code == 409
            assert blocked.json()["error"]["code"] == "field_has_delivery"

            # Moving only the pin does not change the boundary, so it is allowed.
            repinned = client.put(
                f"{REGISTER}/fields/{field['id']}",
                json={"pin_lat": MULTAN[0] + 0.0002, "pin_lng": MULTAN[1] + 0.0002},
                headers=headers,
            )
            assert repinned.status_code == 200, repinned.text
        finally:
            guard_registry.clear()

    def test_without_registered_guards_both_actions_are_allowed(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        field = save_field(client, farmer["id"], square(side_m=200), headers).json()
        assert (
            client.put(
                f"{REGISTER}/fields/{field['id']}",
                json={"geometry": square(side_m=220)},
                headers=headers,
            ).status_code
            == 200
        )
        assert client.delete(f"{REGISTER}/fields/{field['id']}", headers=headers).status_code == 204


class TestMapLayer:
    def test_every_field_is_visible_to_every_officer(
        self,
        client: TestClient,
        pk_office: dict[str, Any],
        gb_office: dict[str, Any],
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_2.tests.conftest import hemp_payload

        save_field(client, farmer["id"], square(side_m=200), as_officer("PK-MUL-01"))
        hemp_headers = as_officer("GB-EOE-01")
        hemp_farmer = client.post(
            f"{REGISTER}/farmers", json=hemp_payload(gb_office["id"]), headers=hemp_headers
        ).json()["farmer"]
        save_field(client, hemp_farmer["id"], square(LINCOLNSHIRE, 200), hemp_headers)

        # A Pakistani officer sees the UK field too: the layer is context, not ownership.
        body = client.get(f"{REGISTER}/fields/map", headers=as_officer("PK-MUL-01")).json()
        assert body["total"] == 2
        assert {f["crop"] for f in body["items"]} == {"cotton", "hemp"}
        assert all(f["geometry"] is not None for f in body["items"])
        assert body["mode"] == "outlines"

    def test_the_popup_payload_names_the_field_farmer_and_area(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        feature = client.get(f"{REGISTER}/fields/map", headers=headers).json()["items"][0]
        assert feature["field_id"] == "1001-01"
        assert feature["farmer_name"] == "Muhammad Imran"
        assert feature["sawie_id"] == 1001
        assert feature["area_acre"] == pytest.approx(9.88, rel=0.01)

    def test_low_zoom_returns_points_for_clustering(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        low = client.get(
            f"{REGISTER}/fields/map", params={"zoom": GEOMETRY_ZOOM - 1}, headers=headers
        ).json()
        assert low["mode"] == "points"
        assert low["items"][0]["geometry"] is None
        assert low["items"][0]["pin_lat"]

        high = client.get(
            f"{REGISTER}/fields/map", params={"zoom": GEOMETRY_ZOOM}, headers=headers
        ).json()
        assert high["mode"] == "outlines"
        assert high["items"][0]["geometry"] is not None

    def test_the_bounding_box_filters_and_the_limit_is_reported(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)

        inside = client.get(
            f"{REGISTER}/fields/map", params={"bbox": "71.0,29.8,72.0,30.6"}, headers=headers
        ).json()
        assert inside["total"] == 1

        elsewhere = client.get(
            f"{REGISTER}/fields/map", params={"bbox": "0.0,50.0,1.0,51.0"}, headers=headers
        ).json()
        assert elsewhere["total"] == 0

        capped = client.get(f"{REGISTER}/fields/map", params={"limit": 1}, headers=headers).json()
        assert capped["limit"] == 1
        assert capped["returned"] <= 1

    @pytest.mark.parametrize("bbox", ["1,2,3", "a,b,c,d", "5,5,1,1"])
    def test_a_malformed_bounding_box_is_a_bad_request(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]], bbox: str
    ) -> None:
        response = client.get(
            f"{REGISTER}/fields/map", params={"bbox": bbox}, headers=as_officer("PK-MUL-01")
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"

    def test_crop_filter(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        assert (
            client.get(f"{REGISTER}/fields/map", params={"crop": "cotton"}, headers=headers).json()[
                "total"
            ]
            == 1
        )
        assert (
            client.get(f"{REGISTER}/fields/map", params={"crop": "hemp"}, headers=headers).json()[
                "total"
            ]
            == 0
        )


class TestProfileCompleteness:
    def test_a_farmer_with_a_field_is_ready_for_the_fieldbook(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        body = client.get(f"{REGISTER}/farmers/{farmer['id']}/profile", headers=headers).json()
        assert body["completeness"]["has_fields"] is True
        assert body["completeness"]["ready_for_fieldbook"] is True
        assert body["completeness"]["missing"] == []
        assert body["completeness"]["total_area_ha"] == pytest.approx(4.0, rel=0.01)
        assert len(body["fields"]) == 1

    def test_the_list_row_shows_the_field_count(
        self,
        client: TestClient,
        farmer: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        headers = as_officer("PK-MUL-01")
        save_field(client, farmer["id"], square(side_m=200), headers)
        row = client.get(f"{REGISTER}/farmers", headers=headers).json()["items"][0]
        assert row["field_count"] == 1
        assert row["has_fields"] is True


def test_saving_a_field_for_an_unknown_farmer_is_a_404(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> None:
    response = save_field(client, "nope", square(side_m=200), as_officer("PK-MUL-01"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "farmer_not_found"


def test_editing_an_unknown_field_is_a_404(
    client: TestClient, as_officer: Callable[[str], dict[str, str]]
) -> None:
    response = client.put(
        f"{REGISTER}/fields/nope",
        json={"geometry": square(side_m=200)},
        headers=as_officer("PK-MUL-01"),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "field_not_found"
