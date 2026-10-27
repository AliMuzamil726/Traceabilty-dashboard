from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin


class MasterList(IdMixin, TimestampMixin, ActorMixin, Base):
    """One option of one dropdown list.

    ``country`` and ``crop`` are optional scopes: ``NULL`` means the option applies to
    every country / crop. Uniqueness of ``(list_key, value, country, crop)`` is
    enforced in the repository because NULLs are distinct in SQL unique indexes.
    """

    __tablename__ = "master_lists"
    __table_args__ = (Index("ix_master_lists_key_scope", "list_key", "country", "crop"),)

    list_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    crop: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
