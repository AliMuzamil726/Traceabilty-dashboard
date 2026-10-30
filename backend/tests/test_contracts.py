"""docs/CONTRACTS.md against the code.

The contracts document is what other modules (and the next developer) build against,
so it must not drift from reality. This test reads the document itself and compares:

* the events table with ``core.events.KNOWN_EVENTS`` and each module's ``PUBLISHES``;
* every payload a module publishes with the keys the table promises;
* each module's declared public API functions with its ``public_api.__all__``;
* each module's endpoint table with the routes its router actually serves.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from core import events as event_names
from core.events import KNOWN_EVENTS

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "CONTRACTS.md"
TEXT = CONTRACTS.read_text(encoding="utf-8")
BACKEND = Path(__file__).resolve().parents[1]
BUILT = [1, 2, 3, 4, 5, 6, 7, 8, 9]


def _section(start: str, *, stop: str = r"\n#{2,3} ") -> str:
    """The text from a heading line up to the next heading of level 2 or 3."""
    found = re.search(re.escape(start) + r".*?(?=" + stop + r"|\Z)", TEXT, re.S)
    assert found, f"CONTRACTS.md has no section starting with {start!r}"
    return found.group(0)


# ----------------------------------------------------------------------- events


def _event_table() -> dict[str, int]:
    events = _section("## 2. Events", stop=r"\n## ")
    rows = re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \| (\d) \|", events, re.M)
    return {name: int(number) for name, number in rows}


def test_the_events_table_lists_exactly_the_known_events() -> None:
    assert set(_event_table()) == set(KNOWN_EVENTS)


@pytest.mark.parametrize("number", BUILT)
def test_each_module_publishes_what_the_table_says(number: int) -> None:
    declared = {name for name, owner in _event_table().items() if owner == number}
    published = set(importlib.import_module(f"module_{number}.events").PUBLISHES)
    assert published == declared


# ---------------------------------------------------------------------- payloads

#: Events whose payload is written as "the same" plus a few keys, so their documented
#: keys are the base event's keys union the extra braces.
_BASED_ON = {
    "pickup.cancelled": "pickup.requested",
    "delivery.dispatched": "delivery.scheduled",
    "delivery.delivered": "delivery.scheduled",
    "delivery.cancelled": "delivery.scheduled",
    "delivery.corrected": "delivery.scheduled",
    "gate.entry_accepted": "gate.entry_created",
    "gate.entry_rejected": "gate.entry_created",
}


def _documented_payloads() -> dict[str, set[str]]:
    """The payload keys the table promises for each event."""
    events = _section("## 2. Events", stop=r"\n## ")
    cells = dict(
        re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \| \d+ \| (.*?) \|$", events, re.M)
    )
    resolved: dict[str, set[str]] = {}
    for name, cell in cells.items():
        keys: set[str] = set()
        for block in re.findall(r"\{([^}]*)\}", cell):
            for part in block.split(","):
                token = part.strip().strip("`").split(":")[0].strip()
                if re.fullmatch(r"[a-z_]+", token):
                    keys.add(token)
        base = _BASED_ON.get(name)
        if base:
            keys |= resolved.get(base, set())
        resolved[name] = keys
    return resolved


def _literal_keys(node: ast.Dict) -> set[str] | None:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        else:
            return None
    return keys


def _helper_keys(tree: ast.Module, node: ast.expr) -> set[str] | None:
    """Keys of the dict a local helper such as ``self._payload(entry)`` returns."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if not name:
        return None
    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if candidate.name != name:
            continue
        for body in ast.walk(candidate):
            if isinstance(body, ast.Return) and isinstance(body.value, ast.Dict):
                return _literal_keys(body.value)
            if (
                isinstance(body, ast.Assign)
                and isinstance(body.value, ast.Dict)
                and any(
                    isinstance(target, ast.Name) and target.id in {"payload", "data", "body"}
                    for target in body.targets
                )
            ):
                return _literal_keys(body.value)
    return None


def _payload_keys(node: ast.expr, tree: ast.Module) -> set[str] | None:
    if isinstance(node, ast.Dict):
        keys: set[str] = set()
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                unpacked = _helper_keys(tree, value)
                if unpacked is None:
                    return None
                keys |= unpacked
            elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
            else:
                return None
        return keys
    return _helper_keys(tree, node)


def _published_names(node: ast.expr, constants: dict[str, str]) -> list[str]:
    if isinstance(node, ast.IfExp):
        return _published_names(node.body, constants) + _published_names(node.orelse, constants)
    if isinstance(node, ast.Name):
        return [constants.get(node.id, node.id)]
    if isinstance(node, ast.Attribute):
        return [constants.get(node.attr, node.attr)]
    return [ast.unparse(node)]


def _published_payloads() -> list[tuple[int, str, int, str, set[str] | None]]:
    """Every ``bus.publish(...)`` in module code, with its event and payload keys."""
    constants = {
        name: value
        for name, value in vars(event_names).items()
        if name.isupper() and isinstance(value, str)
    }
    found: list[tuple[int, str, int, str, set[str] | None]] = []
    for path in sorted(BACKEND.glob("module_*/**/*.py")):
        relative = path.relative_to(BACKEND)
        if "tests" in relative.parts:
            continue
        match = re.fullmatch(r"module_(\d+)", relative.parts[0])
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "publish"
                and len(node.args) >= 2
            ):
                continue
            number = int(match.group(1)) if match else 0
            keys = _payload_keys(node.args[1], tree)
            for name in _published_names(node.args[0], constants):
                found.append((number, str(relative), node.lineno, name, keys))
    return found


@pytest.mark.parametrize("number", BUILT)
def test_every_published_payload_has_the_documented_keys(number: int) -> None:
    """A payload that drops a promised key is a silent cross-module break."""
    documented = _documented_payloads()
    publishes = [row for row in _published_payloads() if row[0] == number]
    problems: list[str] = []
    for _, where, line, name, keys in publishes:
        if name not in documented:
            problems.append(f"{where}:{line} publishes {name}, which the table does not list")
            continue
        if keys is None:
            problems.append(f"{where}:{line} {name} payload cannot be read as a dict literal")
            continue
        missing = documented[name] - keys
        if missing:
            problems.append(f"{where}:{line} {name} is missing {sorted(missing)}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ public APIs


def _declared_functions(number: int) -> set[str]:
    """Every ``def name(`` the document gives for one module."""
    names: set[str] = set()
    heading = re.search(rf"^### Module {number} [^\n]*\n", TEXT, re.M | re.S)
    # The module's own public API block, in section 4.
    public = _section("## 4. Public APIs", stop=r"\n## ")
    own_pattern = rf"^### Module {number} [^\n]*\(built\)\n(.*?)(?=^### |\Z)"
    own = re.search(own_pattern, public, re.M | re.S)
    if own:
        for block in re.findall(r"```python\n(.*?)```", own.group(1), re.S):
            names |= set(re.findall(r"^def ([a-z_0-9]+)\(", block, re.M))
    # Functions added later for another module, grouped under '# Module N' inside a
    # '### Functions added for Module X' block. There is one per consumer (Modules 1
    # and 8 so far), so every block is scanned.
    for added in re.findall(
        r"### Functions added for Module \d+.*?```python\n(.*?)```", TEXT, re.S
    ):
        group = rf"# Module {number}\b[^\n]*\n(.*?)(?=\n# Module |\Z)"
        block = re.search(group, added, re.S)
        if block:
            names |= set(re.findall(r"^def ([a-z_0-9]+)\(", block.group(1), re.M))
    assert heading is not None
    return names


def _exported_functions(number: int) -> set[str]:
    module = importlib.import_module(f"module_{number}.public_api")
    return {
        name
        for name in getattr(module, "__all__", [])
        if callable(getattr(module, name)) and name[0].islower()
    }


@pytest.mark.parametrize("number", [2, 3, 4, 5, 6, 7, 8, 9])
def test_public_api_matches_the_contract(number: int) -> None:
    declared = _declared_functions(number)
    exported = _exported_functions(number)
    assert exported - declared == set(), f"exported but not documented: {exported - declared}"
    assert declared - exported == set(), f"documented but not exported: {declared - exported}"


def test_the_dashboard_exposes_only_its_own_configuration() -> None:
    """Nothing reads the dashboard's figures; Settings reads the thresholds it owns."""
    assert _exported_functions(1) == _declared_functions(1)
    assert "get_config" in _exported_functions(1)


# --------------------------------------------------------------------- endpoints


def _normalise(path: str) -> str:
    """Drop the query string and name every path parameter ``{}``."""
    path = path.split("?")[0].rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}", "{}", path)


def _declared_routes(number: int) -> set[tuple[str, str]]:
    table = _section(f"### Module {number} endpoints")
    rows = re.findall(r"^\| `(GET|POST|PUT|PATCH|DELETE) ([^`]+)` \|", table, re.M)
    out: set[tuple[str, str]] = set()
    for method, paths in rows:
        # A row may name two paths: 'GET /trace/bale/{serial}`, `GET /trace/heap/{id}'.
        out.add((method, _normalise(paths)))
    for method, path in re.findall(r"`(GET|POST|PUT|PATCH|DELETE) ([^`]+)`", table):
        out.add((method, _normalise(path)))
    return out


def _served_routes(number: int) -> set[tuple[str, str]]:
    router = importlib.import_module(f"module_{number}.router").router
    meta = importlib.import_module(f"module_{number}.meta")
    out: set[tuple[str, str]] = set()
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = _normalise(route.path.removeprefix(meta.API_PREFIX) or "/")
        if path == "/meta":
            continue  # every module has one; documented once in the conventions table
        for method in route.methods - {"HEAD", "OPTIONS"}:
            out.add((method, path))
    return out


@pytest.mark.parametrize("number", BUILT)
def test_every_served_route_is_documented(number: int) -> None:
    missing = _served_routes(number) - _declared_routes(number)
    assert not missing, f"module_{number} serves routes CONTRACTS.md does not list: {missing}"


@pytest.mark.parametrize("number", BUILT)
def test_every_documented_route_is_served(number: int) -> None:
    stale = _declared_routes(number) - _served_routes(number)
    assert not stale, f"CONTRACTS.md lists routes module_{number} does not serve: {stale}"


@pytest.mark.parametrize("number", BUILT)
def test_the_parser_finds_routes_on_both_sides(number: int) -> None:
    """Guard against the comparisons above passing because both sides came back empty."""
    assert _served_routes(number)
    assert _declared_routes(number)
