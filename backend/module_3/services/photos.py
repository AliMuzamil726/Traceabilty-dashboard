"""Fieldbook photo storage.

An upload is trusted for nothing: the file name and the declared content type are
ignored, Pillow decodes the bytes and the decoded format decides whether it is a
JPEG, PNG or WebP. The image is turned upright from its EXIF orientation (phones
store most photos sideways with a rotation flag), re-encoded, and given a thumbnail.
Re-encoding also drops any payload riding along in the original file.

Files live under ``{UPLOAD_DIR}/uploads/fieldbook/{fieldbook_id}/``. Paths stored in
the database are relative to ``UPLOAD_DIR`` so the folder can move.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from core.errors import AppError, ValidationAppError

MAX_PHOTOS = 8
MAX_BYTES = 8 * 1024 * 1024
THUMB_SIZE = (320, 320)

#: Pillow format name -> (mime, file extension)
ACCEPTED = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}

SUBDIR = Path("uploads") / "fieldbook"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "photo_too_large"


@dataclass(frozen=True)
class StoredPhoto:
    file_path: str
    thumb_path: str
    mime: str
    size_bytes: int
    width: int
    height: int


def book_dir(upload_root: Path, fieldbook_id: str) -> Path:
    return upload_root / SUBDIR / fieldbook_id


def store_photo(
    upload_root: Path, fieldbook_id: str, content: bytes, original_name: str
) -> StoredPhoto:
    """Validate an upload by its content and write the image and its thumbnail."""
    if len(content) > MAX_BYTES:
        raise PayloadTooLargeError(
            f"{original_name} is larger than 8 MB.",
            details={"name": original_name, "size_bytes": len(content)},
        )
    if not content:
        raise ValidationAppError(f"{original_name} is empty.", code="photo_invalid")
    try:
        with Image.open(io.BytesIO(content)) as probe:
            probe.verify()  # structural check; the image must be reopened afterwards
        image = Image.open(io.BytesIO(content))
        fmt = image.format or ""
        image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationAppError(
            f"{original_name} is not a readable image.",
            code="photo_invalid",
            details={"name": original_name},
        ) from exc
    if fmt not in ACCEPTED:
        raise ValidationAppError(
            f"{original_name} is a {fmt or 'unknown'} file. Use JPEG, PNG or WebP.",
            code="photo_type_not_allowed",
            details={"name": original_name, "format": fmt},
        )

    mime, ext = ACCEPTED[fmt]
    upright = ImageOps.exif_transpose(image) or image
    if fmt == "JPEG" and upright.mode not in ("RGB", "L"):
        upright = upright.convert("RGB")

    folder = book_dir(upload_root, fieldbook_id)
    folder.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex
    full = folder / f"{stem}.{ext}"
    thumb = folder / f"{stem}_thumb.jpg"

    save_kwargs = {"quality": 88} if fmt in ("JPEG", "WEBP") else {}
    upright.save(full, format=fmt, **save_kwargs)
    preview = upright.copy()
    preview.thumbnail(THUMB_SIZE)
    if preview.mode not in ("RGB", "L"):
        preview = preview.convert("RGB")
    preview.save(thumb, format="JPEG", quality=80)

    return StoredPhoto(
        file_path=(SUBDIR / fieldbook_id / full.name).as_posix(),
        thumb_path=(SUBDIR / fieldbook_id / thumb.name).as_posix(),
        mime=mime,
        size_bytes=full.stat().st_size,
        width=upright.width,
        height=upright.height,
    )


def remove_files(upload_root: Path, *relative: str) -> None:
    for rel in relative:
        path = (upload_root / rel).resolve()
        if upload_root.resolve() in path.parents and path.is_file():
            path.unlink()


def remove_book_dir(upload_root: Path, fieldbook_id: str) -> None:
    folder = book_dir(upload_root, fieldbook_id)
    if folder.is_dir():
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()
        folder.rmdir()
