"""Dashboard KPIs and low-stock alerts."""

from decimal import Decimal

from app.models.enums import OperationType
from app.repositories.dashboard_repo import DashboardRepository
from app.schemas.catalog import ProductBrief
from app.schemas.dashboard import DashboardSummary, LowStockItem, OperationCard

ZERO = Decimal(0)


class DashboardService:
    def __init__(self, dashboard: DashboardRepository) -> None:
        self.dashboard = dashboard

    def summary(
        self, *, warehouse_id: int | None = None, category_id: int | None = None
    ) -> DashboardSummary:
        counts = self.dashboard.operation_counts(warehouse_id=warehouse_id)
        by_type = {row.type: row for row in counts}

        # Every card is always present, so the dashboard layout does not jump around.
        cards = [
            OperationCard(
                type=operation_type,
                to_process=getattr(by_type.get(operation_type), "to_process", 0),
                waiting=getattr(by_type.get(operation_type), "waiting", 0),
                late=getattr(by_type.get(operation_type), "late", 0),
                upcoming=getattr(by_type.get(operation_type), "upcoming", 0),
                pending=getattr(by_type.get(operation_type), "pending", 0),
            )
            for operation_type in OperationType
        ]

        stock = self.dashboard.product_stock_counts(
            warehouse_id=warehouse_id, category_id=category_id
        )
        return DashboardSummary(
            products_in_stock=stock.products_in_stock,
            out_of_stock=stock.out_of_stock,
            low_stock=stock.low_stock,
            cards=cards,
        )

    def low_stock(self, *, warehouse_id: int | None = None, limit: int = 50) -> list[LowStockItem]:
        return [
            LowStockItem(
                product=ProductBrief.model_validate(row[0]),
                warehouse_id=row.warehouse_id,
                warehouse_name=row.warehouse_name,
                on_hand=row.on_hand,
                min_quantity=row.min_quantity,
                suggested_order=max(ZERO, row.max_quantity - row.on_hand),
            )
            for row in self.dashboard.low_stock_items(warehouse_id=warehouse_id, limit=limit)
        ]
