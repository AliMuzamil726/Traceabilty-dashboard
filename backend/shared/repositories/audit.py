"""Reads of the shared append-only audit log.

Writes go through :mod:`core.audit`; this repository only reads, for the Dashboard's
recent-activity feed. The log is shared data, so it is read here rather than through
any module's public API.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from shared.models.audit_log import AuditLog
from shared.repositories.base import BaseRepository

#: How many rows a single read may return, whatever the caller asks for.
MAX_LIMIT = 200


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def recent(
        self,
        *,
        entities: Sequence[str] | None = None,
        officer_id: str | None = None,
        limit: int = 25,
    ) -> list[AuditLog]:
        """Newest entries first, optionally restricted to some entity names."""
        stmt = select(AuditLog)
        if entities:
            stmt = stmt.where(AuditLog.entity.in_(list(entities)))
        if officer_id:
            stmt = stmt.where(AuditLog.officer_id == officer_id)
        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(
            max(1, min(limit, MAX_LIMIT))
        )
        return list(self.session.execute(stmt).scalars().all())


__all__ = ["MAX_LIMIT", "AuditLogRepository"]
