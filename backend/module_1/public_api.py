"""Public API of Module 1 (Dashboard / Home): its alert thresholds, and nothing else.

Nothing reads the dashboard's figures. It is the last module in the chain and the only
one that reads every other, so it publishes no data for anyone to call.

The one exception is configuration it owns. The alert thresholds (how many days before
a ready field without a pickup request is worth a warning, and so on) belong to the
Dashboard's rules, and Settings has to show and change them. They are plain numbers
with no table of their own, so they live in the settings registry and are written
through Module 8's values API; this file is the read side (DECISIONS D-117).
"""

from __future__ import annotations

from module_1.config_api import (
    CONFIG_KEY,
    KEYS,
    dispatch_grace_days,
    draft_fieldbook_idle_days,
    get_config,
    heap_idle_days,
    licence_expiry_warning_days,
    ready_without_pickup_days,
)

__all__ = [
    "CONFIG_KEY",
    "KEYS",
    "dispatch_grace_days",
    "draft_fieldbook_idle_days",
    "get_config",
    "heap_idle_days",
    "licence_expiry_warning_days",
    "ready_without_pickup_days",
]
