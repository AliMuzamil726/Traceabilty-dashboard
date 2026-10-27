"""The public API other modules will import, including its sensitive-data gate."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import select

from core.database import Database
from module_2 import public_api
from module_2.models import Farmer, FarmerSeasonProfile
from module_2.services.fields import FieldService
from module_2.tests.conftest import first_office_id, square
from shared.models.officer import ROLE_ADMIN, Officer


@pytest.fixture
def world(database: Database) -> dict[str, str]:
    """A cotton farmer with two fields, plus an owning officer and an administrator."""
    with database.session_scope() as session:
        office_id = first_office_id(session, "PK")
        owner = Officer(
            code="PK-TEST-01",
            full_name="Owning Officer",
            role="officer",
            country="PK",
            field_office_id=office_id,
        )
        admin = Officer(
            code="ADMIN-TEST",
            full_name="An Administrator",
            role=ROLE_ADMIN,
            country="PK",
        )
        stranger = Officer(
            code="PK-TEST-02",
            full_name="Another Officer",
            role="officer",
            country="PK",
            field_office_id=office_id,
        )
        session.add_all([owner, admin, stranger])
        session.flush()

        farmer = Farmer(
            sawie_id=1001,
            crop="cotton",
            country="PK",
            id_number_norm="3520212345671",
            id_number_display="35202-1234567-1",
            name="Muhammad Imran",
            father_name="Ghulam Rasool",
            phone_norm="+923001234567",
            phone_display="0300-1234567",
            province="Punjab",
            district="Multan",
            tehsil="Multan City",
            village="Basti Malook",
            field_office_id=office_id,
            registered_by=owner.id,
            created_by=owner.id,
        )
        session.add(farmer)
        session.flush()
        session.add(
            FarmerSeasonProfile(
                farmer_id=farmer.id,
                season_year=2026,
                variety="fh-142",
                tenure="owner",
                previous_crop="wheat",
            )
        )
        ids = {
            "farmer": farmer.id,
            "owner": owner.id,
            "admin": admin.id,
            "stranger": stranger.id,
            "office": office_id,
        }

    session = database.session_factory()
    try:
        service = FieldService(session)
        first = service.create(
            ids["farmer"], square(side_m=200), pin_lat=None, pin_lng=None, officer_id=ids["owner"]
        )
        second = service.create(
            ids["farmer"],
            square(side_m=200, offset_east_m=500),
            pin_lat=None,
            pin_lng=None,
            officer_id=ids["owner"],
        )
        ids["field_1"] = first.id
        ids["field_1_code"] = first.field_id
        ids["field_2"] = second.id
    finally:
        session.close()
    return ids


class TestFarmerAccess:
    def test_get_farmer_returns_a_frozen_dto(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(session, world["farmer"])
        assert dto is not None
        assert dto.sawie_id == 1001
        assert dto.name == "Muhammad Imran"
        assert dto.crop == "cotton"
        assert dto.country == "PK"
        with pytest.raises(FrozenInstanceError):
            dto.name = "Someone Else"  # type: ignore[misc]

    def test_unknown_ids_return_none_rather_than_raising(self, database: Database) -> None:
        with database.session_scope() as session:
            assert public_api.get_farmer(session, "nope") is None
            assert public_api.get_farmer_by_sawie_id(session, 99_999) is None
            assert public_api.get_field(session, "nope") is None
            assert public_api.get_field_geometry(session, "nope") is None
            assert public_api.get_season_profile(session, "nope", 2026) is None

    def test_lookup_by_sawie_id(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer_by_sawie_id(session, 1001)
        assert dto is not None
        assert dto.id == world["farmer"]

    def test_get_farmers_returns_a_map(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            found = public_api.get_farmers(session, [world["farmer"], "missing"])
        assert list(found) == [world["farmer"]]

    def test_search_and_officer_scoping(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            assert len(public_api.search_farmers(session, "imran")) == 1
            assert len(public_api.search_farmers(session, "1001")) == 1
            assert len(public_api.search_farmers(session, "nobody")) == 0
            # Scoped to the officer who registered the farmer.
            assert len(public_api.search_farmers(session, officer_id=world["owner"])) == 1
            assert len(public_api.search_farmers(session, officer_id=world["stranger"])) == 0
            assert len(public_api.list_farmers_for_officer(session, world["owner"])) == 1
            assert len(public_api.list_farmers_for_officer(session, world["stranger"])) == 0

    def test_crop_filter_and_counts(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            assert len(public_api.search_farmers(session, crop="cotton")) == 1
            assert len(public_api.search_farmers(session, crop="hemp")) == 0
            assert public_api.count_farmers(session) == 1
            assert public_api.count_farmers(session, crop="cotton") == 1
            assert public_api.count_farmers(session, country="GB") == 0


class TestSensitiveData:
    def test_masked_by_default(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(session, world["farmer"])
        assert dto is not None
        assert dto.id_number == "*****-****567-1"
        assert dto.phone == "0300-****567"
        assert dto.sensitive_included is False

    def test_the_registering_officer_may_see_the_real_values(
        self, database: Database, world: dict
    ) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(
                session, world["farmer"], include_sensitive=True, officer_id=world["owner"]
            )
        assert dto is not None
        assert dto.id_number == "35202-1234567-1"
        assert dto.phone == "0300-1234567"
        assert dto.sensitive_included is True

    def test_an_administrator_may_see_the_real_values(
        self, database: Database, world: dict
    ) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(
                session, world["farmer"], include_sensitive=True, officer_id=world["admin"]
            )
        assert dto is not None
        assert dto.sensitive_included is True

    def test_another_officer_may_not_even_when_asking(
        self, database: Database, world: dict
    ) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(
                session, world["farmer"], include_sensitive=True, officer_id=world["stranger"]
            )
        assert dto is not None
        assert dto.sensitive_included is False
        assert dto.id_number == "*****-****567-1"

    def test_asking_without_an_officer_gets_nothing_extra(
        self, database: Database, world: dict
    ) -> None:
        with database.session_scope() as session:
            dto = public_api.get_farmer(session, world["farmer"], include_sensitive=True)
        assert dto is not None
        assert dto.sensitive_included is False


class TestFieldAccess:
    def test_fields_for_a_farmer(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            fields = public_api.list_fields_for_farmer(session, world["farmer"])
        assert [f.field_id for f in fields] == ["1001-01", "1001-02"]
        assert all(f.area_m2 > 0 for f in fields)
        assert all(len(f.bbox) == 4 for f in fields)

    def test_a_field_can_be_fetched_by_key_or_by_business_id(
        self, database: Database, world: dict
    ) -> None:
        with database.session_scope() as session:
            by_key = public_api.get_field(session, world["field_1"])
            by_code = public_api.get_field(session, world["field_1_code"])
        assert by_key is not None
        assert by_code is not None
        assert by_key.id == by_code.id

    def test_get_fields_returns_a_map_keyed_by_id(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            found = public_api.get_fields(session, [world["field_1"], "missing"])
        assert list(found) == [world["field_1"]]

    def test_geometry_comes_back_as_geojson(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            geometry = public_api.get_field_geometry(session, world["field_1"])
        assert geometry is not None
        assert geometry["type"] == "Polygon"
        assert geometry["coordinates"][0][0] == geometry["coordinates"][0][-1]

    def test_list_fields_filters_by_bbox_and_crop(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            assert len(public_api.list_fields(session)) == 2
            assert len(public_api.list_fields(session, crop="cotton")) == 2
            assert len(public_api.list_fields(session, crop="hemp")) == 0
            inside = public_api.list_fields_in_bbox(session, (71.0, 29.8, 72.0, 30.6))
            assert len(inside) == 2
            outside = public_api.list_fields_in_bbox(session, (0.0, 50.0, 1.0, 51.0))
            assert outside == []

    def test_total_area_adds_up(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            total = public_api.total_area_m2(session)
            assert total == pytest.approx(80_000, rel=0.02)
            assert public_api.total_area_m2(session, crop="hemp") == 0.0
            assert public_api.total_area_m2(session, country="PK") == pytest.approx(
                80_000, rel=0.02
            )

    def test_a_soft_deleted_field_disappears_from_the_public_api(
        self, database: Database, world: dict
    ) -> None:
        session = database.session_factory()
        try:
            FieldService(session).delete(world["field_1"], officer_id=world["owner"])
        finally:
            session.close()
        with database.session_scope() as session:
            assert public_api.get_field(session, world["field_1"]) is None
            assert len(public_api.list_fields_for_farmer(session, world["farmer"])) == 1
            assert public_api.total_area_m2(session) == pytest.approx(40_000, rel=0.02)


class TestSeasonProfiles:
    def test_the_season_profile_is_readable(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            profile = public_api.get_season_profile(session, world["farmer"], 2026)
        assert profile is not None
        assert profile.variety == "fh-142"
        assert profile.tenure == "owner"
        assert profile.previous_crop == "wheat"

    def test_another_season_is_absent(self, database: Database, world: dict) -> None:
        with database.session_scope() as session:
            assert public_api.get_season_profile(session, world["farmer"], 2030) is None


def test_the_public_api_exports_everything_contracts_promises() -> None:
    expected = {
        "get_farmer",
        "get_farmer_by_sawie_id",
        "search_farmers",
        "list_farmers_for_officer",
        "get_field",
        "list_fields_for_farmer",
        "list_fields",
        "get_field_geometry",
        "get_season_profile",
        # Carried over from the Prompt 1 contract for the Dashboard.
        "get_farmers",
        "get_fields",
        "list_fields_in_bbox",
        "count_farmers",
        "total_area_m2",
    }
    assert expected <= set(public_api.__all__)
    for name in expected:
        assert callable(getattr(public_api, name))


def test_no_orm_rows_escape_through_the_public_api(database: Database, world: dict) -> None:
    """Every return value is a frozen dataclass, a dict, a primitive or a list of them."""
    from dataclasses import is_dataclass

    with database.session_scope() as session:
        values = [
            public_api.get_farmer(session, world["farmer"]),
            *public_api.search_farmers(session),
            *public_api.list_fields_for_farmer(session, world["farmer"]),
            public_api.get_season_profile(session, world["farmer"], 2026),
        ]
    for value in values:
        assert is_dataclass(value), value
        assert not hasattr(value, "_sa_instance_state")


def test_module_two_owns_exactly_the_tables_the_data_model_says(database: Database) -> None:
    from module_2 import models

    tables = {
        cls.__tablename__
        for cls in (models.Farmer, models.FarmerSeasonProfile, models.Field, models.UkPostcodeCache)
    }
    assert tables == {"farmers", "farmer_season_profiles", "fields", "uk_postcode_cache"}
    with database.session_scope() as session:
        # Every table really exists in the schema create_all produced.
        for table in tables:
            session.execute(select(1).select_from(models.Base.metadata.tables[table]))
