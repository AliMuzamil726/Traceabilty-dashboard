from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, UTCDateTime, utcnow


class IdCounter(Base):
    """Named monotonically increasing counter (see ``core.ids``)."""

    __tablename__ = "id_counters"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
