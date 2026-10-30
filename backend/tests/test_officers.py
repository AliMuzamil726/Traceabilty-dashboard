from fastapi import Depends
from fastapi.testclient import TestClient
from httpx import Response

from app.main import create_app
from core import passwords, sessions
from core.config import Settings
from core.deps import CurrentOfficer, require_admin
from scripts.seed import run_seed, stable_id
from shared.routers.officers import SIGNIN_LIMITER

DEFAULT_ID = stable_id("officer", "PK-MUL-01")
ADMIN_ID = stable_id("officer", "ADMIN-01")
UK_ID = stable_id("officer", "GB-EOE-01")


def test_missing_header_falls_back_to_default_officer_in_dev(client: TestClient) -> None:
    body = client.get("/api/v1/officers/me").json()
    assert body["id"] == DEFAULT_ID
    assert body["code"] == "PK-MUL-01"
    assert body["role"] == "officer"
    assert body["field_office_name"] == "Multan Field Office"
    assert body["is_admin"] is False


def test_header_selects_officer_and_admin_role(client: TestClient) -> None:
    uk = client.get("/api/v1/officers/me", headers={"X-Officer-Id": UK_ID}).json()
    assert uk["country"] == "GB"
    assert uk["field_office_name"] == "East of England Field Office"
    admin = client.get("/api/v1/officers/me", headers={"X-Officer-Id": ADMIN_ID}).json()
    assert admin["role"] == "admin"
    assert admin["is_admin"] is True


def test_unknown_officer_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/officers/me", headers={"X-Officer-Id": "nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "officer_not_found"


def test_production_requires_sign_in(settings: Settings) -> None:
    prod = settings.model_copy(
        update={
            "app_env": "production",
            "qr_ip_salt": "test-only-production-salt",
            "seed_on_start": False,
        }
    )
    app = create_app(prod)
    with TestClient(app) as client:
        # Production never runs the demo seed, so these tests insert it explicitly.
        with app.state.db.session_scope() as session:  # type: ignore[attr-defined]
            run_seed(session)
        response = client.get("/api/v1/officers/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "officer_required"

        # The header is a development tool only: in production it proves nothing.
        spoofed = client.get("/api/v1/officers/me", headers={"X-Officer-Id": ADMIN_ID})
        assert spoofed.status_code == 401

        # The directory stays public but carries no contact details.
        directory = client.get("/api/v1/officers/directory", params={"page_size": 5})
        assert directory.status_code == 200
        assert "email" not in directory.json()["items"][0]

        signed = client.post(
            "/api/v1/officers/sign-in",
            json={"officer_id": DEFAULT_ID, "password": passwords.DEFAULT_PASSWORD},
        )
        assert signed.status_code == 200
        token = signed.json()["token"]
        me = client.get(
            "/api/v1/officers/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json()["id"] == DEFAULT_ID


def test_directory_is_public_and_has_no_contact_details(client: TestClient) -> None:
    body = client.get("/api/v1/officers/directory", params={"page_size": 200}).json()
    assert body["total"] == 12
    assert set(body["items"][0]) == {
        "id",
        "full_name",
        "role",
        "country",
        "field_office",
        "active",
    }


def test_sign_in_returns_a_token_that_authenticates(client: TestClient) -> None:
    signed = client.post(
        "/api/v1/officers/sign-in",
        json={"officer_id": ADMIN_ID, "password": passwords.DEFAULT_PASSWORD},
    )
    assert signed.status_code == 200
    assert signed.json()["officer"]["id"] == ADMIN_ID
    token = signed.json()["token"]

    me = client.get(
        "/api/v1/officers/me", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert me["id"] == ADMIN_ID
    assert me["is_admin"] is True

    for candidate in ("not-a-real-token", "a.b", ".", "....", "%%%%.%%%%"):
        bad = client.get(
            "/api/v1/officers/me", headers={"Authorization": f"Bearer {candidate}"}
        )
        assert bad.status_code == 401, candidate
        assert bad.json()["error"]["code"] == "session_invalid", candidate

    # httpx refuses to send a non-ASCII header, so hostile bytes are checked directly.
    for hostile in ("é.abc", "\u0000.\u0000", "abc.é"):
        assert sessions.verify(client.app.state.settings, hostile) is None


def test_sign_in_is_rate_limited(client: TestClient) -> None:
    SIGNIN_LIMITER.reset()
    try:
        for _ in range(SIGNIN_LIMITER.limit):
            response = client.post(
                "/api/v1/officers/sign-in",
                json={"officer_id": DEFAULT_ID, "password": "wrong-password"},
            )
            assert response.status_code == 401
        blocked = client.post(
            "/api/v1/officers/sign-in",
            json={"officer_id": DEFAULT_ID, "password": passwords.DEFAULT_PASSWORD},
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"
    finally:
        SIGNIN_LIMITER.reset()


def test_require_admin_dependency(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/admin-only")
    def admin_only(officer: CurrentOfficer = Depends(require_admin)) -> dict[str, str]:
        return {"code": officer.code}

    with TestClient(app) as client:
        denied = client.get("/test/admin-only")
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "admin_required"
        allowed = client.get("/test/admin-only", headers={"X-Officer-Id": ADMIN_ID})
        assert allowed.json() == {"code": "ADMIN-01"}


def test_list_officers_paginated_and_filtered(client: TestClient) -> None:
    body = client.get("/api/v1/officers", params={"page_size": 5}).json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 12
    assert len(body["items"]) == 5
    assert body["items"][0]["role"] == "admin"

    gb = client.get("/api/v1/officers", params={"country": "gb"}).json()
    assert gb["total"] == 4
    assert all(o["country"] == "GB" for o in gb["items"])
    assert all(o["is_dummy"] for o in gb["items"])

    search = client.get("/api/v1/officers", params={"q": "batool"}).json()
    assert [o["full_name"] for o in search["items"]] == ["Sana Batool"]

    page3 = client.get("/api/v1/officers", params={"page": 3, "page_size": 5}).json()
    assert len(page3["items"]) == 2


def test_profile_phone_is_required_and_local(client: TestClient) -> None:
    def save(phone: str | None, *, officer: str = DEFAULT_ID) -> Response:
        return client.put(
            "/api/v1/officers/me",
            json={"phone": phone},
            headers={"X-Officer-Id": officer},
        )

    for phone, code in (
        ("", "phone_required"),
        ("   ", "phone_required"),
        (None, "phone_required"),
        ("0300-ABC1234", "phone_invalid"),
        ("030012345", "phone_invalid"),
        ("+447700900123", "phone_invalid"),
    ):
        response = save(phone)
        assert response.status_code == 422, phone
        assert response.json()["error"]["code"] == code, phone

    saved = save("+92 300 1234567")
    assert saved.status_code == 200
    assert saved.json()["phone"] == "0300-1234567"

    uk = save("+447700900123", officer=UK_ID)
    assert uk.status_code == 200
    assert uk.json()["phone"] == "07700 900123"


def test_get_officer_and_offices(client: TestClient) -> None:
    officer = client.get(f"/api/v1/officers/{UK_ID}").json()
    assert officer["field_office"]["code"] == "GB-EOE"
    assert client.get("/api/v1/officers/missing").status_code == 404

    offices = client.get("/api/v1/offices").json()
    assert offices["total"] == 5
    pk = client.get("/api/v1/offices", params={"country": "PK"}).json()
    assert {o["name"] for o in pk["items"]} == {
        "Multan Field Office",
        "Bahawalpur Field Office",
        "Lodhran Field Office",
    }
    one = client.get(f"/api/v1/offices/{pk['items'][0]['id']}")
    assert one.status_code == 200
    missing = client.get("/api/v1/offices/missing")
    assert missing.json()["error"]["code"] == "field_office_not_found"
