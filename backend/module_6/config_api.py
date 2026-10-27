"""Heap and batch defaults as configuration.

These numbers are *copied into* a heap when it is opened, so an open heap keeps the
values it was given: a ratio changed today never re-prices yesterday's bales. That is
the whole point of freezing them on the heap, and the Settings screen says so.

Settings calls these functions; it never writes ``heap_config`` (DECISIONS D-117).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core import audit
from core.errors import ConflictError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from module_6.models import HeapConfig
from module_6.repository import HeapConfigRepository
from module_6.seed import DEFAULT_CONFIG

CONFIG_KEY = "config.heap"
FIELDS = (
    "default_outturn_ratio_pct",
    "default_bale_unit_kg",
    "default_shiv_pct",
    "default_dust_pct",
)
LABELS = {
    "default_outturn_ratio_pct": "outturn ratio",
    "default_bale_unit_kg": "bale unit",
    "default_shiv_pct": "shiv percentage",
    "default_dust_pct": "dust percentage",
}
#: Shiv and dust apply to hemp only; cotton leaves them empty.
OPTIONAL = ("default_shiv_pct", "default_dust_pct")


def get_config(session: Session) -> dict[str, Any]:
    repo = HeapConfigRepository(session)
    crops: dict[str, Any] = {}
    version = 0
    for crop, values in DEFAULT_CONFIG.items():
        row = repo.for_crop(crop)
        if row is None:
            crops[crop] = dict(zip(FIELDS, values, strict=True))
        else:
            crops[crop] = {name: getattr(row, name) for name in FIELDS}
            version = max(version, row.version)
    return {
        "key": CONFIG_KEY,
        "version": version,
        "crops": crops,
        "defaults": {
            crop: dict(zip(FIELDS, values, strict=True)) for crop, values in DEFAULT_CONFIG.items()
        },
    }


def _validate(crop: str, values: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for name in FIELDS:
        raw = values.get(name)
        if raw in (None, "") and name in OPTIONAL:
            out[name] = None
            continue
        try:
            number = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValidationAppError(
                f"The {crop} {LABELS[name]} must be a number.", code="invalid_config"
            ) from None
        if name.endswith("_pct") and not 0 < number <= 100:
            raise ValidationAppError(
                f"The {crop} {LABELS[name]} must be above 0 and at most 100 per cent.",
                code="invalid_config",
            )
        if name == "default_bale_unit_kg" and not 1 <= number <= 1000:
            raise ValidationAppError(
                f"The {crop} bale unit must be between 1 and 1,000 kg.", code="invalid_config"
            )
        out[name] = number
    shiv = out.get("default_shiv_pct") or 0
    dust = out.get("default_dust_pct") or 0
    if shiv + dust >= 100:
        raise ValidationAppError(
            f"For {crop}, shiv and dust together must stay below 100 per cent.",
            code="invalid_config",
        )
    return out


def update_config(
    session: Session,
    values: dict[str, Any],
    officer_id: str | None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    repo = HeapConfigRepository(session)
    current = get_config(session)
    if expected_version is not None and expected_version != current["version"]:
        raise ConflictError(
            "These defaults were changed by someone else while you were editing them. "
            "Reload to see the current values.",
            code="stale_version",
            details={"current_version": current["version"]},
        )
    changed: list[str] = []
    for crop, entry in values.items():
        if crop not in DEFAULT_CONFIG:
            raise ValidationAppError(f"Unknown crop {crop!r}.", code="invalid_config")
        cleaned = _validate(crop, entry)
        row = repo.for_crop(crop)
        before = {name: getattr(row, name) for name in FIELDS} if row is not None else None
        if row is None:
            row = HeapConfig(crop=crop, created_by=officer_id, updated_by=officer_id, **cleaned)
            repo.add(row)
        else:
            for name, number in cleaned.items():
                setattr(row, name, number)
            row.version += 1
            row.updated_by = officer_id
        diff = audit.compute_diff(before, cleaned)
        if diff:
            changed.append(crop)
            audit.record(
                "heap_config", row.id, audit.ACTION_UPDATE, officer_id, diff, session=session
            )
    session.flush()
    if changed:
        bus.publish(
            CONFIG_CHANGED,
            {"key": CONFIG_KEY, "group": "operations", "crops": sorted(changed)},
            session=session,
        )
    return get_config(session)


__all__ = ["CONFIG_KEY", "FIELDS", "get_config", "update_config"]
