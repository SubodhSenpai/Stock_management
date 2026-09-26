"""Queries over the stock balance and the move ledger.

The quant repository is the only place that locks rows, and it always locks them in a
deterministic order so concurrent operations queue up instead of deadlocking.
"""

import base64
import binascii
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import Product
from app.models.enums import LocationType, OperationStatus
from app.models.operation import Operation, OperationLine
from app.models.stock import StockMove, StockQuant
from app.models.warehouse import Location

QuantKey = tuple[int, int]  # (product_id, location_id)


class QuantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_exist(self, keys: list[QuantKey]) -> None:
        """Create any missing balance rows at zero, so they can be locked and updated."""
        if not keys:
            return
        rows = [
            {"product_id": product_id, "location_id": location_id}
            for product_id, location_id in keys
        ]
        self.db.execute(
            insert(StockQuant)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[StockQuant.product_id, StockQuant.location_id])
        )

    def lock(self, keys: list[QuantKey]) -> dict[QuantKey, StockQuant]:
        """Lock the given balances for update, in sorted order to avoid deadlocks."""
        if not keys:
            return {}
        ordered = sorted(set(keys))
        self.ensure_exist(ordered)
        stmt = (
            select(StockQuant)
            .where(tuple_(StockQuant.product_id, StockQuant.location_id).in_(ordered))
            .order_by(StockQuant.product_id, StockQuant.location_id)
            .with_for_update()
        )
        return {(q.product_id, q.location_id): q for q in self.db.execute(stmt).scalars()}

    def get(self, product_id: int, location_id: int) -> StockQuant | None:
        return self.db.get(StockQuant, (product_id, location_id))

    def free_quantities(self, keys: list[QuantKey]) -> dict[QuantKey, Decimal]:
        """Free stock per (product, location), without locking. For read-only availability views."""
        if not keys:
            return {}
        stmt = select(
            StockQuant.product_id,
            StockQuant.location_id,
            StockQuant.quantity - StockQuant.reserved_quantity,
        ).where(tuple_(StockQuant.product_id, StockQuant.location_id).in_(sorted(set(keys))))
        return {(row[0], row[1]): row[2] for row in self.db.execute(stmt)}

    def list_rows(
        self,
        *,
        warehouse_id: int | None = None,
        location_id: int | None = None,
        category_id: int | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[tuple[Product, Location, StockQuant]], int]:
        """Rows for the stock page: one product at one location."""
        base = (
            select(Product, Location, StockQuant)
            .join(StockQuant, StockQuant.product_id == Product.id)
            .join(Location, Location.id == StockQuant.location_id)
            .where(Location.type == LocationType.INTERNAL, Product.is_active)
        )
        count_stmt = (
            select(func.count())
            .select_from(StockQuant)
            .join(Product, Product.id == StockQuant.product_id)
            .join(Location, Location.id == StockQuant.location_id)
            .where(Location.type == LocationType.INTERNAL, Product.is_active)
        )

        filters = []
        if warehouse_id is not None:
            filters.append(Location.warehouse_id == warehouse_id)
        if location_id is not None:
            filters.append(Location.id == location_id)
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if query:
            pattern = f"%{query}%"
            filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))

        if filters:
            base = base.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.db.execute(count_stmt).scalar_one()
        rows = self.db.execute(
            base.options(selectinload(Location.warehouse))
            .order_by(Product.name, Location.name)
            .limit(limit)
            .offset(offset)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows], total


class MoveRepository:
    """The stock ledger. Rows are only ever inserted; the database refuses anything else."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, move: StockMove) -> StockMove:
        self.db.add(move)
        self.db.flush()
        return move

    def _base_query(self) -> Select:
        return (
            select(StockMove, Operation)
            .join(Operation, Operation.id == StockMove.operation_id)
            .options(
                selectinload(StockMove.product),
                selectinload(StockMove.from_location).selectinload(Location.warehouse),
                selectinload(StockMove.to_location).selectinload(Location.warehouse),
                selectinload(Operation.partner),
            )
        )

    def history(
        self,
        *,
        product_id: int | None = None,
        location_id: int | None = None,
        warehouse_id: int | None = None,
        query: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> list[tuple[StockMove, Operation]]:
        """Newest moves first, paginated by keyset so deep pages stay fast.

        One extra row is fetched to tell the caller whether another page exists.
        """
        stmt = self._base_query()

        if product_id is not None:
            stmt = stmt.where(StockMove.product_id == product_id)
        if location_id is not None:
            stmt = stmt.where(
                or_(
                    StockMove.from_location_id == location_id,
                    StockMove.to_location_id == location_id,
                )
            )
        if warehouse_id is not None:
            stmt = stmt.where(Operation.warehouse_id == warehouse_id)
        if query:
            stmt = stmt.where(Operation.reference.ilike(f"%{query}%"))
        if date_from is not None:
            stmt = stmt.where(StockMove.moved_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(StockMove.moved_at <= date_to)

        if cursor:
            moved_at, move_id = decode_cursor(cursor)
            stmt = stmt.where(tuple_(StockMove.moved_at, StockMove.id) < (moved_at, move_id))

        stmt = stmt.order_by(StockMove.moved_at.desc(), StockMove.id.desc()).limit(limit + 1)
        return [(row[0], row[1]) for row in self.db.execute(stmt)]


class OperationLineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def waiting_operations(self, product_ids: set[int], location_ids: set[int]) -> list[Operation]:
        """Waiting documents that need these products from these locations, oldest first.

        Oldest schedule date wins, so newly arrived stock is offered to whoever has waited longest.
        """
        if not product_ids or not location_ids:
            return []
        stmt = (
            select(Operation)
            .join(OperationLine, OperationLine.operation_id == Operation.id)
            .options(
                selectinload(Operation.lines).selectinload(OperationLine.product),
                selectinload(Operation.source_location),
                selectinload(Operation.dest_location),
            )
            .where(
                Operation.status == OperationStatus.WAITING,
                Operation.source_location_id.in_(location_ids),
                OperationLine.product_id.in_(product_ids),
            )
            .order_by(Operation.schedule_date, Operation.id)
            .distinct()
        )
        return list(self.db.execute(stmt).scalars())


def encode_cursor(moved_at: datetime, move_id: int) -> str:
    """Pack the sort key of the last row into an opaque cursor."""
    raw = f"{moved_at.isoformat()}|{move_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    from app.core.exceptions import BusinessRuleError

    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        timestamp, move_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(timestamp), int(move_id)
    except (ValueError, binascii.Error) as exc:
        raise BusinessRuleError("That page cursor is not valid.") from exc
