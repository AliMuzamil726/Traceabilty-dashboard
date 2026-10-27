"""Data access for Module 1 (Dashboard / Home): none.

A repository is the only place that builds SQL for a module\'s own tables, and the
dashboard has none (see ``module_1/models.py``). It reads other modules through their
``public_api`` and the shared audit log through ``shared.repositories.audit``, so no
SQL is written here.
"""

from __future__ import annotations

__all__: list[str] = []
