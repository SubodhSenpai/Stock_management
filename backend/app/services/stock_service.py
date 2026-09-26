"""The only code that changes stock.

Every change goes through here, which is what makes the ledger complete: no other module
may write to `stock_quants` or `stock_moves`.

Two rules keep concurrent users correct:
  * balances are locked with SELECT ... FOR UPDATE before being read or changed, so a
    second request waits rather than acting on a stale number;
  * they are always locked in sorted order, so two requests touching the same products
    queue up instead of deadlocking.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, InsufficientStockError
from app.models.enums import LocationType
from app.models.operation import Operation, OperationLine
from app.models.stock import StockMove
from app.models.user import User
from app.repositories.stock_repo import MoveRepository, QuantKey, QuantRepository
from app.repositories.warehouse_repo import LocationRepository

logger = logging.getLogger(__name__)
ZERO = Decimal(0)


@dataclass(frozen=True)
class Shortage:
    """A line that cannot be met from free stock."""

    line: OperationLine
    requested: Decimal
    available: Decimal

    def as_detail(self) -> dict[str, str]:
        label = f"[{self.line.product.sku}] {self.line.product.name}"
        return {
            "field": f"lines.{self.line.product_id}",
            "message": f"{label}: asked {self.requested}, free {self.available}",
        }


class StockService:
    def __init__(
        self,
        db: Session,
        quants: QuantRepository,
        moves: MoveRepository,
        locations: LocationRepository,
    ) -> None:
        self.db = db
        self.quants = quants
        self.moves = moves
        self.locations = locations

    def try_reserve(self, operation: Operation) -> list[Shortage]:
        """Set stock aside for an outgoing document.

        All or nothing: if any line is short, nothing is reserved and the shortages are
        returned so the document can go to Waiting and the UI can mark those lines.
        """
        source_id = operation.source_location_id
        keys = [(line.product_id, source_id) for line in operation.lines]
        quants = self.quants.lock(keys)

        shortages = []
        for line in operation.lines:
            quant = quants[(line.product_id, source_id)]
            free = quant.quantity - quant.reserved_quantity
            if free < line.quantity:
                shortages.append(Shortage(line=line, requested=line.quantity, available=free))

        if shortages:
            return shortages

        for line in operation.lines:
            quants[(line.product_id, source_id)].reserved_quantity += line.quantity
        return []

    def release(self, operation: Operation) -> None:
        """Give reserved stock back, when a confirmed document is cancelled."""
        source_id = operation.source_location_id
        quants = self.quants.lock([(line.product_id, source_id) for line in operation.lines])
        for line in operation.lines:
            quant = quants[(line.product_id, source_id)]
            quant.reserved_quantity = max(ZERO, quant.reserved_quantity - line.quantity)

    def execute(self, operation: Operation, user: User, *, from_reserved: bool) -> list[StockMove]:
        """Move the stock and write the ledger rows. This is what Validate does."""
        source = operation.source_location
        destination = operation.dest_location
        keys = self._affected_keys(
            operation, source.id, destination.id, source.type, destination.type
        )
        quants = self.quants.lock(keys)

        moves = []
        for line in operation.lines:
            quantity = line.quantity
            if source.type == LocationType.INTERNAL:
                quant = quants[(line.product_id, source.id)]
                if quant.quantity < quantity:
                    raise InsufficientStockError(
                        f"Not enough stock at {source.code} to validate {operation.reference}.",
                        [Shortage(line, quantity, quant.quantity).as_detail()],
                    )
                quant.quantity -= quantity
                if from_reserved:
                    quant.reserved_quantity = max(ZERO, quant.reserved_quantity - quantity)

            if destination.type == LocationType.INTERNAL:
                quants[(line.product_id, destination.id)].quantity += quantity

            moves.append(
                self.moves.add(
                    StockMove(
                        operation_id=operation.id,
                        operation_line_id=line.id,
                        product_id=line.product_id,
                        from_location_id=source.id,
                        to_location_id=destination.id,
                        quantity=quantity,
                        unit_cost=line.product.unit_cost,
                        moved_by=user.id,
                    )
                )
            )

        logger.info("Executed %s: %d move(s)", operation.reference, len(moves))
        return moves

    def apply_count(self, operation: Operation, user: User) -> list[StockMove]:
        """Apply a stock count: move only the difference between counted and on hand.

        A line that matches the system quantity produces no move, because nothing changed.
        """
        location = operation.source_location
        adjustment = self.locations.get_or_create_virtual(LocationType.ADJUSTMENT)
        quants = self.quants.lock([(line.product_id, location.id) for line in operation.lines])

        moves = []
        for line in operation.lines:
            quant = quants[(line.product_id, location.id)]
            line.system_quantity = quant.quantity
            difference = line.counted_quantity - quant.quantity
            if difference == ZERO:
                continue

            if difference < ZERO and quant.reserved_quantity > line.counted_quantity:
                raise BusinessRuleError(
                    f"[{line.product.sku}] {line.product.name}: {quant.reserved_quantity} is "
                    f"reserved for pending orders, so the count cannot be set to "
                    f"{line.counted_quantity}.",
                    code="BELOW_RESERVED",
                )

            quant.quantity = line.counted_quantity
            increase = difference > ZERO
            moves.append(
                self.moves.add(
                    StockMove(
                        operation_id=operation.id,
                        operation_line_id=line.id,
                        product_id=line.product_id,
                        from_location_id=adjustment.id if increase else location.id,
                        to_location_id=location.id if increase else adjustment.id,
                        quantity=abs(difference),
                        unit_cost=line.product.unit_cost,
                        moved_by=user.id,
                    )
                )
            )

        logger.info("Applied count %s: %d adjustment(s)", operation.reference, len(moves))
        return moves

    def availability(self, operation: Operation) -> dict[int, Decimal]:
        """Free stock per product at the source, for showing which lines can be met."""
        if operation.source_location.type != LocationType.INTERNAL:
            return {}
        source_id = operation.source_location_id
        free = self.quants.free_quantities(
            [(line.product_id, source_id) for line in operation.lines]
        )
        return {product_id: quantity for (product_id, _), quantity in free.items()}

    @staticmethod
    def _affected_keys(
        operation: Operation,
        source_id: int,
        destination_id: int,
        source_type: LocationType,
        destination_type: LocationType,
    ) -> list[QuantKey]:
        """Only internal locations hold stock, so only those need locking."""
        keys: list[QuantKey] = []
        for line in operation.lines:
            if source_type == LocationType.INTERNAL:
                keys.append((line.product_id, source_id))
            if destination_type == LocationType.INTERNAL:
                keys.append((line.product_id, destination_id))
        return keys
