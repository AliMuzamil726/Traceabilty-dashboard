"""The crop clock as configuration: read it, preview a change, save it.

Settings (Module 8) must never write ``crop_clock_config`` itself, so the three
functions it needs live here, beside the table that owns them, and are re-exported from
``module_3.public_api`` (DECISIONS D-117). They validate, audit, bump the version and
publish ``config.changed``; the caller commits.

A clock change moves every field between Growing, Approaching, Ready and Overdue at
once, so :func:`preview_config_change` counts the moves before an administrator
confirms. Nothing stored changes: the status is computed from the sowing date, so new
days apply to the next calculation and never rewrite history.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from core import audit
from core.errors import ConflictError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from module_3.models import CropClockConfig
from module_3.repository import CropClockRepository
from module_3.services.clock import DEFAULT_CLOCKS

CONFIG_KEY = "config.crop_clock"
#: Lowest and highest day number a clock field may hold (days after sowing).
MIN_DAY = 1
MAX_DAY = 400


def get_config(session: Session) -> dict[str, Any]:
    """Every crop's clock, with the version Settings sends back on save."""
    repo = CropClockRepository(session)
    rows = repo.all()
    crops: dict[str, Any] = {}
    version = 0
    for crop, defaults in DEFAULT_CLOCKS.items():
        row = rows.get(crop)
        if row is None:
            approach, ready, window_end = defaults
            crops[crop] = {
                "approach_day": approach,
                "ready_day": ready,
                "window_end_day": window_end,
            }
        else:
            crops[crop] = {
                "approach_day": row.approach_day,
                "ready_day": row.ready_day,
                "window_end_day": row.window_end_day,
            }
            version = max(version, row.version)
    return {
        "key": CONFIG_KEY,
        "version": version,
        "crops": crops,
        "defaults": {
            crop: {"approach_day": a, "ready_day": r, "window_end_day": w}
            for crop, (a, r, w) in DEFAULT_CLOCKS.items()
        },
    }


def _validate(crop: str, values: dict[str, Any]) -> tuple[int, int, int]:
    try:
        approach = int(values["approach_day"])
        ready = int(values["ready_day"])
        window_end = int(values["window_end_day"])
    except (KeyError, TypeError, ValueError):
        raise ValidationAppError(
            f"The {crop} clock needs an approach day, a ready day and a window-end day.",
            code="invalid_clock",
        ) from None
    for name, day in (("approach", approach), ("ready", ready), ("window end", window_end)):
        if not MIN_DAY <= day <= MAX_DAY:
            raise ValidationAppError(
                f"The {crop} {name} day must be between {MIN_DAY} and {MAX_DAY} days after sowing.",
                code="invalid_clock",
            )
    if not approach < ready < window_end:
        raise ValidationAppError(
            f"For {crop}, the approach day must come before the ready day, and the ready day "
            "before the window-end day.",
            code="invalid_clock",
        )
    return approach, ready, window_end


def preview_config_change(session: Session, values: dict[str, Any]) -> dict[str, Any]:
    """How many fields would change readiness bucket if these days were saved.

    Counts every fieldbook with a sowing date in the current season: once with the
    clock in force and once with the proposed one, and reports the moves between the
    two. Reads only; nothing is written.
    """
    from module_3.services.clock import Clock, crop_status

    current = get_config(session)["crops"]
    proposed: dict[str, tuple[int, int, int]] = {}
    for crop, entry in values.items():
        if crop not in DEFAULT_CLOCKS:
            raise ValidationAppError(f"Unknown crop {crop!r}.", code="invalid_clock")
        proposed[crop] = _validate(crop, entry)

    today = date.today()
    moves: Counter[tuple[str, str]] = Counter()
    before_totals: Counter[str] = Counter()
    after_totals: Counter[str] = Counter()
    examined = 0

    for crop, (approach, ready, window_end) in proposed.items():
        now = current.get(crop, {})
        old_clock = Clock(
            crop,
            int(now.get("approach_day", approach)),
            int(now.get("ready_day", ready)),
            int(now.get("window_end_day", window_end)),
        )
        new_clock = Clock(crop, approach, ready, window_end)
        for sowing, harvested in _sowing_dates(session, crop):
            examined += 1
            before = crop_status(old_clock, sowing, today, harvested=harvested).status
            after = crop_status(new_clock, sowing, today, harvested=harvested).status
            before_totals[before] += 1
            after_totals[after] += 1
            if before != after:
                moves[(before, after)] += 1

    return {
        "fields_examined": examined,
        "fields_moving": sum(moves.values()),
        "before": dict(before_totals),
        "after": dict(after_totals),
        "moves": [
            {"from": a, "to": b, "fields": count} for (a, b), count in sorted(moves.items())
        ],
    }


def _sowing_dates(session: Session, crop: str) -> list[tuple[date, bool]]:
    """(sowing date, harvested) for every fieldbook of one crop that has a sowing date."""
    from sqlalchemy import select

    from module_3.models import Fieldbook
    from module_3.public_api import get_sowing_date
    from module_3.repository import EntryRepository
    from module_3.services import formschema as fs

    harvest_step = fs.load_definition(crop)["harvest_step"]
    out: list[tuple[date, bool]] = []
    books = session.execute(select(Fieldbook).where(Fieldbook.crop == crop)).scalars()
    entries = EntryRepository(session)
    for book in books:
        sowing = get_sowing_date(session, book.field_id, book.season_year)
        if sowing is None:
            continue
        out.append((sowing, bool(entries.for_step(book.id, harvest_step))))
    return out


def update_config(
    session: Session,
    values: dict[str, Any],
    officer_id: str | None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    """Save the clock for one or more crops. The caller commits."""
    repo = CropClockRepository(session)
    current = get_config(session)
    if expected_version is not None and expected_version != current["version"]:
        raise ConflictError(
            "The crop clock was changed by someone else while you were editing it. "
            "Reload to see the current days.",
            code="stale_version",
            details={"current_version": current["version"]},
        )

    changed: dict[str, Any] = {}
    for crop, entry in values.items():
        if crop not in DEFAULT_CLOCKS:
            raise ValidationAppError(f"Unknown crop {crop!r}.", code="invalid_clock")
        approach, ready, window_end = _validate(crop, entry)
        row = repo.for_crop(crop)
        before = (
            {
                "approach_day": row.approach_day,
                "ready_day": row.ready_day,
                "window_end_day": row.window_end_day,
            }
            if row is not None
            else None
        )
        if row is None:
            row = CropClockConfig(
                crop=crop,
                approach_day=approach,
                ready_day=ready,
                window_end_day=window_end,
                created_by=officer_id,
                updated_by=officer_id,
            )
            repo.add(row)
        else:
            row.approach_day = approach
            row.ready_day = ready
            row.window_end_day = window_end
            row.version += 1
            row.updated_by = officer_id
        after = {
            "approach_day": approach,
            "ready_day": ready,
            "window_end_day": window_end,
        }
        diff = audit.compute_diff(before, after)
        if diff:
            changed[crop] = after
            audit.record(
                "crop_clock_config", row.id, audit.ACTION_UPDATE, officer_id, diff, session=session
            )

    session.flush()
    if changed:
        bus.publish(
            CONFIG_CHANGED,
            {"key": CONFIG_KEY, "group": "programme", "crops": sorted(changed)},
            session=session,
        )
    return get_config(session)


__all__ = ["CONFIG_KEY", "get_config", "preview_config_change", "update_config"]
