"""ORM tables owned by Module 3 (Fieldbook). Documented in ``docs/DATA_MODEL.md``.

A fieldbook belongs to one field and one season year. Module 2's field is referenced
by its primary key as a plain string, not a foreign key: Module 3 only knows Module 2
through its public API, and a foreign key would couple the two schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActorMixin, Base, IdMixin, TimestampMixin, UTCDateTime, utcnow

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"

STEP_NOT_STARTED = "not_started"
STEP_IN_PROGRESS = "in_progress"
STEP_COMPLETE = "complete"
STEP_NOT_APPLICABLE = "not_applicable"

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Fieldbook(IdMixin, TimestampMixin, ActorMixin, Base):
    __tablename__ = "fieldbooks"
    __table_args__ = (
        UniqueConstraint("field_id", "season_year", name="uq_fieldbook_field_season"),
        Index("ix_fieldbooks_farmer_season", "farmer_id", "season_year"),
    )

    #: Module 2 field primary key (UUID). ``field_code`` is its business ID.
    field_id: Mapped[str] = mapped_column(String(36), nullable=False)
    field_code: Mapped[str] = mapped_column(String(32), nullable=False)
    farmer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(16), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_DRAFT, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Optimistic concurrency token, bumped by every write.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    submitted_by: Mapped[str | None] = mapped_column(String(36))
    ready_for_pickup_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    #: Set when the field itself is removed in Module 2 while this is still a draft.
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    entries: Mapped[list[FieldbookEntry]] = relationship(
        back_populates="fieldbook", cascade="all, delete-orphan"
    )
    step_statuses: Mapped[list[FieldbookStepStatus]] = relationship(
        back_populates="fieldbook", cascade="all, delete-orphan"
    )
    photos: Mapped[list[FieldbookPhoto]] = relationship(
        back_populates="fieldbook", cascade="all, delete-orphan"
    )


class FieldbookEntry(IdMixin, TimestampMixin, Base):
    __tablename__ = "fieldbook_entries"
    __table_args__ = (
        UniqueConstraint("fieldbook_id", "step_key", "entry_index", name="uq_fieldbook_entry"),
    )

    fieldbook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fieldbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36))

    fieldbook: Mapped[Fieldbook] = relationship(back_populates="entries")


class FieldbookStepStatus(Base):
    __tablename__ = "fieldbook_step_status"

    fieldbook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fieldbooks.id", ondelete="CASCADE"), primary_key=True
    )
    step_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STEP_NOT_STARTED)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(36))

    fieldbook: Mapped[Fieldbook] = relationship(back_populates="step_statuses")


class FieldbookPhoto(IdMixin, Base):
    __tablename__ = "fieldbook_photos"

    fieldbook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fieldbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Paths relative to ``UPLOAD_DIR``.
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(String(36))
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    fieldbook: Mapped[Fieldbook] = relationship(back_populates="photos")


class CropClockConfig(IdMixin, TimestampMixin, ActorMixin, Base):
    """Days after sowing at which a crop approaches, reaches and leaves harvest readiness.

    Owned here because the Fieldbook holds the sowing date; Harvest Radar (Module 4)
    reads it through ``module_3.public_api.get_crop_clock``.
    """

    __tablename__ = "crop_clock_config"

    crop: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    approach_day: Mapped[int] = mapped_column(Integer, nullable=False)
    ready_day: Mapped[int] = mapped_column(Integer, nullable=False)
    window_end_day: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Bumped on every save; Settings compares it to refuse a stale overwrite.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
