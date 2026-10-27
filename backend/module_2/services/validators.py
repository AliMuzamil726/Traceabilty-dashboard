"""Normalisation and validation of the identifiers Module 2 accepts.

Every rule here is enforced on the server regardless of what the client sent. Each
function either returns the normalised value or raises :class:`ValidationAppError`
with a message that says how to fix the input.

Two forms are kept for identifiers and phone numbers:

* a **normalised** form, which is the uniqueness key and never shown
  (digits only for a CNIC, E.164 for a phone);
* a **display** form, which keeps the formatting an officer reads
  (``12345-1234567-1``, ``0300-1234567``).
"""

from __future__ import annotations

import re
import unicodedata

from core import app_settings
from core.errors import ValidationAppError
from module_2.models import COUNTRY_GB, COUNTRY_PK, CROP_COTTON, CROP_HEMP

# Hemp ID numbers: the accepted length range. These constants are the DEFAULTS; the
# values in force come from Settings (``validation.hemp_id_*``), so a programme change
# is made on screen rather than in code. With no override the behaviour is identical.
HEMP_ID_MIN_DIGITS = 9
HEMP_ID_MAX_DIGITS = 13


def hemp_id_digits() -> tuple[int, int]:
    """The fewest and most digits a hemp ID number may have, as configured."""
    return (
        int(app_settings.setting_or("validation.hemp_id_min_digits", HEMP_ID_MIN_DIGITS)),
        int(app_settings.setting_or("validation.hemp_id_max_digits", HEMP_ID_MAX_DIGITS)),
    )


def unicode_names_allowed() -> bool:
    """True when a name may be written in any script (the default)."""
    return bool(app_settings.setting_or("validation.allow_unicode_names", True))


CNIC_DIGITS = 13

NAME_MIN = 3
NAME_MAX = 60
FARM_NAME_MIN = 2
FARM_NAME_MAX = 80
LICENCE_MIN = 6
LICENCE_MAX = 30
VILLAGE_MIN = 2
VILLAGE_MAX = 120

#: Letters in any script, plus the punctuation that appears in real names.
_NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_ '.\-]|[ '.\-])*$", re.UNICODE)
#: The same shape limited to Latin letters, used when Settings turns Unicode names off.
_LATIN_NAME_RE = re.compile(r"^[A-Za-z](?:[A-Za-z '.\-])*$")
_LICENCE_RE = re.compile(r"^[A-Z0-9-]+$")
_UK_POSTCODE_RE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$")
#: Unicode categories dropped by :func:`sanitise_text`: control characters (Cc),
#: formatting and bidi marks (Cf), unassigned and private use (Cn, Co),
#: surrogates (Cs) and the line and paragraph separators (Zl, Zp). Matching on
#: the category rather than on a list of literal characters keeps invisible
#: characters out of this source file and catches the ones a list would miss.
_STRIPPED_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Zl", "Zp"})


def _fail(message: str, field: str, code: str = "validation_error") -> ValidationAppError:
    return ValidationAppError(
        message,
        code=code,
        details={"fields": [{"field": field, "location": "body", "message": message}]},
    )


def sanitise_text(value: str | None, *, max_length: int | None = None) -> str | None:
    """Strip control characters, normalise to NFC and collapse runs of whitespace."""
    if value is None:
        return None
    normalised = unicodedata.normalize("NFC", value)
    cleaned = "".join(
        ch for ch in normalised if unicodedata.category(ch) not in _STRIPPED_CATEGORIES
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    return cleaned[:max_length] if max_length else cleaned


def ascii_digits(value: str) -> str:
    """Every Unicode decimal digit as its ASCII digit: Urdu, Arabic-Indic or full-width
    digits typed on another keyboard name the same person as 0-9 (audit F-10)."""
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in (value or ""))


def digits_only(value: str) -> str:
    return re.sub(r"[^0-9]", "", ascii_digits(value))


# --------------------------------------------------------------------------- names


def title_case_name(value: str) -> str:
    """Capitalise each word, leaving names that already carry internal capitals alone.

    ``ALI RAZA`` and ``ali raza`` both become ``Ali Raza``, while ``McDonald`` and
    ``O'Neill`` keep their own capitalisation.
    """
    words: list[str] = []
    for word in value.split(" "):
        if not word:
            continue
        core = word.strip("'.-")
        if core and (core.islower() or core.isupper()):
            words.append(word[:1].upper() + word[1:].lower())
        else:
            words.append(word)
    return " ".join(words)


def normalise_person_name(value: str | None, *, field: str, label: str) -> str:
    cleaned = sanitise_text(value)
    if not cleaned:
        raise _fail(f"{label} is required.", field)
    if len(cleaned) < NAME_MIN or len(cleaned) > NAME_MAX:
        raise _fail(f"{label} must be between {NAME_MIN} and {NAME_MAX} characters.", field)
    pattern = _NAME_RE if unicode_names_allowed() else _LATIN_NAME_RE
    if not pattern.match(cleaned):
        raise _fail(
            f"{label} may contain letters, spaces, apostrophes, hyphens and dots only.", field
        )
    return title_case_name(cleaned)


def normalise_farm_name(value: str | None, *, field: str = "farm_name") -> str:
    cleaned = sanitise_text(value, max_length=FARM_NAME_MAX)
    if not cleaned:
        raise _fail("Farm name is required.", field)
    if len(cleaned) < FARM_NAME_MIN:
        raise _fail(f"Farm name must be at least {FARM_NAME_MIN} characters.", field)
    return cleaned


def normalise_village(value: str | None, *, field: str = "village") -> str:
    cleaned = sanitise_text(value, max_length=VILLAGE_MAX)
    if not cleaned:
        raise _fail("Village or town is required.", field)
    if len(cleaned) < VILLAGE_MIN:
        raise _fail(f"Village or town must be at least {VILLAGE_MIN} characters.", field)
    return cleaned


# --------------------------------------------------------------------- ID numbers


def format_cnic(digits: str) -> str:
    """``1234512345671`` -> ``12345-1234567-1``."""
    return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"


def format_hemp_id(digits: str) -> str:
    """Group digits in threes for readability, merging a trailing single digit.

    ``123456789`` -> ``123 456 789`` and ``1234567890123`` -> ``123 456 789 0123``.
    """
    groups = [digits[i : i + 3] for i in range(0, len(digits), 3)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        groups[-2:] = [groups[-2] + groups[-1]]
    return " ".join(groups)


def normalise_id_number(
    value: str | None, crop: str, *, field: str = "id_number"
) -> tuple[str, str]:
    """Return ``(normalised, display)`` for a CNIC (cotton) or hemp ID number.

    The normalised form is the uniqueness key across every farmer: digits for a
    CNIC, upper-case alphanumerics for a hemp ID number.
    """
    raw = (value or "").strip()
    if not raw:
        raise _fail("ID number is required.", field)
    if crop == CROP_COTTON:
        digits = digits_only(raw)
        if len(digits) != CNIC_DIGITS:
            raise _fail(
                f"A CNIC has exactly {CNIC_DIGITS} digits, for example 12345-1234567-1.", field
            )
        return digits, format_cnic(digits)
    if crop == CROP_HEMP:
        compact = re.sub(r"[^0-9A-Za-z]", "", ascii_digits(raw)).upper()
        if not compact.isdigit():
            raise _fail("The ID number must contain digits only.", field)
        low, high = hemp_id_digits()
        if not low <= len(compact) <= high:
            raise _fail(f"The ID number must be between {low} and {high} digits.", field)
        return compact, format_hemp_id(compact)
    raise _fail(f"Unknown crop '{crop}'.", "crop")


def normalise_licence_no(value: str | None, *, field: str = "home_office_licence_no") -> str:
    cleaned = (sanitise_text(value) or "").upper().replace(" ", "")
    if not cleaned:
        raise _fail("The Home Office hemp licence number is required.", field)
    if not LICENCE_MIN <= len(cleaned) <= LICENCE_MAX:
        raise _fail(
            f"The licence number must be between {LICENCE_MIN} and {LICENCE_MAX} characters.",
            field,
        )
    if not _LICENCE_RE.match(cleaned):
        raise _fail("The licence number may contain letters, digits and dashes only.", field)
    return cleaned


# ------------------------------------------------------------------------- phones


def normalise_phone(
    value: str | None, country: str, *, field: str = "phone", required: bool = False
) -> tuple[str | None, str | None]:
    """Return ``(E.164, local display)``, or ``(None, None)`` for a blank optional phone."""
    raw = (value or "").strip()
    if not raw:
        if required:
            raise _fail("Phone number is required.", field)
        return None, None
    digits = digits_only(raw)
    if country == COUNTRY_PK:
        # 03001234567 | 923001234567 | 00923001234567 -> +923001234567
        if digits.startswith("0092"):
            digits = digits[4:]
        elif digits.startswith("92") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0"):
            digits = digits[1:]
        if len(digits) != 10 or not digits.startswith("3"):
            raise _fail("Enter a Pakistani mobile number, for example 0300-1234567.", field)
        return f"+92{digits}", f"0{digits[:3]}-{digits[3:]}"
    if country == COUNTRY_GB:
        # 07700900123 | 447700900123 | 00447700900123 -> +447700900123
        if digits.startswith("0044"):
            digits = digits[4:]
        elif digits.startswith("44") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0"):
            digits = digits[1:]
        if len(digits) != 10 or not digits.startswith("7"):
            raise _fail("Enter a UK mobile number, for example 07700 900123.", field)
        return f"+44{digits}", f"0{digits[:4]} {digits[4:]}"
    raise _fail(f"Unknown country '{country}'.", "country")


# ----------------------------------------------------------------------- postcode


def normalise_postcode(value: str | None, *, field: str = "postcode") -> str:
    """``sw1a1aa`` -> ``SW1A 1AA`` (one space before the final three characters)."""
    compact = re.sub(r"\s+", "", (value or "")).upper()
    if not compact:
        raise _fail("Postcode is required.", field)
    match = _UK_POSTCODE_RE.match(compact)
    if not match:
        raise _fail("Enter a valid UK postcode, for example CB23 6DP.", field)
    return f"{match.group(1)} {match.group(2)}"


def postcode_area(postcode: str) -> str:
    """The leading letters of a postcode (``CB23 6DP`` -> ``CB``)."""
    return re.match(r"^[A-Z]{1,2}", postcode.upper().strip()).group(0)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- misc


def validate_crop(value: str | None, *, field: str = "crop") -> str:
    crop = (value or "").strip().lower()
    if crop not in (CROP_COTTON, CROP_HEMP):
        raise _fail("Choose a crop programme: cotton or hemp.", field)
    return crop


def mask_id_number(display: str) -> str:
    """Mask every digit except the last four, keeping the formatting readable.

    ``12345-1234567-1`` -> ``*****-****567-1``. Used in lists and by any caller that
    is not allowed to see the full number.
    """
    kept = 4
    out: list[str] = []
    seen = 0
    total = sum(ch.isalnum() for ch in display)
    for ch in display:
        if ch.isalnum():
            seen += 1
            out.append(ch if seen > total - kept else "*")
        else:
            out.append(ch)
    return "".join(out)


def mask_phone(display: str | None) -> str | None:
    """``0300-1234567`` -> ``0300-****567``: enough to recognise, not enough to call."""
    if not display:
        return None
    kept = 3
    out: list[str] = []
    digit_positions = [i for i, ch in enumerate(display) if ch.isdigit()]
    mask_until = digit_positions[-kept] if len(digit_positions) > kept else len(display)
    for i, ch in enumerate(display):
        if ch.isdigit() and i >= 4 and i < mask_until:
            out.append("*")
        else:
            out.append(ch)
    return "".join(out)
