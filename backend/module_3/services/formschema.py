"""Schema-driven form engine: the single source of truth for every fieldbook form.

The form definitions in ``module_3/form_definitions/{crop}.json`` are served unchanged
to the frontend (``GET /schemas/{crop}``), which renders from them, and the same
definitions validate every save here. A field, range, unit, list or rule therefore
exists in exactly one place, and the two sides cannot drift.

What a definition can express:

* field types: text, number, date, select, multiselect, yesno, dates, paired_number,
  photos (photos are stored separately, so they are skipped here);
* per field: required, min, max, integer, unit, list_key, default_from, readonly,
  visible_if (a hidden field is neither validated nor stored), not_future (dates,
  default true), warn_above / warn_values (non-blocking), computed values;
* per step: rules that look at other fields, other entries and other steps, each with
  a level of ``error`` (blocks the save) or ``warning`` (recorded, never blocks).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.errors import NotFoundError

DEFINITIONS_DIR = Path(__file__).resolve().parents[1] / "form_definitions"

FIELD_TYPES = frozenset(
    {"text", "number", "date", "select", "multiselect", "yesno", "dates", "paired_number", "photos"}
)
RULE_KINDS = frozenset(
    {
        "max_ref",
        "lte_sum",
        "date_vs_sowing",
        "date_on_or_after",
        "date_not_before_ref",
        "unique_across_entries",
    }
)
TEXT_MAX = 500

ERROR = "error"
WARNING = "warning"


# --------------------------------------------------------------------------- loading


class SchemaDefinitionError(ValueError):
    """A form definition file is malformed. Raised at load time, never at request time."""


def _check_definition(doc: dict[str, Any]) -> None:
    crop = doc.get("crop")
    if crop not in ("cotton", "hemp"):
        raise SchemaDefinitionError(f"Unknown crop {crop!r}")
    for key in ("version", "steps", "area_ref", "sowing_date_ref", "pickup", "harvest_step"):
        if key not in doc:
            raise SchemaDefinitionError(f"{crop}: missing top-level key '{key}'")
    seen_steps: set[str] = set()
    orders: list[int] = []
    for step in doc["steps"]:
        for key in ("key", "title", "order", "repeatable", "required", "fields"):
            if key not in step:
                raise SchemaDefinitionError(f"{crop}: a step lacks '{key}'")
        if step["key"] in seen_steps:
            raise SchemaDefinitionError(f"{crop}: duplicate step '{step['key']}'")
        seen_steps.add(step["key"])
        orders.append(step["order"])
        field_keys: set[str] = set()
        for f in step["fields"]:
            if f.get("type") not in FIELD_TYPES:
                raise SchemaDefinitionError(f"{crop}.{step['key']}: bad type on {f.get('key')}")
            if f["key"] in field_keys:
                raise SchemaDefinitionError(f"{crop}.{step['key']}: duplicate field {f['key']}")
            field_keys.add(f["key"])
            if f["type"] in ("select", "multiselect", "yesno") and not f.get("list_key"):
                raise SchemaDefinitionError(f"{crop}.{step['key']}.{f['key']}: needs list_key")
            if f["type"] == "paired_number" and not f.get("parts"):
                raise SchemaDefinitionError(f"{crop}.{step['key']}.{f['key']}: needs parts")
        for f in step["fields"]:
            cond = f.get("visible_if")
            if cond and cond["field"] not in field_keys:
                raise SchemaDefinitionError(
                    f"{crop}.{step['key']}.{f['key']}: visible_if names unknown field"
                )
        for rule in step.get("rules", []):
            if rule.get("kind") not in RULE_KINDS:
                raise SchemaDefinitionError(f"{crop}.{step['key']}: unknown rule {rule}")
            if rule["field"] not in field_keys:
                raise SchemaDefinitionError(f"{crop}.{step['key']}: rule names unknown field")
            if rule.get("level") not in (ERROR, WARNING):
                raise SchemaDefinitionError(f"{crop}.{step['key']}: rule needs a level")
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise SchemaDefinitionError(f"{crop}: step orders must run 1..n")
    pickup = doc["pickup"]
    if pickup["step"] not in seen_steps:
        raise SchemaDefinitionError(f"{crop}: pickup step unknown")


@lru_cache(maxsize=4)
def load_definition(crop: str) -> dict[str, Any]:
    """The parsed, checked definition for one crop."""
    path = DEFINITIONS_DIR / f"{crop}.json"
    if crop not in ("cotton", "hemp") or not path.is_file():
        raise NotFoundError(
            f"There is no fieldbook form for '{crop}'.",
            code="fieldbook_schema_not_found",
            details={"crop": crop},
        )
    doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    _check_definition(doc)
    doc["steps"] = sorted(doc["steps"], key=lambda s: s["order"])
    return doc


def get_step(definition: Mapping[str, Any], step_key: str) -> dict[str, Any]:
    for step in definition["steps"]:
        if step["key"] == step_key:
            return dict(step)
    raise NotFoundError(
        f"'{step_key}' is not a step of the {definition['crop']} fieldbook.",
        code="fieldbook_step_unknown",
        details={"step_key": step_key, "crop": definition["crop"]},
    )


def list_keys(definition: Mapping[str, Any]) -> set[str]:
    return {
        f["list_key"] for step in definition["steps"] for f in step["fields"] if f.get("list_key")
    }


def ref_parts(ref: str) -> tuple[str, ...]:
    """``step.sowing.sowing_date`` -> ``("step", "sowing", "sowing_date")``."""
    return tuple(ref.split("."))


# ------------------------------------------------------------------------- context


@dataclass
class ValidationContext:
    """Everything a validation may look at besides the entry itself."""

    today: date
    #: ``list_key`` -> allowed values (already scoped to the crop and country).
    options: Callable[[str], set[str]]
    #: ``field.area_acre``, ``farmer.licence``, ``season.variety`` ...
    values: dict[str, Any] = field(default_factory=dict)
    #: Saved data of single-entry steps, ``{step_key: data}``.
    single_steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Other saved entries of the step being validated (for uniqueness).
    sibling_entries: list[dict[str, Any]] = field(default_factory=list)
    #: Reference to the sowing date in this crop's schema.
    sowing_ref: str = ""

    def resolve(self, ref: str) -> Any:
        parts = ref_parts(ref)
        if parts[0] == "step" and len(parts) == 3:
            return (self.single_steps.get(parts[1]) or {}).get(parts[2])
        return self.values.get(ref)

    def sowing_date(self) -> date | None:
        return parse_date(self.resolve(self.sowing_ref)) if self.sowing_ref else None


@dataclass
class Issue:
    field: str
    level: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "level": self.level, "message": self.message}


@dataclass
class EntryResult:
    clean: dict[str, Any]
    errors: list[Issue]
    warnings: list[Issue]

    @property
    def ok(self) -> bool:
        return not self.errors


# ------------------------------------------------------------------------- helpers


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def is_visible(f: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    """Evaluate ``visible_if`` against the entry's own (raw) values."""
    cond = f.get("visible_if")
    if not cond:
        return True
    current = values.get(cond["field"])
    if "in" in cond:
        return current in cond["in"]
    if "not_in" in cond:
        # A condition on an unanswered field hides nothing until it is answered.
        return current is None or current == "" or current not in cond["not_in"]
    return True


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _fmt(number: float) -> str:
    return f"{number:g}"


def compute(f: Mapping[str, Any], clean: Mapping[str, Any]) -> Any:
    spec = f["computed"]
    kind = spec["kind"]
    if kind == "count":
        items = clean.get(spec["of"]) or []
        return len(items)
    if kind == "days_between":
        start, end = parse_date(clean.get(spec["from"])), parse_date(clean.get(spec["to"]))
        return (end - start).days if start and end else None
    if kind == "product":
        values = [_num(clean.get(k)) for k in spec["of"]]
        if any(v is None for v in values):
            return None
        result = 1.0
        for v in values:
            result *= v  # type: ignore[operator]
        return round(result, 4)
    raise SchemaDefinitionError(f"Unknown computed kind {kind}")


# ---------------------------------------------------------------------- validation


def _coerce(f: Mapping[str, Any], raw: Any, ctx: ValidationContext, errors: list[Issue]) -> Any:
    key, ftype, label = f["key"], f["type"], f["label"]

    def fail(message: str, path: str | None = None) -> None:
        errors.append(Issue(path or key, ERROR, message))

    if ftype == "text":
        if not isinstance(raw, str):
            fail(f"{label} must be text.")
            return None
        value = re.sub(r"\s+", " ", raw).strip()
        if len(value) > TEXT_MAX:
            fail(f"{label} must be {TEXT_MAX} characters or fewer.")
            return None
        return value or None

    if ftype == "number":
        value = _num(raw)
        if value is None:
            fail(f"{label} must be a number.")
            return None
        if f.get("integer") and not float(value).is_integer():
            fail(f"{label} must be a whole number.")
            return None
        unit = f" {f['unit']}" if f.get("unit") else ""
        if "min" in f and value < f["min"]:
            fail(f"{label} must be at least {_fmt(f['min'])}{unit}.")
            return None
        if "max" in f and value > f["max"]:
            fail(f"{label} must be at most {_fmt(f['max'])}{unit}.")
            return None
        return int(value) if f.get("integer") else value

    if ftype == "date":
        value = parse_date(raw)
        if value is None:
            fail(f"{label} must be a date (YYYY-MM-DD).")
            return None
        if f.get("not_future", True) and value > ctx.today:
            fail(f"{label} cannot be in the future.")
            return None
        return value.isoformat()

    if ftype in ("select", "yesno"):
        if not isinstance(raw, str) or raw not in ctx.options(f["list_key"]):
            fail(f"Choose a {label.lower()} from the list.")
            return None
        return raw

    if ftype == "multiselect":
        if not isinstance(raw, list) or not all(isinstance(v, str) for v in raw):
            fail(f"{label} must be a list of choices.")
            return None
        allowed = ctx.options(f["list_key"])
        bad = [v for v in raw if v not in allowed]
        if bad:
            fail(f"{label} contains a choice that is not in the list.")
            return None
        return list(dict.fromkeys(raw))

    if ftype == "dates":
        if not isinstance(raw, list):
            fail(f"{label} must be a list of dates.")
            return None
        parsed: list[date] = []
        for item in raw:
            d = parse_date(item)
            if d is None:
                fail(f"Every entry in {label.lower()} must be a date.")
                return None
            if f.get("not_future", True) and d > ctx.today:
                fail(f"{label} cannot include a future date.")
                return None
            parsed.append(d)
        return [d.isoformat() for d in sorted(set(parsed))]

    if ftype == "paired_number":
        if not isinstance(raw, dict):
            fail(f"{label} must give a value for each part.")
            return None
        out: dict[str, float] = {}
        for part in f["parts"]:
            pv = raw.get(part["key"])
            if _empty(pv):
                continue
            number = _num(pv)
            path = f"{key}.{part['key']}"
            if number is None:
                fail(f"{part['label']} must be a number.", path)
                return None
            if "min" in part and number < part["min"]:
                fail(f"{part['label']} must be at least {_fmt(part['min'])}.", path)
                return None
            if "max" in part and number > part["max"]:
                fail(f"{part['label']} must be at most {_fmt(part['max'])}.", path)
                return None
            out[part["key"]] = number
        if f.get("required") and len(out) != len(f["parts"]):
            fail(f"Give every part of {label.lower()}.")
            return None
        return out or None

    raise SchemaDefinitionError(f"Unhandled field type {ftype}")  # pragma: no cover


def _apply_rules(
    step: Mapping[str, Any],
    clean: dict[str, Any],
    ctx: ValidationContext,
    errors: list[Issue],
    warnings: list[Issue],
    *,
    skip_fields: Iterable[str] = (),
) -> None:
    skip = set(skip_fields)
    sowing = ctx.sowing_date()
    for rule in step.get("rules", []):
        name = rule["field"]
        if name in skip or _empty(clean.get(name)):
            continue
        value = clean[name]
        hit = False
        message = rule["message"]

        kind = rule["kind"]
        if kind == "max_ref":
            ref = _num(ctx.resolve(rule["ref"]))
            if ref is None:
                continue
            limit = ref * float(rule.get("factor", 1))
            if rule.get("multiply_by_field"):
                factor = _num(clean.get(rule["multiply_by_field"]))
                if factor is None:
                    continue
                limit *= factor
            hit = float(value) > limit + 1e-9
            message = message.replace("{ref}", _fmt(round(ref, 2)))
        elif kind == "lte_sum":
            parts = [_num(clean.get(k)) for k in rule["sum"]]
            if any(p is None for p in parts):
                continue
            hit = float(value) > sum(parts)  # type: ignore[arg-type]
        elif kind == "date_vs_sowing":
            if sowing is None:
                continue
            d = parse_date(value)
            if d is None:
                continue
            op = rule["op"]
            if op == "after":
                hit = d <= sowing
            elif op == "not_after":
                hit = d > sowing
            elif op == "not_before_minus":
                hit = (sowing - d).days > int(rule["days"])
        elif kind == "date_on_or_after":
            d, other = parse_date(value), parse_date(clean.get(rule["other"]))
            if d is None or other is None:
                continue
            hit = d < other
        elif kind == "date_not_before_ref":
            d, ref_date = parse_date(value), parse_date(ctx.resolve(rule["ref"]))
            if d is None or ref_date is None:
                continue
            hit = d < ref_date
        elif kind == "unique_across_entries":
            hit = any(e.get(name) == value for e in ctx.sibling_entries)

        if hit:
            issue = Issue(name, rule["level"], message)
            (errors if rule["level"] == ERROR else warnings).append(issue)


def validate_entry(
    step: Mapping[str, Any], raw: Mapping[str, Any], ctx: ValidationContext
) -> EntryResult:
    """Validate and normalise one entry of one step against its definition.

    Hidden fields are dropped, computed fields are recomputed (never trusted from the
    client), read-only fields with a ``default_from`` take the server's value.
    """
    raw = dict(raw or {})
    clean: dict[str, Any] = {}
    errors: list[Issue] = []
    warnings: list[Issue] = []
    failed: set[str] = set()

    for f in step["fields"]:
        key, ftype = f["key"], f["type"]
        if ftype == "photos" or f.get("computed"):
            continue
        if not is_visible(f, raw):
            continue
        if f.get("readonly") and f.get("default_from"):
            clean[key] = ctx.values.get(f["default_from"])
            continue
        value = raw.get(key)
        if _empty(value):
            if f.get("required"):
                errors.append(Issue(key, ERROR, f"{f['label']} is required."))
                failed.add(key)
            continue
        before = len(errors)
        coerced = _coerce(f, value, ctx, errors)
        if len(errors) > before:
            failed.add(key)
            continue
        if coerced is not None:
            clean[key] = coerced

    for f in step["fields"]:
        if f.get("computed"):
            value = compute(f, clean)
            if value is not None:
                clean[f["key"]] = value

    for f in step["fields"]:
        key = f["key"]
        if key not in clean:
            continue
        if "warn_above" in f and _num(clean[key]) is not None and clean[key] > f["warn_above"]:
            warnings.append(Issue(key, WARNING, f.get("warn_message", f"{f['label']} is high.")))
        if clean[key] in f.get("warn_values", []):
            warnings.append(
                Issue(key, WARNING, f.get("warn_message", f"Check {f['label'].lower()}."))
            )

    _apply_rules(step, clean, ctx, errors, warnings, skip_fields=failed)
    return EntryResult(clean=clean, errors=errors, warnings=warnings)


def summarise(
    step: Mapping[str, Any], data: Mapping[str, Any], labels: Callable[[str, str], str]
) -> str:
    """Fill the step's one-line summary template, showing list labels, not codes."""
    template = step.get("summary") or step["title"]
    lists = {f["key"]: f.get("list_key") for f in step["fields"]}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = data.get(key)
        if _empty(value):
            return "-"
        list_key = lists.get(key)
        if list_key and isinstance(value, str):
            return labels(list_key, value)
        if isinstance(value, float):
            return _fmt(round(value, 2))
        return str(value)

    return re.sub(r"\{(\w+)\}", replace, template)
