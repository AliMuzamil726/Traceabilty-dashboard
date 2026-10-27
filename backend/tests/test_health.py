from datetime import datetime

from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "SAWIE"
    assert body["version"]
    assert body["database"] == {"reachable": True, "dialect": "sqlite"}
    server_time = datetime.fromisoformat(body["server_time"])
    assert server_time.utcoffset() is not None
    assert server_time.utcoffset().total_seconds() == 0


def test_health_sets_request_id_header(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-Id": "abc123"})
    assert response.headers["X-Request-Id"] == "abc123"
    generated = client.get("/api/health").headers["X-Request-Id"]
    assert len(generated) == 32


def test_health_degraded_when_db_unreachable(client: TestClient) -> None:
    db = client.app.state.db  # type: ignore[attr-defined]
    original = db.is_reachable
    db.is_reachable = lambda: False
    try:
        body = client.get("/api/health").json()
    finally:
        db.is_reachable = original
    assert body["status"] == "degraded"
    assert body["database"]["reachable"] is False


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in (
        "/api/v1/dashboard",
        "/api/v1/register",
        "/api/v1/fieldbook",
        "/api/v1/radar",
        "/api/v1/deliveries",
        "/api/v1/heaps",
        "/api/v1/qr",
        "/api/v1/settings",
    ):
        assert f"{prefix}/meta" in paths


def test_cors_allows_vite_origin(client: TestClient) -> None:
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.options(
            "/api/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert response.headers.get("access-control-allow-origin") == origin
