"""docs/CONTRACTS.md against the code.

The contracts document is what other modules (and the next developer) build against,
so it must not drift from reality. This test reads the document itself and compares:

* the events table with ``core.events.KNOWN_EVENTS`` and each module's ``PUBLISHES``;
* each module's declared public API functions with its ``public_api.__all__``;
* each module's endpoint table with the routes its router actually serves.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from core.events import KNOWN_EVENTS

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "CONTRACTS.md"
TEXT = CONTRACTS.read_text(encoding="utf-8")
BUILT = [1, 2, 3, 4, 5, 6, 7]


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


@pytest.mark.parametrize("number", [2, 3, 4, 5, 6, 7, 8])
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
