from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActorMixin, Base, IdMixin, TimestampMixin

SITE_GINNER = "ginner"
SITE_PROCESSOR = "processor"


class Site(IdMixin, TimestampMixin, ActorMixin, Base):
    """Where harvested crop is delivered: a ginner (cotton) or a processor (hemp).

    Shared because Deliveries (5), Heap (6) and QR Tracing (7) all refer to it.
    """

    __tablename__ = "sites"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # ginner | processor
    crop: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(120))
    contact_person: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    is_dummy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
