"""UK postcode lookup: the API, the cache, the area-table fallback and manual entry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.database import Database
from module_2.models import UkPostcodeCache
from module_2.services import postcode as pc
from module_2.services.postcode import PostcodeService

REGISTER = "/api/v1/register"


def _client_returning(payload: dict[str, Any], status: int = 200) -> httpx.Client:
    """An httpx client whose every request is answered from memory."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _client_failing(exc: Exception | None = None, status: int = 500) -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        if exc is not None:
            raise exc
        return httpx.Response(status, json={"error": "nope"})

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestAreaTable:
    def test_the_bundled_table_covers_the_usual_areas(self) -> None:
        table = pc.area_table()
        assert len(table) >= 120
        assert table["LN"] == ("Lincolnshire", "East Midlands")
        assert table["CB"] == ("Cambridgeshire", "East of England")
        assert table["AB"][1] == "Scotland"

    def test_the_data_file_says_it_still_needs_verifying(self) -> None:
        import json

        document = json.loads(pc._DATA_FILE.read_text(encoding="utf-8"))
        assert document["_meta"]["status"] == "SEED DATA - TO BE VERIFIED"
        assert document["_meta"]["count"] == len(document["items"])


class TestLookupSources:
    def test_the_api_answer_is_preferred_and_cached(self, database: Database) -> None:
        api = _client_returning(
            {
                "result": {
                    "postcode": "LN4 3QP",
                    "admin_county": "Lincolnshire",
                    "admin_district": "North Kesteven",
                    "region": "East Midlands",
                    "country": "England",
                }
            }
        )
        with database.session_scope() as session:
            found = PostcodeService(session, client=api).lookup("ln43qp")
            assert found.postcode == "LN4 3QP"
            assert found.county == "Lincolnshire"
            assert found.region == "East Midlands"
            assert found.source == pc.SOURCE_API
            assert found.editable is False

        # Second call never reaches the network.
        with database.session_scope() as session:
            cached = PostcodeService(session, client=_client_failing()).lookup("LN4 3QP")
            assert cached.source == pc.SOURCE_CACHE
            assert cached.county == "Lincolnshire"
            assert (
                session.execute(select(func.count()).select_from(UkPostcodeCache)).scalar_one() == 1
            )

    def test_admin_district_is_used_where_there_is_no_county(self, database: Database) -> None:
        api = _client_returning(
            {
                "result": {
                    "admin_county": None,
                    "admin_district": "City of Edinburgh",
                    "region": None,
                    "country": "Scotland",
                }
            }
        )
        with database.session_scope() as session:
            found = PostcodeService(session, client=api).lookup("EH1 1AA")
        assert found.county == "City of Edinburgh"
        assert found.region == "Scotland"

    @pytest.mark.parametrize(
        "failing",
        [
            _client_failing(status=404),
            _client_failing(status=500),
            _client_failing(httpx.ConnectError("offline")),
            _client_failing(httpx.ReadTimeout("too slow")),
        ],
    )
    def test_the_area_table_catches_every_kind_of_api_failure(
        self, database: Database, failing: httpx.Client
    ) -> None:
        with database.session_scope() as session:
            found = PostcodeService(session, client=failing).lookup("LN4 3QP")
        assert found.source == pc.SOURCE_AREA_TABLE
        assert found.county == "Lincolnshire"
        assert found.region == "East Midlands"
        assert found.resolved is True
        assert found.editable is False

    def test_an_unknown_area_is_unresolved_and_opens_manual_entry(self, database: Database) -> None:
        api = _client_returning({"result": {}})
        with database.session_scope() as session:
            # ZZ is not a real postcode area, so nothing can resolve it.
            found = PostcodeService(session, client=api).lookup("ZZ1 1ZZ")
        assert found.source == pc.SOURCE_UNRESOLVED
        assert found.county is None
        assert found.resolved is False
        assert found.editable is True

    def test_an_empty_api_result_falls_through_to_the_table(self, database: Database) -> None:
        with database.session_scope() as session:
            found = PostcodeService(session, client=_client_returning({"result": {}})).lookup(
                "CB23 6DP"
            )
        assert found.source == pc.SOURCE_AREA_TABLE
        assert found.county == "Cambridgeshire"


class TestPostcodeEndpoint:
    def test_the_endpoint_normalises_and_resolves(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        body = client.get(f"{REGISTER}/uk/postcode/ln43qp", headers=as_officer("GB-EOE-01")).json()
        assert body["postcode"] == "LN4 3QP"
        assert body["county"]
        assert body["region"]
        assert body["resolved"] is True
        assert body["editable"] is False

    def test_an_invalid_postcode_is_a_validation_error(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        response = client.get(f"{REGISTER}/uk/postcode/NOTAPOST", headers=as_officer("GB-EOE-01"))
        assert response.status_code == 422

    def test_the_answer_is_cached_between_requests(
        self, client: TestClient, as_officer: Callable[[str], dict[str, str]], database: Any
    ) -> None:
        headers = as_officer("GB-EOE-01")
        first = client.get(f"{REGISTER}/uk/postcode/CB23 6DP", headers=headers).json()
        second = client.get(f"{REGISTER}/uk/postcode/cb236dp", headers=headers).json()
        assert first["county"] == second["county"]
        assert second["source"] == pc.SOURCE_CACHE


class TestManualEntryOnFailure:
    def test_county_and_region_are_only_accepted_when_nothing_resolved(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_2.tests.conftest import hemp_payload

        headers = as_officer("GB-EOE-01")
        # LN resolves, so the officer's own values are ignored in favour of the lookup.
        response = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"], county="Made Up County", region="Made Up Region"),
            headers=headers,
        )
        assert response.status_code == 201, response.text
        farmer = response.json()["farmer"]
        assert farmer["county"] != "Made Up County"
        assert farmer["region"] != "Made Up Region"

    def test_an_unresolvable_postcode_requires_the_officer_to_supply_them(
        self,
        client: TestClient,
        gb_office: dict[str, Any],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_2.tests.conftest import hemp_payload

        headers = as_officer("GB-EOE-01")
        without = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(gb_office["id"], postcode="ZZ1 1ZZ"),
            headers=headers,
        )
        assert without.status_code == 422
        assert without.json()["error"]["details"]["fields"][0]["field"] == "county"

        with_values = client.post(
            f"{REGISTER}/farmers",
            json=hemp_payload(
                gb_office["id"],
                postcode="ZZ1 1ZZ",
                county="Islands County",
                region="Islands Region",
            ),
            headers=headers,
        )
        assert with_values.status_code == 201, with_values.text
        assert with_values.json()["farmer"]["county"] == "Islands County"
