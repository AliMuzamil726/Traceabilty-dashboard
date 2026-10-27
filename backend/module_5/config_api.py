"""Delivery tolerances as configuration: the weight variance and moisture thresholds.

Settings calls these; it never writes ``delivery_config`` (DECISIONS D-117). A change
applies to the next load weighed in. Loads already received keep the variance level
they were given, because that judgement was made against the rule in force at the time.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core import audit
from core.errors import ConflictError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from module_5.models import DeliveryConfig
from module_5.repository import ConfigRepository
from module_5.seed import DEFAULT_CONFIG

CONFIG_KEY = "config.delivery"
FIELDS = ("variance_warn_pct", "variance_flag_pct", "moisture_warn_pct")
LABELS = {
    "variance_warn_pct": "warning variance",
    "variance_flag_pct": "flag variance",
    "moisture_warn_pct": "moisture warning",
}


def get_config(session: Session) -> dict[str, Any]:
    repo = ConfigRepository(session)
    crops: dict[str, Any] = {}
    version = 0
    for crop, (warn, flag, moisture) in DEFAULT_CONFIG.items():
        row = repo.for_crop(crop)
        if row is None:
            crops[crop] = {
                "variance_warn_pct": warn,
                "variance_flag_pct": flag,
                "moisture_warn_pct": moisture,
            }
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


def _validate(crop: str, values: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in FIELDS:
        try:
            number = float(values[name])
        except (KeyError, TypeError, ValueError):
            raise ValidationAppError(
                f"The {crop} {LABELS[name]} must be a percentage.", code="invalid_config"
            ) from None
        if not 0 < number <= 100:
            raise ValidationAppError(
                f"The {crop} {LABELS[name]} must be above 0 and at most 100 per cent.",
                code="invalid_config",
            )
        out[name] = number
    if out["variance_warn_pct"] >= out["variance_flag_pct"]:
        raise ValidationAppError(
            f"For {crop}, the warning variance must be smaller than the flag variance.",
            code="invalid_config",
        )
    return out


def update_config(
    session: Session,
    values: dict[str, Any],
    officer_id: str | None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    repo = ConfigRepository(session)
    current = get_config(session)
    if expected_version is not None and expected_version != current["version"]:
        raise ConflictError(
            "These thresholds were changed by someone else while you were editing them. "
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
            row = DeliveryConfig(crop=crop, created_by=officer_id, updated_by=officer_id, **cleaned)
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
                "delivery_config", row.id, audit.ACTION_UPDATE, officer_id, diff, session=session
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
