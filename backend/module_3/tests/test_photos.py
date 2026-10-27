"""Photo upload: content checks, limits, thumbnails, serving and removal."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from core.config import Settings
from module_3.tests.conftest import FB

Farm = dict[str, Any]


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (800, 600)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 96, 57)).save(buf, format=fmt)
    return buf.getvalue()


def upload(
    client: TestClient, book: Farm, headers: dict[str, str], *files: tuple[str, bytes, str]
) -> Any:
    return client.post(
        f"{FB}/books/{book['id']}/photos", files=[("files", f) for f in files], headers=headers
    )


def test_valid_images_are_stored_with_thumbnails(
    client: TestClient,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    settings: Settings,
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    r = upload(
        client,
        book,
        farm["headers"],
        ("a.jpg", image_bytes("JPEG"), "image/jpeg"),
        ("b.png", image_bytes("PNG"), "image/png"),
        ("c.webp", image_bytes("WEBP"), "image/webp"),
    )
    assert r.status_code == 201, r.text
    photos = r.json()["photos"]
    assert len(photos) == 3
    folder = Path(settings.upload_path) / "uploads" / "fieldbook" / book["id"]
    assert folder.is_dir()
    thumb = client.get(
        f"{FB}/books/{book['id']}/photos/{photos[0]['id']}",
        params={"size": "thumb"},
        headers=farm["headers"],
    )
    assert thumb.status_code == 200
    assert max(Image.open(io.BytesIO(thumb.content)).size) <= 320
    full = client.get(f"{FB}/books/{book['id']}/photos/{photos[0]['id']}", headers=farm["headers"])
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("image/")


def test_a_renamed_non_image_is_refused(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    r = upload(client, book, farm["headers"], ("x.jpg", b"%PDF-1.4 not an image", "image/jpeg"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "photo_invalid"


def test_other_image_types_are_refused(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    r = upload(client, book, farm["headers"], ("x.gif", image_bytes("GIF"), "image/gif"))
    assert r.json()["error"]["code"] == "photo_type_not_allowed"


def test_oversize_files_are_refused(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    r = upload(
        client, book, farm["headers"], ("big.jpg", b"\xff" * (8 * 1024 * 1024 + 10), "image/jpeg")
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "photo_too_large"


def test_at_most_eight_photos(
    client: TestClient, make_farm: Callable[..., Farm], open_book: Callable[..., Farm]
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    small = image_bytes(size=(40, 40))
    assert (
        upload(
            client, book, farm["headers"], *[(f"{i}.jpg", small, "image/jpeg") for i in range(8)]
        ).status_code
        == 201
    )
    r = upload(client, book, farm["headers"], ("9.jpg", small, "image/jpeg"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "photo_limit"


def test_deleting_a_photo_and_a_draft_removes_files(
    client: TestClient,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    settings: Settings,
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    photos = upload(
        client,
        book,
        farm["headers"],
        ("a.jpg", image_bytes(), "image/jpeg"),
        ("b.jpg", image_bytes(), "image/jpeg"),
    ).json()["photos"]
    folder = Path(settings.upload_path) / "uploads" / "fieldbook" / book["id"]
    before = len(list(folder.iterdir()))
    state = client.delete(
        f"{FB}/books/{book['id']}/photos/{photos[0]['id']}", headers=farm["headers"]
    ).json()
    assert len(state["photos"]) == 1
    assert len(list(folder.iterdir())) == before - 2
    assert client.delete(f"{FB}/books/{book['id']}", headers=farm["headers"]).status_code == 204
    assert not folder.exists()


def test_another_officer_cannot_fetch_a_photo(
    client: TestClient,
    make_farm: Callable[..., Farm],
    open_book: Callable[..., Farm],
    as_officer: Callable[[str], dict[str, str]],
) -> None:
    farm = make_farm("cotton")
    book = open_book(farm)
    photo = upload(client, book, farm["headers"], ("a.jpg", image_bytes(), "image/jpeg")).json()[
        "photos"
    ][0]
    r = client.get(f"{FB}/books/{book['id']}/photos/{photo['id']}", headers=as_officer("PK-BWP-01"))
    assert r.status_code == 403
