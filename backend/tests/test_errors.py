from fastapi import Query
from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings
from core.errors import ConflictError


def _assert_envelope(body: dict, code: str) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    _assert_envelope(response.json(), "not_found")


def test_method_not_allowed_uses_envelope(client: TestClient) -> None:
    response = client.delete("/api/health")
    assert response.status_code == 405
    _assert_envelope(response.json(), "method_not_allowed")


def test_validation_error_has_per_field_details(client: TestClient) -> None:
    response = client.get("/api/v1/officers", params={"page": 0, "page_size": 999})
    assert response.status_code == 422
    body = response.json()
    _assert_envelope(body, "validation_error")
    fields = {f["field"] for f in body["error"]["details"]["fields"]}
    assert fields == {"page", "page_size"}


def test_app_error_and_unhandled_error(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/test/conflict")
    def conflict() -> None:
        raise ConflictError("Already exists.", code="thing_exists", details={"id": "x"})

    @app.get("/test/boom")
    def boom() -> None:
        raise RuntimeError("secret internals")

    @app.get("/test/body")
    def needs_int(n: int = Query(...)) -> dict[str, int]:
        return {"n": n}

    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/test/conflict")
        assert r.status_code == 409
        _assert_envelope(r.json(), "thing_exists")
        assert r.json()["error"]["details"] == {"id": "x"}

        r = client.get("/test/boom")
        assert r.status_code == 500
        _assert_envelope(r.json(), "internal_error")
        assert "secret" not in r.text
        assert r.json()["error"]["details"]["request_id"]

        r = client.get("/test/body", params={"n": "abc"})
        assert r.status_code == 422
        assert r.json()["error"]["details"]["fields"][0]["field"] == "n"
