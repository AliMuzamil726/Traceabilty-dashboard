"""The stored override of a generic setting.

The table lives in ``shared`` rather than ``module_8`` because ``core.app_settings``
reads it on behalf of every module, and ``core`` may import ``shared.models`` but never
a module (DECISIONS D-116). Module 8 is its only writer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin


class AppSetting(IdMixin, TimestampMixin, ActorMixin, Base):
    """One administrator override, keyed by the registry key it belongs to.

    ``value`` is JSON so a setting can be a number, a string, a flag or a small object
    (map centres, label grids) without a column per type. ``version`` counts saves and
    is what optimistic concurrency compares.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


__all__ = ["AppSetting"]
