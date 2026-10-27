"""What Module 1 listens to. It publishes nothing and registers no guards.

The dashboard holds every section for 30 seconds (``module_1.services.cache``). That is
short, but a figure that is wrong straight after a write is worse than a figure that is
a few seconds old, so the whole cache is dropped as soon as any module says its data
changed, and again once the publishing transaction commits: a read between the publish
and the commit would otherwise cache the old numbers for the full 30 seconds.

Subscribing to every event is deliberate. The dashboard reads all seven modules, so
there is no event whose data it does not show, and one list is easier to keep right
than a mapping of events to sections.
"""

from __future__ import annotations

from sqlalchemy import event as sa_event

from core import events
from core.events import Event, EventBus
from core.guards import GuardRegistry

PUBLISHES: tuple[str, ...] = ()
"""Module 1 owns no data, so it announces nothing."""

#: Every event in the product: all of them change something the dashboard counts.
SUBSCRIBES: tuple[str, ...] = tuple(sorted(events.KNOWN_EVENTS))


def on_data_changed(event: Event) -> None:
    """Drop the cached sections now, and again once the publisher commits."""
    from module_1.services import cache

    cache.invalidate()
    if event.session is not None:
        sa_event.listen(event.session, "after_commit", lambda _s: cache.invalidate(), once=True)


def register(bus: EventBus, guards: GuardRegistry) -> None:
    del guards  # the dashboard never blocks another module's action
    for name in SUBSCRIBES:
        bus.subscribe(name, on_data_changed)
