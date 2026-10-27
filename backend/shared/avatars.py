"""Profile photos.

An upload is trusted for nothing: the file name and the declared content type are
ignored, Pillow decodes the bytes and the decoded format decides whether it is a JPEG,
PNG or WebP. The image is turned upright from its EXIF orientation, cropped to a
square and re-encoded small, which also drops any payload riding along in the original
file. One file per officer, replaced on every upload.

Files live under ``{UPLOAD_DIR}/uploads/avatars/``; the path stored on the officer row
is relative to ``UPLOAD_DIR`` so the folder can move.
"""

from __future__ import annotations

import contextlib
import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from core.errors import AppError, ValidationAppError

MAX_BYTES = 5 * 1024 * 1024
SIZE = 320
SUBDIR = Path("uploads") / "avatars"

#: Pillow format name -> file extension
ACCEPTED = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MIME = "image/jpeg"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "photo_too_large"


def store_avatar(upload_root: Path, officer_id: str, content: bytes) -> str:
    """Validate, square off and write the photo. Returns the path to store on the row."""
    if len(content) > MAX_BYTES:
        raise PayloadTooLargeError(
            "That photo is larger than 5 MB.", details={"size_bytes": len(content)}
        )
    if not content:
        raise ValidationAppError("That photo is empty.", code="photo_invalid")
    try:
        with Image.open(io.BytesIO(content)) as probe:
            probe.verify()  # structural check; the image must be reopened afterwards
        image = Image.open(io.BytesIO(content))
        fmt = image.format or ""
        image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationAppError(
            "That file is not a readable image.", code="photo_invalid"
        ) from exc
    if fmt not in ACCEPTED:
        raise ValidationAppError(
            "A photo must be a JPEG, PNG or WebP image.", code="photo_invalid"
        )

    square = ImageOps.fit(ImageOps.exif_transpose(image) or image, (SIZE, SIZE), Image.LANCZOS)
    folder = upload_root / SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{officer_id}-{uuid.uuid4().hex[:8]}.jpg"
    square.convert("RGB").save(folder / name, "JPEG", quality=85, optimize=True)
    return str(SUBDIR / name)


def remove_avatar(upload_root: Path, stored_path: str | None) -> None:
    """Delete the file behind a stored path. A missing file is not an error."""
    if not stored_path:
        return
    # A locked or unreadable file is not worth failing a request over.
    with contextlib.suppress(OSError):
        (upload_root / stored_path).unlink(missing_ok=True)


def avatar_file(upload_root: Path, stored_path: str | None) -> Path | None:
    if not stored_path:
        return None
    path = upload_root / stored_path
    return path if path.is_file() else None


__all__ = [
    "MAX_BYTES",
    "MIME",
    "PayloadTooLargeError",
    "avatar_file",
    "remove_avatar",
    "store_avatar",
]
