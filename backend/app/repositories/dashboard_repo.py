"""Aggregate queries behind the dashboard.

Each KPI set is one round trip using FILTER, rather than a query per counter.
"""

from decimal import Decimal

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.core.clock import today
from app.models.catalog import Product, ReorderRule
from app.models.enums import OperationStatus
from app.models.operation import Operation
from app.models.stock import stock_levels
from app.models.warehouse import Warehouse

OPEN_STATUSES = (OperationStatus.DRAFT, OperationStatus.WAITING, OperationStatus.READY)
ZERO = Decimal(0)


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def operation_counts(self, *, warehouse_id: int | None = None) -> list[Row]:
        """Per document type: ready, waiting, late, upcoming and total open."""
        is_open = Operation.status.in_(OPEN_STATUSES)
        stmt = select(
            Operation.type,
            func.count().filter(Operation.status == OperationStatus.READY).label("to_process"),
            func.count().filter(Operation.status == OperationStatus.WAITING).label("waiting"),
            func.count().filter(is_open, Operation.schedule_date < today()).label("late"),
            func.count().filter(is_open, Operation.schedule_date > today()).label("upcoming"),
            func.count().filter(is_open).label("pending"),
        )
        if warehouse_id is not None:
            stmt = stmt.where(Operation.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt.group_by(Operation.type)))

    def product_stock_counts(
        self, *, warehouse_id: int | None = None, category_id: int | None = None
    ) -> Row:
        """How many products are in stock, out of stock and below their reorder level."""
        levels = select(
            stock_levels.c.product_id, func.sum(stock_levels.c.on_hand).label("on_hand")
        )
        if warehouse_id is not None:
            levels = levels.where(stock_levels.c.warehouse_id == warehouse_id)
        levels = levels.group_by(stock_levels.c.product_id).subquery()

        minimums = select(
            ReorderRule.product_id, func.sum(ReorderRule.min_quantity).label("min_quantity")
        )
        if warehouse_id is not None:
            minimums = minimums.where(ReorderRule.warehouse_id == warehouse_id)
        minimums = minimums.group_by(ReorderRule.product_id).subquery()

        on_hand = func.coalesce(levels.c.on_hand, 0)
        minimum = minimums.c.min_quantity

        stmt = (
            select(
                func.count().filter(on_hand > 0).label("products_in_stock"),
                func.count().filter(on_hand <= 0).label("out_of_stock"),
                func.count()
                .filter(on_hand > 0, minimum.isnot(None), on_hand <= minimum)
                .label("low_stock"),
            )
            .select_from(Product)
            .outerjoin(levels, levels.c.product_id == Product.id)
            .outerjoin(minimums, minimums.c.product_id == Product.id)
            .where(Product.is_active)
        )
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        return self.db.execute(stmt).one()

    def low_stock_items(self, *, warehouse_id: int | None = None, limit: int = 50) -> list[Row]:
        """Products at or below their reorder level, with how much to order to reach the maximum."""
        on_hand = func.coalesce(stock_levels.c.on_hand, 0)
        stmt = (
            select(
                Product,
                Warehouse.id.label("warehouse_id"),
                Warehouse.name.label("warehouse_name"),
                on_hand.label("on_hand"),
                ReorderRule.min_quantity,
                ReorderRule.max_quantity,
            )
            .select_from(ReorderRule)
            .join(Product, Product.id == ReorderRule.product_id)
            .join(Warehouse, Warehouse.id == ReorderRule.warehouse_id)
            .outerjoin(
                stock_levels,
                (stock_levels.c.product_id == ReorderRule.product_id)
                & (stock_levels.c.warehouse_id == ReorderRule.warehouse_id),
            )
            .where(Product.is_active, on_hand <= ReorderRule.min_quantity)
            .order_by(on_hand, Product.name)
            .limit(limit)
        )
        if warehouse_id is not None:
            stmt = stmt.where(ReorderRule.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt))
