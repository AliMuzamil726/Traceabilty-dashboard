"""Fixtures for the cross-module audit tests.

The full-chain helpers (register, map, fieldbook, pickup, delivery, heap, bales) are the
Dashboard's, which already drive every module through its HTTP API. They are reused
here rather than copied a fourth time.
"""

from module_1.tests.conftest import (  # noqa: F401 - pytest finds fixtures by name
    as_officer,
    dashboard,
    deliver,
    heap_with_bales,
    make_farm,
    officer_ids,
    request_pickup,
    schedule,
    sites,
)
