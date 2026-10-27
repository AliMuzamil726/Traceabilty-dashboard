from fastapi.testclient import TestClient

from module_3 import events, meta


def test_meta_identity() -> None:
    assert meta.NUMBER == 3
    assert meta.FOLDER == "module_3"
    assert meta.API_PREFIX.startswith("/api/v1/")


def test_published_events_are_declared() -> None:
    from core.events import KNOWN_EVENTS

    assert set(events.PUBLISHES) <= KNOWN_EVENTS


def test_meta_endpoint(client: TestClient) -> None:
    response = client.get(f"{meta.API_PREFIX}/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["number"] == 3
    assert body["status"] == meta.STATUS
