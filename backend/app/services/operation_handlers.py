"""What differs between receipts, deliveries, transfers and adjustments.

Everything the four types share lives in OperationService. Each subclass below only
declares the parts that genuinely differ: which locations are valid, whether stock must be
reserved, and what validating actually does.
"""

from abc import ABC, abstractmethod

from app.core.exceptions import BusinessRuleError
from app.models.enums import LocationType, OperationStatus, OperationType, PartnerType
from app.models.operation import Operation
from app.models.stock import StockMove
from app.models.user import User
from app.models.warehouse import Location
from app.services.stock_service import Shortage, StockService


class OperationHandler(ABC):
    """Base behaviour: confirm makes a document ready, validate moves the stock."""

    source_types: frozenset[LocationType]
    dest_types: frozenset[LocationType]
    reserves_stock: bool = False
    required_partner: PartnerType | None = None

    def __init__(self, stock: StockService) -> None:
        self.stock = stock

    @property
    @abstractmethod
    def operation_type(self) -> OperationType: ...

    def check_locations(self, source: Location, destination: Location) -> None:
        if source.type not in self.source_types:
            raise BusinessRuleError(
                f"A {self.operation_type.value} cannot start from {source.code}.",
                code="INVALID_LOCATION",
            )
        if destination.type not in self.dest_types:
            raise BusinessRuleError(
                f"A {self.operation_type.value} cannot end at {destination.code}.",
                code="INVALID_LOCATION",
            )

    def on_confirm(self, operation: Operation) -> tuple[OperationStatus, list[Shortage]]:
        """Decide the state after confirming, reserving stock first if this type needs it."""
        if not self.reserves_stock:
            return OperationStatus.READY, []
        shortages = self.stock.try_reserve(operation)
        if shortages:
            return OperationStatus.WAITING, shortages
        return OperationStatus.READY, []

    def on_cancel(self, operation: Operation) -> None:
        """Ready documents hold a reservation, so cancelling has to give it back."""
        if self.reserves_stock and operation.status == OperationStatus.READY:
            self.stock.release(operation)

    def on_validate(self, operation: Operation, user: User) -> list[StockMove]:
        return self.stock.execute(operation, user, from_reserved=self.reserves_stock)


class ReceiptHandler(OperationHandler):
    """Goods arriving from a vendor."""

    operation_type = OperationType.RECEIPT
    source_types = frozenset({LocationType.VENDOR})
    dest_types = frozenset({LocationType.INTERNAL})
    required_partner = PartnerType.VENDOR


class DeliveryHandler(OperationHandler):
    """Goods leaving for a customer. Stock is reserved on confirmation."""

    operation_type = OperationType.DELIVERY
    source_types = frozenset({LocationType.INTERNAL})
    dest_types = frozenset({LocationType.CUSTOMER})
    reserves_stock = True
    required_partner = PartnerType.CUSTOMER


class InternalHandler(OperationHandler):
    """Stock moving between two locations inside the company."""

    operation_type = OperationType.INTERNAL
    source_types = frozenset({LocationType.INTERNAL})
    dest_types = frozenset({LocationType.INTERNAL})
    reserves_stock = True


class AdjustmentHandler(OperationHandler):
    """A physical count. Validating writes the difference, not the counted amount."""

    operation_type = OperationType.ADJUSTMENT
    source_types = frozenset({LocationType.INTERNAL})
    dest_types = frozenset({LocationType.ADJUSTMENT})

    def on_validate(self, operation: Operation, user: User) -> list[StockMove]:
        return self.stock.apply_count(operation, user)


def build_handlers(stock: StockService) -> dict[OperationType, OperationHandler]:
    return {
        handler.operation_type: handler
        for handler in (
            ReceiptHandler(stock),
            DeliveryHandler(stock),
            InternalHandler(stock),
            AdjustmentHandler(stock),
        )
    }
