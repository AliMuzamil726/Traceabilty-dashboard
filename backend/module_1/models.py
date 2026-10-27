"""ORM tables owned by Module 1 (Dashboard / Home): none.

The dashboard is a read-only view over the other modules. It owns no business data, so
there is nothing to store and nothing to migrate. Every figure it shows is read through
another module's ``public_api`` (see ``module_1/services/sources.py``), which is what
keeps its numbers identical to the screens those modules own.

This file stays so the module keeps the same shape as every other one, and so the
architecture test can say the dashboard adds no tables.
"""

from __future__ import annotations

__all__: list[str] = []
