"""Generic repository base class reused by shared and module repositories."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: str) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list_all(self) -> Sequence[ModelT]:
        return self.session.execute(select(self.model)).scalars().all()

    def count(self) -> int:
        return int(self.session.execute(select(func.count()).select_from(self.model)).scalar_one())

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def find_one_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return self.session.execute(stmt).scalars().first()
