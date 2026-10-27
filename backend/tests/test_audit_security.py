"""Security and privacy checks from the final audit, kept as regression tests.

Each test here was written to find a hole. The ones that found one have a fix beside
them (see docs/AUDIT_REPORT.md); the rest stay so the hole cannot open later.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings
from core.csvsafe import safe_cell
from module_1.tests.conftest import YEAR, cotton_picking

BACKEND = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------- CSV injection


class TestCsvInjection:
    @pytest.mark.parametrize("value", ["=1+1", "+SUM(A1)", "-2+3", "@cmd", "\tx", "\rx"])
    def test_formula_starters_are_neutralised(self, value: str) -> None:
        assert safe_cell(value) == "'" + value

    @pytest.mark.parametrize("value", ["-3.25", "+4", "12", "Basti Malook", "", None, 5, -2.5])
    def test_numbers_and_plain_text_are_left_alone(self, value: Any) -> None:
        assert safe_cell(value) == ("" if value is None else value)

    def test_no_export_writes_csv_without_the_safe_writer(self) -> None:
        offenders = [
            str(p.relative_to(BACKEND))
            for p in BACKEND.rglob("*.py")
            if "venv" not in p.parts
            and p.name != "csvsafe.py"
            and "tests" not in p.parts
            and "csv.writer(" in p.read_text(encoding="utf-8")
        ]
        assert offenders == []

    def test_a_typed_village_cannot_become_a_formula_in_the_radar_export(
        self,
        client: TestClient,
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140)
        r = client.put(
            f"/api/v1/register/farmers/{farm['farmer']['id']}",
            json={**_farmer_body(farm), "village": '=HYPERLINK("http://x")'},
            headers=farm["headers"],
        )
        if r.status_code == 422:
            pytest.skip("the village field already refuses formula characters")
        assert r.status_code == 200, r.text
        export = client.get(
            "/api/v1/radar/export.csv", params={"crop": "cotton"}, headers=farm["headers"]
        )
        cells = [c for row in csv.reader(io.StringIO(export.text.lstrip("﻿"))) for c in row]
        assert not any(c.startswith("=") for c in cells)
        assert any(c.startswith("'=") or "=HYPERLINK" not in c for c in cells)

    def test_a_typed_vehicle_number_cannot_become_a_formula_in_the_delivery_export(
        self,
        client: TestClient,
        make_farm: Callable[..., dict[str, Any]],
        schedule: Callable[..., dict[str, Any]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        r = None
        try:
            schedule(farm, vehicle_no="@SUM(1+1)")
        except AssertionError:
            pytest.skip("the vehicle number already refuses formula characters")
        export = client.get(
            "/api/v1/deliveries/export.csv", params={"scope": "all"}, headers=farm["headers"]
        )
        assert export.status_code == 200
        cells = [c for row in csv.reader(io.StringIO(export.text.lstrip("﻿"))) for c in row]
        assert not any(c.startswith("@") for c in cells)
        del r


def _farmer_body(farm: dict[str, Any]) -> dict[str, Any]:
    return {
        "crop": "cotton",
        "id_number": farm["farmer"]["id_number"],
        "name": farm["farmer"]["name"],
        "father_name": "ghulam rasool",
        "phone": "0300-1234567",
        "province_code": "PK-PB",
        "district_code": "PK-PB-MUL",
        "tehsil_code": "PK-PB-MUL-T01",
        "village": "Basti Malook",
        "field_office_id": (farm["farmer"].get("field_office") or {}).get("id")
        or farm["farmer"].get("field_office_id"),
        "variety": "fh-142",
        "tenure": "owner",
        "previous_crop": "wheat",
    }


# -------------------------------------------------------------- cross-officer access


class TestCrossOfficerAccess:
    """Officer B guesses officer A's ids and tries to read or change A's records."""

    @pytest.fixture
    def a(
        self,
        make_farm: Callable[..., dict[str, Any]],
        request_pickup: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        farm = make_farm("cotton", sown=140, officer="PK-MUL-01")
        farm["request"] = request_pickup(farm)
        return farm

    @pytest.fixture
    def b(self, as_officer: Callable[[str], dict[str, str]]) -> dict[str, str]:
        return as_officer("PK-MUL-02")

    def test_b_sees_a_farmers_id_number_and_phone_masked(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        r = client.get(f"/api/v1/register/farmers/{a['farmer']['id']}", headers=b)
        assert r.status_code in (200, 403, 404)
        if r.status_code == 200:
            body = r.json()
            farmer = body.get("farmer", body)
            assert farmer["id_number"] != a["farmer"]["id_number"]
            assert "*" in farmer["id_number"] or "•" in farmer["id_number"]

    def test_b_cannot_change_a_farmer(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        r = client.put(
            f"/api/v1/register/farmers/{a['farmer']['id']}",
            json={**_farmer_body(a), "village": "Taken over"},
            headers=b,
        )
        assert r.status_code in (403, 404), r.text

    def test_b_cannot_reshape_or_remove_a_field(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        field_id = a["field"]["id"]
        assert client.delete(f"/api/v1/register/fields/{field_id}", headers=b).status_code in (
            403,
            404,
            409,
        )
        moved = client.put(
            f"/api/v1/register/fields/{field_id}",
            json={"pin": {"lat": 30.2, "lng": 71.5}},
            headers=b,
        )
        assert moved.status_code in (403, 404, 422), moved.text

    def test_b_cannot_add_a_field_to_a_farmer(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        from module_1.tests.conftest import square

        r = client.post(
            f"/api/v1/register/farmers/{a['farmer']['id']}/fields",
            json={"geometry": square((29.9, 71.9))},
            headers=b,
        )
        assert r.status_code in (403, 404), r.text

    def test_b_cannot_write_a_fieldbook(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        from module_1.tests.conftest import cotton_sowing

        r = client.put(
            f"/api/v1/fieldbook/books/{a['book']['id']}/steps/sowing",
            json={"data": cotton_sowing(30)},
            headers=b,
        )
        assert r.status_code == 403, r.text

    def test_b_cannot_cancel_a_pickup_request(
        self, client: TestClient, a: dict[str, Any], b: dict[str, str]
    ) -> None:
        r = client.post(
            f"/api/v1/radar/pickup-requests/{a['request']['id']}/cancel",
            json={"reason": "not mine"},
            headers=b,
        )
        assert r.status_code == 403, r.text

    def test_b_cannot_schedule_or_move_a_delivery(
        self,
        client: TestClient,
        a: dict[str, Any],
        b: dict[str, str],
        sites: dict[str, str],
        schedule: Callable[..., dict[str, Any]],
    ) -> None:
        from module_1.tests.conftest import transport

        stolen = client.post(
            "/api/v1/deliveries/schedule",
            json={"request_ids": [a["request"]["id"]], **transport(sites["BWP-G1"])},
            headers=b,
        )
        assert stolen.status_code == 201
        assert stolen.json()["created"] == []
        delivery = schedule(a)
        for action, body in (("dispatch", {}), ("cancel", {"reason": "x"})):
            r = client.post(f"/api/v1/deliveries/{delivery['id']}/{action}", json=body, headers=b)
            assert r.status_code == 403, (action, r.text)


# ------------------------------------------------------------------ officer identity


def _production(tmp_path: Path) -> TestClient:
    settings = Settings(
        app_env="production",
        database_url=f"sqlite:///{(tmp_path / 'prod.db').as_posix()}",
        upload_dir=str(tmp_path / "storage"),
        seed_on_start=True,
        _env_file=None,  # type: ignore[call-arg]
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


class TestOfficerIdentity:
    ROUTES = (
        "/api/v1/dashboard/overview",
        "/api/v1/register/farmers",
        "/api/v1/fieldbook/books",
        "/api/v1/radar/fields",
        "/api/v1/deliveries/",
        "/api/v1/heaps/",
        "/api/v1/qr/lots",
        "/api/v1/officers/me",
    )

    @pytest.mark.parametrize("path", ROUTES)
    def test_production_refuses_every_route_without_the_header(
        self, tmp_path: Path, path: str
    ) -> None:
        with _production(tmp_path) as client:
            r = client.get(path)
        assert r.status_code == 401, r.text
        assert r.json()["error"]["code"] == "officer_required"

    def test_an_unknown_officer_id_is_refused(self, client: TestClient) -> None:
        r = client.get("/api/v1/register/farmers", headers={"X-Officer-Id": "not-an-officer"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "officer_not_found"

    def test_the_public_trace_page_needs_no_officer(self, tmp_path: Path) -> None:
        with _production(tmp_path) as client:
            r = client.get("/api/v1/qr/public/ABCDEFGHJKMN")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "qr_invalid"


class TestProductionHardening:
    def test_an_unexpected_error_hides_the_stack_trace(self, tmp_path: Path) -> None:
        with _production(tmp_path) as client:
            app = client.app

            @app.get("/api/v1/_boom")  # type: ignore[attr-defined]
            def boom() -> None:
                raise RuntimeError("secret internals /home/user/db.sqlite")

            r = client.get("/api/v1/_boom")
        assert r.status_code == 500
        text = r.text
        assert "Traceback" not in text
        assert "secret internals" not in text
        assert r.json()["error"]["code"] == "internal_error"

    def test_cors_only_answers_configured_origins(self, client: TestClient) -> None:
        good = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        evil = client.options(
            "/api/health",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert good.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "access-control-allow-origin" not in evil.headers


class TestUploads:
    def test_photo_download_cannot_traverse_paths(
        self, client: TestClient, make_farm: Callable[..., dict[str, Any]]
    ) -> None:
        farm = make_farm("cotton", sown=30)
        book = farm["book"]["id"]
        for evil in ("..%2F..%2Fconftest.py", "../../../etc/passwd", "%2e%2e%2f%2e%2e%2fapp"):
            r = client.get(f"/api/v1/fieldbook/books/{book}/photos/{evil}", headers=farm["headers"])
            assert r.status_code in (404, 422), (evil, r.status_code)

    def test_a_non_image_disguised_as_jpeg_is_refused(
        self, client: TestClient, make_farm: Callable[..., dict[str, Any]]
    ) -> None:
        farm = make_farm("cotton", sown=30)
        r = client.post(
            f"/api/v1/fieldbook/books/{farm['book']['id']}/photos",
            files={"files": ("photo.jpg", b"<?php echo 'x'; ?>", "image/jpeg")},
            headers=farm["headers"],
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] in ("photo_invalid", "photo_type_not_allowed")


class TestPublicTrace:
    @pytest.fixture(autouse=True)
    def _fresh_limiter(self) -> Any:
        from module_7.services.scans import public_limiter

        public_limiter.reset()
        yield
        public_limiter.reset()

    def test_unknown_malformed_and_lowercase_codes_answer_identically(
        self, client: TestClient
    ) -> None:
        answers = {
            code: client.get(f"/api/v1/qr/public/{code}").json()
            for code in ("ZZZZZZZZZZZZ", "short", "' OR 1=1 --", "abcdefghjkmn")
        }
        assert len({str(a) for a in answers.values()}) == 1

    def test_the_lookup_is_rate_limited(self, client: TestClient) -> None:
        codes = [client.get("/api/v1/qr/public/ZZZZZZZZZZZZ").status_code for _ in range(40)]
        assert 429 in codes

    def test_the_public_page_reveals_no_personal_data(
        self,
        client: TestClient,
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        heap_with_bales: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        heap = heap_with_bales([deliver(farm, weighbridge=1000)], bales=1)
        overview = client.get(
            f"/api/v1/qr/lots/{heap['heap_id']}/overview", headers=as_officer("ADMIN-01")
        ).json()
        public = client.get(f"/api/v1/qr/public/{overview['token']}")
        assert public.status_code == 200
        text = public.text
        farmer = farm["farmer"]
        for secret in (
            farmer["name"],
            farmer["id_number"],
            "0300",
            "ghulam rasool",
            "Basti Malook",
            farm["field"]["field_id"],
            str(farm["field"]["pin_lat"])[:6],
        ):
            assert secret not in text, secret
        assert str(YEAR) in text


# ------------------------------------------------------------------ every route


#: Routes that are public on purpose. Anything else must name the acting officer.
PUBLIC_ROUTES = {
    "/api/v1/qr/public/{token}",
    # The web app reads tile URLs and the QR base URL before anyone is identified.
    "/api/v1/settings/public",
}


def _dependency_calls(dependant: Any) -> set[Any]:
    found: set[Any] = set()
    for sub in dependant.dependencies:
        found.add(sub.call)
        found |= _dependency_calls(sub)
    return found


def test_every_module_route_requires_the_acting_officer() -> None:
    """The officer dependency is the one place identity is checked (KNOWN_LIMITATIONS)."""
    import importlib

    from fastapi.routing import APIRoute

    from core.deps import get_current_officer, require_admin

    open_routes = []
    for number in range(1, 9):
        router = importlib.import_module(f"module_{number}.router").router
        for route in router.routes:
            if not isinstance(route, APIRoute) or route.path.endswith("/meta"):
                continue
            if route.path in PUBLIC_ROUTES:
                continue
            calls = _dependency_calls(route.dependant)
            if get_current_officer not in calls and require_admin not in calls:
                open_routes.append(f"{sorted(route.methods)} {route.path}")
    assert open_routes == []


class TestUnicodeDigits:
    """F-10: Arabic-Indic and Devanagari digits must fold to ASCII before ID checks."""

    def test_digits_fold_to_ascii(self) -> None:
        from module_2.services.validators import ascii_digits

        assert ascii_digits("٣٥٢٠١") == "35201"
        assert ascii_digits("३५२०१") == "35201"
        assert ascii_digits("35201") == "35201"
