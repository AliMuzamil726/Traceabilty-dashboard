"""Transport details: phone numbers per country and vehicle plates."""

from __future__ import annotations

import re

from core.errors import ValidationAppError

_PK_MOBILE = re.compile(r"^(?:\+92|0092|0)?(3\d{9})$")
_UK_MOBILE = re.compile(r"^(?:\+44|0044|0)?(7\d{9})$")
_VEHICLE = re.compile(r"^[A-Z0-9][A-Z0-9 -]{1,18}[A-Z0-9]$")


def _fail(field: str, message: str) -> ValidationAppError:
    return ValidationAppError(
        message,
        details={
            "fields": [{"field": field, "location": "body", "message": message, "type": "value"}]
        },
    )


def normalise_phone(raw: str, country: str) -> str:
    """Return E.164 for a Pakistani or UK mobile, or raise a field error."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if country == "PK":
        m = _PK_MOBILE.match(digits)
        if m:
            return f"+92{m.group(1)}"
        raise _fail("driver_phone", "Enter a Pakistani mobile number, for example 0300 1234567.")
    m = _UK_MOBILE.match(digits)
    if m:
        return f"+44{m.group(1)}"
    raise _fail("driver_phone", "Enter a UK mobile number, for example 07700 900123.")


def normalise_vehicle(raw: str) -> str:
    """Plates differ between Pakistan and the UK, so only shape is checked: uppercased."""
    value = re.sub(r"\s+", " ", (raw or "").strip().upper())
    if not _VEHICLE.match(value):
        raise _fail(
            "vehicle_no", "Enter the vehicle number, 3 to 20 letters, digits, spaces or hyphens."
        )
    return value


def clean_name(raw: str, field: str = "driver_name") -> str:
    value = re.sub(r"\s+", " ", (raw or "").strip())
    if not 2 <= len(value) <= 120:
        raise _fail(field, "Enter the driver's name.")
    return value
