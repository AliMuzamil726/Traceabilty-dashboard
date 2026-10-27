from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActorMixin, Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from shared.models.field_office import FieldOffice

ROLE_OFFICER = "officer"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"
ROLES = (ROLE_OFFICER, ROLE_STAFF, ROLE_ADMIN)
#: Roles that work across every officer's records. Staff do everything an administrator
#: does except open Settings.
SEES_ALL_ROLES = (ROLE_STAFF, ROLE_ADMIN)


class Officer(IdMixin, TimestampMixin, ActorMixin, Base):
    """A field officer or administrator. Becomes the authenticated user once login lands."""

    __tablename__ = "officers"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16), default=ROLE_OFFICER, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    field_office_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("field_offices.id", ondelete="SET NULL"), index=True
    )
    #: PBKDF2 hash (core.passwords). Seeded accounts start on the default password.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    #: Profile photo, relative to UPLOAD_DIR. Administrators and staff only.
    photo_path: Mapped[str | None] = mapped_column(String(255))
    is_dummy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    field_office: Mapped[FieldOffice | None] = relationship(back_populates="officers")

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def sees_all(self) -> bool:
        return self.role in SEES_ALL_ROLES
