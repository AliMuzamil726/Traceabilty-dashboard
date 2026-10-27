"""How many records use a piece of reference data.

Settings must answer two questions before it lets an administrator change shared data:

* *Used by how many records?* shown next to every list value, office, site, officer and
  location, so a change is never made blind;
* *Is it safe to delete?* deleting is allowed only when the count is zero (deactivating
  is always allowed and hides the value from new entries only).

A module that stores a reference registers a counter at startup, the same way it
registers event handlers, so ``core`` never imports a module and Settings never writes
a query against another module's tables. A counter is a plain function
``(session, key) -> int``; ``key`` is the stored value (a list value key, an office id,
a tehsil name). Counters are cheap ``SELECT count(*)`` statements; Settings calls them
per row on one page of results.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final

from sqlalchemy.orm import Session

logger = logging.getLogger("sawie.usage")

Counter = Callable[[Session, str], int]

#: Kinds of reference data that can be counted. A counter names the kind it answers for.
KIND_LIST_VALUE: Final = "list_value"
KIND_OFFICE: Final = "office"
KIND_SITE: Final = "site"
KIND_OFFICER: Final = "officer"
KIND_LOCATION: Final = "location"
KINDS: Final[tuple[str, ...]] = (
    KIND_LIST_VALUE,
    KIND_OFFICE,
    KIND_SITE,
    KIND_OFFICER,
    KIND_LOCATION,
)


@dataclass(frozen=True)
class Registration:
    kind: str
    #: Which module registered it, named in the Settings screen ("Used by: Fieldbook").
    module: int
    label: str
    counter: Counter


_COUNTERS: list[Registration] = []


def register_counter(kind: str, module: int, label: str, counter: Counter) -> None:
    """Add one counter. Called by each module's ``events.register_handlers``."""
    if kind not in KINDS:  # pragma: no cover - a typo, caught by tests
        raise ValueError(f"Unknown usage kind {kind!r}")
    _COUNTERS.append(Registration(kind=kind, module=module, label=label, counter=counter))


def clear_counters() -> None:
    """Forget every counter (startup and tests)."""
    _COUNTERS.clear()


def registrations(kind: str | None = None) -> Iterator[Registration]:
    for item in _COUNTERS:
        if kind is None or item.kind == kind:
            yield item


def count_usage(session: Session, kind: str, key: str) -> int:
    """Total records that refer to ``key``, across every module that registered one."""
    return sum(count for _, count in usage_breakdown(session, kind, key))


def usage_breakdown(session: Session, kind: str, key: str) -> list[tuple[str, int]]:
    """``[(label, count)]`` per registered counter, skipping the ones that find nothing."""
    out: list[tuple[str, int]] = []
    for item in registrations(kind):
        try:
            count = int(item.counter(session, key))
        except Exception:
            logger.exception("Usage counter %s (%s) failed", item.label, item.kind)
            continue
        if count:
            out.append((item.label, count))
    return out


def is_in_use(session: Session, kind: str, key: str) -> bool:
    for item in registrations(kind):
        try:
            if int(item.counter(session, key)) > 0:
                return True
        except Exception:
            logger.exception("Usage counter %s (%s) failed", item.label, item.kind)
            return True
    return False


__all__ = [
    "KINDS",
    "KIND_LIST_VALUE",
    "KIND_LOCATION",
    "KIND_OFFICE",
    "KIND_OFFICER",
    "KIND_SITE",
    "Counter",
    "Registration",
    "clear_counters",
    "count_usage",
    "is_in_use",
    "register_counter",
    "registrations",
    "usage_breakdown",
]
