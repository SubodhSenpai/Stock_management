"""Creating, editing and moving inventory documents through their lifecycle.

This service owns the transaction. It decides *when* things happen; the per-type handlers
decide *what* happens, and StockService is the only thing that touches stock.

Events are published after the commit, never before, so a client never refetches a change
that is about to be rolled back.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import today, utcnow
from app.core.events import EventBus
from app.core.exceptions import BusinessRuleError, InsufficientStockError, NotFoundError
from app.models.enums import LocationType, OperationStatus, OperationType
from app.models.operation import Operation, OperationLine
from app.models.user import User
from app.models.warehouse import Location
from app.repositories.catalog_repo import ProductRepository
from app.repositories.operation_repo import OperationRepository
from app.repositories.partner_repo import PartnerRepository
from app.repositories.stock_repo import OperationLineRepository
from app.repositories.warehouse_repo import LocationRepository, WarehouseRepository
from app.schemas.operation import OperationCreate, OperationLineIn, OperationUpdate
from app.services import events
from app.services.operation_handlers import OperationHandler, build_handlers
from app.services.state_machine import Action, assert_allowed, assert_editable
from app.services.stock_service import Shortage, StockService

logger = logging.getLogger(__name__)


class OperationService:
    def __init__(
        self,
        db: Session,
        operations: OperationRepository,
        lines: OperationLineRepository,
        locations: LocationRepository,
        warehouses: WarehouseRepository,
        products: ProductRepository,
        partners: PartnerRepository,
        stock: StockService,
        event_bus: EventBus,
    ) -> None:
        self.db = db
        self.operations = operations
        self.lines = lines
        self.locations = locations
        self.warehouses = warehouses
        self.products = products
        self.partners = partners
        self.stock = stock
        self.event_bus = event_bus
        self.handlers = build_handlers(stock)

    # ---------- creating and editing ----------

    def create(self, data: OperationCreate, user: User) -> Operation:
        handler = self.handlers[data.type]
        source, destination = self._resolve_locations(data, handler)

        # Check the location types first: "a delivery cannot start from Vendors" is a far
        # more useful message than a complaint about the missing warehouse it implies.
        handler.check_locations(source, destination)
        self._check_partner(data.partner_id, handler)

        warehouse = self.warehouses.get(self._warehouse_for(source, destination))
        if warehouse is None:
            raise NotFoundError("That warehouse no longer exists.")

        operation = Operation(
            reference=self.operations.next_reference(warehouse, data.type),
            type=data.type,
            status=OperationStatus.DRAFT,
            warehouse_id=warehouse.id,
            source_location_id=source.id,
            dest_location_id=destination.id,
            partner_id=data.partner_id,
            delivery_address=data.delivery_address,
            schedule_date=data.schedule_date or today(),
            responsible_id=data.responsible_id or user.id,
            notes=data.notes,
            created_by=user.id,
        )
        self.operations.add(operation)
        self._replace_lines(operation, data.lines, data.type)

        self.db.commit()
        self.event_bus.publish(events.operation_changed(operation))
        logger.info("Created %s", operation.reference)
        return self._reload(operation.id)

    def update(self, operation_id: int, data: OperationUpdate, user: User) -> Operation:
        operation = self._get_locked(operation_id)
        assert_editable(operation)
        handler = self.handlers[operation.type]

        if data.source_location_id or data.dest_location_id:
            source = self._require_location(data.source_location_id or operation.source_location_id)
            destination = self._require_location(
                data.dest_location_id or operation.dest_location_id
            )
            if source.id == destination.id:
                raise BusinessRuleError(
                    "Source and destination must be different locations.", code="INVALID_LOCATION"
                )
            handler.check_locations(source, destination)
            operation.source_location_id = source.id
            operation.dest_location_id = destination.id
            operation.warehouse_id = self._warehouse_for(source, destination)

        if data.partner_id is not None:
            self._check_partner(data.partner_id, handler)
            operation.partner_id = data.partner_id
        for field in ("delivery_address", "schedule_date", "responsible_id", "notes"):
            value = getattr(data, field)
            if value is not None:
                setattr(operation, field, value)

        if data.lines is not None:
            self._replace_lines(operation, data.lines, operation.type)

        self.db.commit()
        self.event_bus.publish(events.operation_changed(operation))
        return self._reload(operation.id)

    # ---------- lifecycle ----------

    def confirm(self, operation_id: int, user: User) -> Operation:
        """Mark a document as to-do. Outgoing documents reserve stock here."""
        operation = self._get_locked(operation_id)
        assert_allowed(operation, Action.CONFIRM)

        status, shortages = self.handlers[operation.type].on_confirm(operation)
        operation.status = status
        self.db.commit()

        self.event_bus.publish(events.operation_changed(operation))
        if shortages:
            logger.info("%s is waiting on %d line(s)", operation.reference, len(shortages))
        return self._reload(operation.id)

    def check_availability(self, operation_id: int, user: User) -> Operation:
        """Retry the reservation for a waiting document."""
        operation = self._get_locked(operation_id)
        assert_allowed(operation, Action.CHECK_AVAILABILITY)

        shortages = self.stock.try_reserve(operation)
        if not shortages:
            operation.status = OperationStatus.READY
        self.db.commit()

        self.event_bus.publish(events.operation_changed(operation))
        if shortages:
            raise InsufficientStockError(
                f"{operation.reference} still cannot be filled from "
                f"{operation.source_location.code}.",
                [shortage.as_detail() for shortage in shortages],
            )
        return self._reload(operation.id)

    def validate(self, operation_id: int, user: User) -> Operation:
        """Execute the document: move the stock, write the ledger, release anything waiting."""
        operation = self._get_locked(operation_id)
        assert_allowed(operation, Action.VALIDATE)

        moves = self.handlers[operation.type].on_validate(operation, user)
        operation.status = OperationStatus.DONE
        operation.validated_at = utcnow()
        operation.validated_by = user.id

        promoted = self._promote_waiting(moves)
        self.db.commit()

        self.event_bus.publish(events.operation_changed(operation, *promoted))
        if moves:
            self.event_bus.publish(events.stock_changed(moves))
        logger.info("Validated %s", operation.reference)
        return self._reload(operation.id)

    def cancel(self, operation_id: int, user: User) -> Operation:
        operation = self._get_locked(operation_id)
        assert_allowed(operation, Action.CANCEL)

        self.handlers[operation.type].on_cancel(operation)
        operation.status = OperationStatus.CANCELED
        self.db.commit()

        self.event_bus.publish(events.operation_changed(operation))
        return self._reload(operation.id)

    # ---------- reading ----------

    def get(self, operation_id: int) -> Operation:
        operation = self.operations.get(operation_id)
        if operation is None:
            raise NotFoundError("That operation does not exist.")
        return operation

    def availability_for(self, operation: Operation) -> dict[int, Decimal]:
        return self.stock.availability(operation)

    # ---------- internals ----------

    def _promote_waiting(self, moves: list) -> list[Operation]:
        """After stock arrives, let waiting documents that can now be filled become ready.

        Oldest schedule date first, so the longest-waiting order is served before a newer one.
        """
        incoming = [move for move in moves if move.to_location.type == LocationType.INTERNAL]
        if not incoming:
            return []

        product_ids = {move.product_id for move in incoming}
        location_ids = {move.to_location_id for move in incoming}

        promoted = []
        for waiting in self.lines.waiting_operations(product_ids, location_ids):
            if not self.stock.try_reserve(waiting):
                waiting.status = OperationStatus.READY
                promoted.append(waiting)
                logger.info("%s is now ready", waiting.reference)
        return promoted

    def _replace_lines(
        self, operation: Operation, lines: list[OperationLineIn], operation_type: OperationType
    ) -> None:
        products = self.products.get_many([line.product_id for line in lines])
        is_adjustment = operation_type == OperationType.ADJUSTMENT

        operation.lines.clear()
        self.db.flush()

        for line in lines:
            product = products.get(line.product_id)
            if product is None:
                raise NotFoundError(f"Product {line.product_id} does not exist.")
            if not product.is_active:
                raise BusinessRuleError(
                    f"[{product.sku}] {product.name} is archived and cannot be used.",
                    code="PRODUCT_INACTIVE",
                )

            quantity = line.counted_quantity if is_adjustment else line.quantity
            if quantity is None:
                expected = "counted_quantity" if is_adjustment else "quantity"
                raise BusinessRuleError(
                    f"A {operation_type.value} line needs {expected}.", code="INVALID_QUANTITY"
                )
            self._check_whole_units(product, quantity)

            operation.lines.append(
                OperationLine(
                    product_id=product.id,
                    quantity=None if is_adjustment else quantity,
                    counted_quantity=quantity if is_adjustment else None,
                )
            )
        self.db.flush()

    @staticmethod
    def _check_whole_units(product, quantity: Decimal) -> None:
        if not product.uom.allow_fraction and quantity % 1 != 0:
            raise BusinessRuleError(
                f"[{product.sku}] {product.name} is measured in {product.uom.name}, "
                f"so {quantity} is not a valid amount.",
                code="INVALID_QUANTITY",
            )

    def _resolve_locations(
        self, data: OperationCreate, handler: OperationHandler
    ) -> tuple[Location, Location]:
        """Fill in whichever side the caller left out, using the virtual location for the type."""
        source = (
            self._require_location(data.source_location_id)
            if data.source_location_id
            else self._default_virtual(handler.source_types)
        )
        destination = (
            self._require_location(data.dest_location_id)
            if data.dest_location_id
            else self._default_virtual(handler.dest_types)
        )
        if source.id == destination.id:
            raise BusinessRuleError(
                "Source and destination must be different locations.", code="INVALID_LOCATION"
            )
        return source, destination

    def _default_virtual(self, allowed: frozenset[LocationType]) -> Location:
        virtual = [kind for kind in allowed if kind != LocationType.INTERNAL]
        if not virtual:
            raise BusinessRuleError(
                "This operation needs both a source and a destination location.",
                code="INVALID_LOCATION",
            )
        return self.locations.get_or_create_virtual(virtual[0])

    def _require_location(self, location_id: int) -> Location:
        location = self.locations.get(location_id)
        if location is None:
            raise NotFoundError(f"Location {location_id} does not exist.")
        if not location.is_active:
            raise BusinessRuleError(
                f"{location.code} is archived and cannot be used.", code="INVALID_LOCATION"
            )
        return location

    @staticmethod
    def _warehouse_for(source: Location, destination: Location) -> int:
        """The document belongs to whichever internal side it touches."""
        warehouse_id = source.warehouse_id or destination.warehouse_id
        if warehouse_id is None:
            raise BusinessRuleError(
                "At least one side of the operation must be a warehouse location.",
                code="INVALID_LOCATION",
            )
        return warehouse_id

    def _check_partner(self, partner_id: int | None, handler: OperationHandler) -> None:
        if handler.required_partner is None:
            return
        if partner_id is None:
            raise BusinessRuleError(
                f"A {handler.operation_type.value} needs a contact.", code="VALIDATION_ERROR"
            )
        partner = self.partners.get(partner_id)
        if partner is None:
            raise NotFoundError("That contact does not exist.")
        if not self.partners.can_act_as(partner, handler.required_partner):
            raise BusinessRuleError(
                f"{partner.name} is not a {handler.required_partner.value}.",
                code="VALIDATION_ERROR",
            )

    def _get_locked(self, operation_id: int) -> Operation:
        operation = self.operations.get_for_update(operation_id)
        if operation is None:
            raise NotFoundError("That operation does not exist.")
        return operation

    def _reload(self, operation_id: int) -> Operation:
        return self.operations.get(operation_id)


__all__ = ["OperationService", "Shortage"]
