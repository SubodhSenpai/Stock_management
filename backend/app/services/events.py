"""Change notifications broadcast to connected clients.

Events carry identifiers only. Clients refetch through the REST API, so permissions and
response shapes stay defined in exactly one place.
"""

from typing import Any

from app.models.operation import Operation
from app.models.stock import StockMove


def operation_changed(*operations: Operation) -> dict[str, Any]:
    return {
        "type": "operation.changed",
        "operations": [
            {
                "id": operation.id,
                "reference": operation.reference,
                "operation_type": operation.type.value,
                "status": operation.status.value,
            }
            for operation in operations
        ],
    }


def stock_changed(moves: list[StockMove]) -> dict[str, Any]:
    product_ids = sorted({move.product_id for move in moves})
    location_ids = sorted(
        {move.from_location_id for move in moves} | {move.to_location_id for move in moves}
    )
    return {
        "type": "stock.changed",
        "product_ids": product_ids,
        "location_ids": location_ids,
    }


def low_stock(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "stock.low", "items": items}
