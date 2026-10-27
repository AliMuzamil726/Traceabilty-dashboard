"""Standard paginated list contract: ``{items, total, page, page_size}``."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PageParams:
    """FastAPI dependency for list endpoints."""
    return PageParams(page=page, page_size=page_size)


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """Repository-level page (ORM rows); services convert it to :class:`Page`."""

    rows: Sequence[T]
    total: int
    params: PageParams


def paginate(session: Session, stmt: Select[Any], params: PageParams) -> PageResult[Any]:
    """Run ``stmt`` with limit/offset and a matching COUNT."""
    total = session.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = session.execute(stmt.limit(params.page_size).offset(params.offset)).scalars().all()
    return PageResult(rows=rows, total=int(total), params=params)
