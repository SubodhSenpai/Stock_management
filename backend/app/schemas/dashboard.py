"""Dashboard KPIs."""

from decimal import Decimal

from app.models.enums import OperationType
from app.schemas.base import ReadModel
from app.schemas.catalog import ProductBrief


class OperationCard(ReadModel):
    """The Receipt and Delivery cards on the dashboard.

    `late` counts open documents scheduled before today, `upcoming` those scheduled after,
    and `to_process` those ready to act on right now.
    """

    type: OperationType
    to_process: int
    waiting: int
    late: int
    upcoming: int
    pending: int


class LowStockItem(ReadModel):
    product: ProductBrief
    warehouse_id: int
    warehouse_name: str
    on_hand: Decimal
    min_quantity: Decimal
    suggested_order: Decimal


class DashboardSummary(ReadModel):
    products_in_stock: int
    out_of_stock: int
    low_stock: int
    cards: list[OperationCard]
