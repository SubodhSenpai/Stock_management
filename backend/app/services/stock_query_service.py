"""Read-only views of stock: the stock page and the move history.

Kept apart from StockService, which is the write side. Nothing here changes anything.
"""

from datetime import datetime

from app.models.enums import LocationType
from app.models.operation import Operation
from app.models.stock import StockMove
from app.repositories.stock_repo import MoveRepository, QuantRepository, encode_cursor
from app.schemas.stock import MoveDirection, MoveOut, StockRow
from app.schemas.warehouse import LocationBrief


class StockQueryService:
    def __init__(self, quants: QuantRepository, moves: MoveRepository) -> None:
        self.quants = quants
        self.moves = moves

    def stock_rows(
        self,
        *,
        warehouse_id: int | None = None,
        location_id: int | None = None,
        category_id: int | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[StockRow], int]:
        rows, total = self.quants.list_rows(
            warehouse_id=warehouse_id,
            location_id=location_id,
            category_id=category_id,
            query=query,
            limit=limit,
            offset=offset,
        )
        return [
            StockRow(
                product=product,
                location=location,
                unit_cost=product.unit_cost,
                on_hand=quant.quantity,
                reserved=quant.reserved_quantity,
                free_to_use=quant.quantity - quant.reserved_quantity,
            )
            for product, location, quant in rows
        ], total

    def move_history(
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
    ) -> tuple[list[MoveOut], str | None]:
        """A page of the ledger, newest first, plus the cursor for the next page."""
        rows = self.moves.history(
            product_id=product_id,
            location_id=location_id,
            warehouse_id=warehouse_id,
            query=query,
            date_from=date_from,
            date_to=date_to,
            cursor=cursor,
            limit=limit,
        )

        # The repository fetches one extra row to reveal whether another page exists.
        has_more = len(rows) > limit
        page = rows[:limit]

        items = [self._to_move_out(move, operation) for move, operation in page]
        next_cursor = encode_cursor(page[-1][0].moved_at, page[-1][0].id) if has_more else None
        return items, next_cursor

    @staticmethod
    def _to_move_out(move: StockMove, operation: Operation) -> MoveOut:
        return MoveOut(
            id=move.id,
            operation_id=move.operation_id,
            reference=operation.reference,
            product=move.product,
            from_location=LocationBrief.model_validate(move.from_location),
            to_location=LocationBrief.model_validate(move.to_location),
            quantity=move.quantity,
            direction=direction_of(move),
            contact=operation.partner.name if operation.partner else None,
            moved_at=move.moved_at,
        )


def direction_of(move: StockMove) -> MoveDirection:
    """Whether this move brought stock in, sent it out, or shuffled it internally."""
    from_internal = move.from_location.type == LocationType.INTERNAL
    to_internal = move.to_location.type == LocationType.INTERNAL
    if from_internal and to_internal:
        return MoveDirection.INTERNAL
    return MoveDirection.OUT if from_internal else MoveDirection.IN
