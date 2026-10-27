"""Data access for Module 5 (Deliveries). The only layer that builds SQL for its tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import case, func, select

from module_5.models import CANCELLED, DELIVERED, Delivery, DeliveryConfig, DeliveryStatusHistory
from shared.repositories.base import BaseRepository

#: Ids per ``IN (...)`` list, well inside SQLite's bound-parameter limit. Officer
#: scoping passes one id per farmer, which can run into thousands.
CHUNK = 500


def _chunks(items: list[str]) -> list[list[str]]:
    return [items[i : i + CHUNK] for i in range(0, len(items), CHUNK)] or [[]]


class DeliveryRepository(BaseRepository[Delivery]):
    model = Delivery

    def get_for_update(self, delivery_id: str) -> Delivery | None:
        """The row, read inside the caller's write transaction (BEGIN IMMEDIATE on SQLite)."""
        stmt = select(Delivery).where(Delivery.id == delivery_id).with_for_update()
        return self.session.execute(stmt).scalars().first()

    def filtered(
        self,
        *,
        crop: str | None = None,
        statuses: Sequence[str] | None = None,
        site_id: str | None = None,
        season_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        farmer_ids: Sequence[str] | None = None,
        heap_id: str | None = None,
        unassigned_only: bool = False,
        delivered_since: datetime | None = None,
        variance_level: str | None = None,
        limit: int | None = None,
    ) -> list[Delivery]:
        stmt = select(Delivery)
        if crop:
            stmt = stmt.where(Delivery.crop == crop)
        if statuses:
            stmt = stmt.where(Delivery.status.in_(list(statuses)))
        if site_id:
            stmt = stmt.where(Delivery.site_id == site_id)
        if season_year:
            stmt = stmt.where(Delivery.season_year == season_year)
        if date_from:
            stmt = stmt.where(Delivery.scheduled_date >= date_from)
        if date_to:
            stmt = stmt.where(Delivery.scheduled_date <= date_to)
        if farmer_ids is not None:
            stmt = stmt.where(Delivery.farmer_id.in_(list(farmer_ids) or [""]))
        if heap_id:
            stmt = stmt.where(Delivery.heap_id == heap_id)
        if unassigned_only:
            stmt = stmt.where(Delivery.heap_id.is_(None))
        if delivered_since:
            stmt = stmt.where(Delivery.delivered_at >= delivered_since)
        if variance_level:
            stmt = stmt.where(Delivery.variance_level == variance_level)
        stmt = stmt.order_by(Delivery.created_at.desc(), Delivery.delivery_no.desc())
        if limit is not None:
            stmt = stmt.limit(max(1, limit))
        return list(self.session.execute(stmt).scalars())

    # ----------------------------------------------------- aggregates (Dashboard)

    def count_by_status(
        self,
        *,
        crop: str | None = None,
        farmer_ids: Sequence[str] | None = None,
        season_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, int]:
        """Deliveries per status, one query per chunk of farmer ids."""
        out: dict[str, int] = {}
        for ids in self._id_batches(farmer_ids):
            stmt = self._narrow(
                select(Delivery.status, func.count()).group_by(Delivery.status),
                crop=crop,
                farmer_ids=ids,
                season_year=season_year,
                date_from=date_from,
                date_to=date_to,
            )
            for row in self.session.execute(stmt).all():
                out[row[0]] = out.get(row[0], 0) + int(row[1])
        return out

    def delivered_totals(
        self,
        *,
        crop: str | None = None,
        farmer_ids: Sequence[str] | None = None,
        season_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        delivered_from: datetime | None = None,
        delivered_to: datetime | None = None,
    ) -> tuple[int, float, float | None, int]:
        """``(deliveries, weighbridge_kg, average_moisture_pct, flagged)``.

        The average moisture is weighted by the number of readings, so chunking the
        farmer ids cannot change it: the sum of readings and their count are added up
        and divided once at the end.
        """
        deliveries = kg = flagged = 0
        moisture_sum = 0.0
        moisture_n = 0
        for ids in self._id_batches(farmer_ids):
            stmt = self._narrow(
                select(
                    func.count(),
                    func.coalesce(func.sum(Delivery.weighbridge_weight_kg), 0.0),
                    func.coalesce(func.sum(Delivery.moisture_pct), 0.0),
                    func.count(Delivery.moisture_pct),
                    func.coalesce(
                        func.sum(case((Delivery.variance_level == "flag", 1), else_=0)), 0
                    ),
                ).where(Delivery.status == DELIVERED),
                crop=crop,
                farmer_ids=ids,
                season_year=season_year,
                date_from=date_from,
                date_to=date_to,
            )
            if delivered_from:
                stmt = stmt.where(Delivery.delivered_at >= delivered_from)
            if delivered_to:
                stmt = stmt.where(Delivery.delivered_at <= delivered_to)
            row = self.session.execute(stmt).one()
            deliveries += int(row[0])
            kg += float(row[1])
            moisture_sum += float(row[2])
            moisture_n += int(row[3])
            flagged += int(row[4])
        moisture = None if moisture_n == 0 else round(moisture_sum / moisture_n, 2)
        return deliveries, round(kg, 1), moisture, flagged

    @staticmethod
    def _id_batches(farmer_ids: Sequence[str] | None) -> list[Sequence[str] | None]:
        """One pass with no id filter, or one pass per chunk of ids."""
        if farmer_ids is None:
            return [None]
        return list(_chunks(list(farmer_ids)))

    def delivered_rows(
        self,
        *,
        crop: str | None = None,
        farmer_ids: Sequence[str] | None = None,
        season_year: int | None = None,
        delivered_from: datetime | None = None,
        delivered_to: datetime | None = None,
    ) -> list[tuple[datetime, float, float | None]]:
        """``(delivered_at, weighbridge_kg, moisture_pct)`` for a time series.

        Bucketing by week happens in the caller: date truncation is not portable
        between SQLite and Postgres (DECISIONS D-097).
        """
        rows: list[tuple[datetime, float, float | None]] = []
        for ids in self._id_batches(farmer_ids):
            stmt = select(
                Delivery.delivered_at, Delivery.weighbridge_weight_kg, Delivery.moisture_pct
            ).where(Delivery.status == DELIVERED, Delivery.delivered_at.is_not(None))
            if crop:
                stmt = stmt.where(Delivery.crop == crop)
            if season_year:
                stmt = stmt.where(Delivery.season_year == season_year)
            if ids is not None:
                stmt = stmt.where(Delivery.farmer_id.in_(list(ids) or [""]))
            if delivered_from:
                stmt = stmt.where(Delivery.delivered_at >= delivered_from)
            if delivered_to:
                stmt = stmt.where(Delivery.delivered_at <= delivered_to)
            rows += [
                (row[0], float(row[1] or 0.0), None if row[2] is None else float(row[2]))
                for row in self.session.execute(stmt).all()
            ]
        return sorted(rows, key=lambda r: r[0])

    def count_matching(
        self,
        *,
        crop: str | None = None,
        statuses: Sequence[str] | None = None,
        farmer_ids: Sequence[str] | None = None,
        season_year: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        variance_level: str | None = None,
    ) -> int:
        """How many deliveries match, counted in SQL.

        The attention panel needs a count and a handful of examples, not every row:
        loading tens of thousands of records to call ``len`` on them is what this
        avoids (D-096).
        """
        total = 0
        for ids in self._id_batches(farmer_ids):
            stmt = self._narrow(
                select(func.count()).select_from(Delivery),
                crop=crop,
                farmer_ids=ids,
                season_year=season_year,
                date_from=date_from,
                date_to=date_to,
            )
            if statuses:
                stmt = stmt.where(Delivery.status.in_(list(statuses)))
            if variance_level:
                stmt = stmt.where(Delivery.variance_level == variance_level)
            total += int(self.session.execute(stmt).scalar_one())
        return total

    def totals_by_heap(
        self, *, crop: str | None = None
    ) -> dict[str, tuple[int, float, datetime | None]]:
        """``{heap_id: (deliveries, weighbridge_kg, last_change_at)}`` in one query.

        Only delivered loads count: those are the ones a heap's input is made of.
        """
        stmt = (
            select(
                Delivery.heap_id,
                func.count(),
                func.coalesce(func.sum(Delivery.weighbridge_weight_kg), 0.0),
                func.max(Delivery.updated_at),
            )
            .where(Delivery.heap_id.is_not(None), Delivery.status == DELIVERED)
            .group_by(Delivery.heap_id)
        )
        if crop:
            stmt = stmt.where(Delivery.crop == crop)
        return {
            str(row[0]): (int(row[1]), round(float(row[2]), 1), row[3])
            for row in self.session.execute(stmt).all()
        }

    @staticmethod
    def _narrow(
        stmt: Any,
        *,
        crop: str | None,
        farmer_ids: Sequence[str] | None,
        season_year: int | None,
        date_from: date | None,
        date_to: date | None,
    ) -> Any:
        if crop:
            stmt = stmt.where(Delivery.crop == crop)
        if season_year:
            stmt = stmt.where(Delivery.season_year == season_year)
        if farmer_ids is not None:
            stmt = stmt.where(Delivery.farmer_id.in_(list(farmer_ids) or [""]))
        if date_from:
            stmt = stmt.where(Delivery.scheduled_date >= date_from)
        if date_to:
            stmt = stmt.where(Delivery.scheduled_date <= date_to)
        return stmt

    def active_for_field(self, field_id: str) -> list[Delivery]:
        stmt = select(Delivery).where(Delivery.field_id == field_id, Delivery.status != CANCELLED)
        return list(self.session.execute(stmt).scalars())

    def open_for_request(self, request_id: str) -> list[Delivery]:
        stmt = select(Delivery).where(
            Delivery.pickup_request_id == request_id,
            Delivery.status.notin_([CANCELLED, DELIVERED]),
        )
        return list(self.session.execute(stmt).scalars())

    def for_farmer(self, farmer_id: str) -> list[Delivery]:
        stmt = select(Delivery).where(Delivery.farmer_id == farmer_id)
        return list(self.session.execute(stmt.order_by(Delivery.created_at)).scalars())


class HistoryRepository(BaseRepository[DeliveryStatusHistory]):
    model = DeliveryStatusHistory

    def for_delivery(self, delivery_id: str) -> list[DeliveryStatusHistory]:
        stmt = (
            select(DeliveryStatusHistory)
            .where(DeliveryStatusHistory.delivery_id == delivery_id)
            .order_by(DeliveryStatusHistory.at, DeliveryStatusHistory.id)
        )
        return list(self.session.execute(stmt).scalars())


class ConfigRepository(BaseRepository[DeliveryConfig]):
    model = DeliveryConfig

    def for_crop(self, crop: str) -> DeliveryConfig | None:
        stmt = select(DeliveryConfig).where(DeliveryConfig.crop == crop)
        return self.session.execute(stmt).scalars().first()
