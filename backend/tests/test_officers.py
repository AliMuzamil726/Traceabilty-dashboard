from fastapi import Depends
from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings
from core.deps import CurrentOfficer, require_admin
from scripts.seed import stable_id

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


def test_production_requires_header(settings: Settings) -> None:
    prod = settings.model_copy(update={"app_env": "production"})
    with TestClient(create_app(prod)) as client:
        response = client.get("/api/v1/officers/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "officer_required"
        ok = client.get("/api/v1/officers/me", headers={"X-Officer-Id": DEFAULT_ID})
        assert ok.status_code == 200


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
