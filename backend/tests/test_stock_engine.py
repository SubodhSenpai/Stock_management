"""The inventory engine: reservations, the ledger, and moving documents through their states.

These are the rules the whole product rests on, so they are tested against a real database
rather than mocks.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
    InvalidTransitionError,
)
from app.models.enums import LocationType, OperationStatus, OperationType
from app.models.stock import StockMove, StockQuant
from app.schemas.operation import OperationCreate, OperationLineIn, OperationUpdate
from app.services.operation_service import OperationService
from tests import factories

ZERO = Decimal(0)


@pytest.fixture
def world(db: Session) -> dict:
    """A warehouse with two locations, a vendor, a customer and two products."""
    warehouse = factories.make_warehouse(db)
    uom_pieces = factories.make_uom(db, "pcs", allow_fraction=False)
    uom_kilos = factories.make_uom(db, "kg", allow_fraction=True)
    category = factories.make_category(db)
    return {
        "user": factories.make_user(db),
        "warehouse": warehouse,
        "stock": factories.make_location(db, warehouse, "Stock"),
        "rack": factories.make_location(db, warehouse, "ProdRack"),
        "partner": factories.make_partner(db),
        "desk": factories.make_product(db, category, uom_pieces, sku="DESK001", name="Desk"),
        "steel": factories.make_product(db, category, uom_kilos, sku="STEEL001", name="Steel"),
    }


@pytest.fixture
def service(db: Session) -> OperationService:
    return factories.build_operation_service(db)


def quantity_at(db: Session, product_id: int, location_id: int) -> tuple[Decimal, Decimal]:
    """On hand and reserved for one product at one location."""
    quant = db.execute(
        select(StockQuant).where(
            StockQuant.product_id == product_id, StockQuant.location_id == location_id
        )
    ).scalar_one_or_none()
    return (ZERO, ZERO) if quant is None else (quant.quantity, quant.reserved_quantity)


def receive(
    service: OperationService, world: dict, product, quantity: int, *, validate: bool = True
):
    """Shorthand: bring stock in from the vendor."""
    operation = service.create(
        OperationCreate(
            type=OperationType.RECEIPT,
            dest_location_id=world["stock"].id,
            partner_id=world["partner"].id,
            lines=[OperationLineIn(product_id=product.id, quantity=Decimal(quantity))],
        ),
        world["user"],
    )
    service.confirm(operation.id, world["user"])
    if validate:
        service.validate(operation.id, world["user"])
    return operation


def deliver(
    service: OperationService, world: dict, product, quantity: int, *, confirm: bool = True
):
    """Shorthand: send stock out to the customer."""
    operation = service.create(
        OperationCreate(
            type=OperationType.DELIVERY,
            source_location_id=world["stock"].id,
            partner_id=world["partner"].id,
            lines=[OperationLineIn(product_id=product.id, quantity=Decimal(quantity))],
        ),
        world["user"],
    )
    if confirm:
        service.confirm(operation.id, world["user"])
    return operation


def count_stock(service: OperationService, world: dict, product, counted: int):
    """Shorthand: record a physical count."""
    return service.create(
        OperationCreate(
            type=OperationType.ADJUSTMENT,
            source_location_id=world["stock"].id,
            lines=[OperationLineIn(product_id=product.id, counted_quantity=Decimal(counted))],
        ),
        world["user"],
    )


class TestReceipts:
    def test_validating_a_receipt_increases_stock(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50)

        on_hand, reserved = quantity_at(db, world["desk"].id, world["stock"].id)
        assert on_hand == Decimal(50)
        assert reserved == ZERO

    def test_a_receipt_writes_one_ledger_row_per_line(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        operation = receive(service, world, world["desk"], 50)

        move = db.execute(
            select(StockMove).where(StockMove.operation_id == operation.id)
        ).scalar_one()
        assert move.quantity == Decimal(50)
        assert move.to_location_id == world["stock"].id
        assert move.from_location.type == LocationType.VENDOR
        assert move.unit_cost == world["desk"].unit_cost

    def test_stock_is_unchanged_until_the_receipt_is_validated(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50, validate=False)

        assert quantity_at(db, world["desk"].id, world["stock"].id) == (ZERO, ZERO)

    def test_a_receipt_needs_a_contact(self, service: OperationService, world: dict) -> None:
        with pytest.raises(BusinessRuleError, match="needs a contact"):
            service.create(
                OperationCreate(
                    type=OperationType.RECEIPT,
                    dest_location_id=world["stock"].id,
                    lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(5))],
                ),
                world["user"],
            )


class TestDeliveries:
    def test_confirming_reserves_stock_without_removing_it(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50)
        deliver(service, world, world["desk"], 6)

        on_hand, reserved = quantity_at(db, world["desk"].id, world["stock"].id)
        assert on_hand == Decimal(50), "reserving must not remove stock"
        assert reserved == Decimal(6)

    def test_validating_removes_the_stock_and_the_reservation(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50)
        delivery = deliver(service, world, world["desk"], 6)

        service.validate(delivery.id, world["user"])

        assert quantity_at(db, world["desk"].id, world["stock"].id) == (Decimal(44), ZERO)

    def test_a_short_delivery_waits_and_reserves_nothing(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        """All or nothing: a document that cannot be filled must not hold stock hostage."""
        receive(service, world, world["desk"], 4)

        delivery = deliver(service, world, world["desk"], 6)

        assert delivery.status == OperationStatus.WAITING
        _, reserved = quantity_at(db, world["desk"].id, world["stock"].id)
        assert reserved == ZERO

    def test_a_multi_line_delivery_reserves_nothing_if_any_line_is_short(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50)
        receive(service, world, world["steel"], 2)

        delivery = service.create(
            OperationCreate(
                type=OperationType.DELIVERY,
                source_location_id=world["stock"].id,
                partner_id=world["partner"].id,
                lines=[
                    OperationLineIn(product_id=world["desk"].id, quantity=Decimal(5)),
                    OperationLineIn(product_id=world["steel"].id, quantity=Decimal(10)),
                ],
            ),
            world["user"],
        )
        service.confirm(delivery.id, world["user"])

        assert service.get(delivery.id).status == OperationStatus.WAITING
        assert quantity_at(db, world["desk"].id, world["stock"].id)[1] == ZERO

    def test_reserved_stock_is_not_free_for_another_delivery(
        self, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 10)
        deliver(service, world, world["desk"], 8)

        second = deliver(service, world, world["desk"], 5)

        assert second.status == OperationStatus.WAITING, "the first delivery holds 8 of the 10"

    def test_cancelling_a_ready_delivery_returns_the_reservation(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 50)
        delivery = deliver(service, world, world["desk"], 6)

        service.cancel(delivery.id, world["user"])

        assert quantity_at(db, world["desk"].id, world["stock"].id) == (Decimal(50), ZERO)


class TestWaitingDocumentsBecomeReady:
    def test_arriving_stock_releases_a_waiting_delivery(
        self, service: OperationService, world: dict
    ) -> None:
        """The behaviour the demo turns on: receive stock, and the blocked order frees itself."""
        receive(service, world, world["desk"], 4)
        delivery = deliver(service, world, world["desk"], 6)
        assert delivery.status == OperationStatus.WAITING

        receive(service, world, world["desk"], 10)

        assert service.get(delivery.id).status == OperationStatus.READY

    def test_the_released_delivery_now_holds_its_reservation(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 4)
        deliver(service, world, world["desk"], 6)

        receive(service, world, world["desk"], 10)

        _, reserved = quantity_at(db, world["desk"].id, world["stock"].id)
        assert reserved == Decimal(6)

    def test_partial_stock_leaves_the_delivery_waiting(
        self, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 4)
        delivery = deliver(service, world, world["desk"], 20)

        receive(service, world, world["desk"], 5)

        assert service.get(delivery.id).status == OperationStatus.WAITING

    def test_the_longest_waiting_order_is_served_first(
        self, service: OperationService, world: dict
    ) -> None:
        """Two waiting orders, only enough stock for one: the earlier schedule date wins."""
        user = world["user"]
        older = service.create(
            OperationCreate(
                type=OperationType.DELIVERY,
                source_location_id=world["stock"].id,
                partner_id=world["partner"].id,
                schedule_date=date(2026, 1, 1),
                lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(5))],
            ),
            user,
        )
        newer = service.create(
            OperationCreate(
                type=OperationType.DELIVERY,
                source_location_id=world["stock"].id,
                partner_id=world["partner"].id,
                schedule_date=date(2026, 6, 1),
                lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(5))],
            ),
            user,
        )
        service.confirm(older.id, user)
        service.confirm(newer.id, user)

        receive(service, world, world["desk"], 5)

        assert service.get(older.id).status == OperationStatus.READY
        assert service.get(newer.id).status == OperationStatus.WAITING

    def test_check_availability_reports_what_is_still_missing(
        self, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 4)
        delivery = deliver(service, world, world["desk"], 6)

        with pytest.raises(InsufficientStockError) as error:
            service.check_availability(delivery.id, world["user"])

        assert "asked 6" in error.value.details[0]["message"]


class TestInternalTransfers:
    def test_a_transfer_moves_stock_without_changing_the_total(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["steel"], 100)

        transfer = service.create(
            OperationCreate(
                type=OperationType.INTERNAL,
                source_location_id=world["stock"].id,
                dest_location_id=world["rack"].id,
                lines=[OperationLineIn(product_id=world["steel"].id, quantity=Decimal(30))],
            ),
            world["user"],
        )
        service.confirm(transfer.id, world["user"])
        service.validate(transfer.id, world["user"])

        at_stock, _ = quantity_at(db, world["steel"].id, world["stock"].id)
        at_rack, _ = quantity_at(db, world["steel"].id, world["rack"].id)
        assert (at_stock, at_rack) == (Decimal(70), Decimal(30))
        assert at_stock + at_rack == Decimal(100)

    def test_source_and_destination_must_differ(
        self, service: OperationService, world: dict
    ) -> None:
        with pytest.raises(BusinessRuleError, match="different locations"):
            service.create(
                OperationCreate(
                    type=OperationType.INTERNAL,
                    source_location_id=world["stock"].id,
                    dest_location_id=world["stock"].id,
                    lines=[OperationLineIn(product_id=world["steel"].id, quantity=Decimal(5))],
                ),
                world["user"],
            )


class TestAdjustments:
    def test_a_higher_count_raises_stock(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 10)

        adjustment = count_stock(service, world, world["desk"], 12)
        service.validate(adjustment.id, world["user"])

        assert quantity_at(db, world["desk"].id, world["stock"].id)[0] == Decimal(12)

    def test_a_lower_count_reduces_stock(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 10)

        adjustment = count_stock(service, world, world["desk"], 7)
        service.validate(adjustment.id, world["user"])

        assert quantity_at(db, world["desk"].id, world["stock"].id)[0] == Decimal(7)

    def test_the_adjustment_records_what_the_system_thought(
        self, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 10)

        adjustment = count_stock(service, world, world["desk"], 7)
        applied = service.validate(adjustment.id, world["user"])

        assert applied.lines[0].system_quantity == Decimal(10)
        assert applied.lines[0].counted_quantity == Decimal(7)

    def test_a_matching_count_writes_no_ledger_row(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        """Nothing changed, so nothing should be recorded as having moved."""
        receive(service, world, world["desk"], 10)
        before = db.execute(select(StockMove)).scalars().all()

        adjustment = count_stock(service, world, world["desk"], 10)
        service.validate(adjustment.id, world["user"])

        after = db.execute(select(StockMove)).scalars().all()
        assert len(after) == len(before)

    def test_a_count_cannot_go_below_what_is_reserved(
        self, service: OperationService, world: dict
    ) -> None:
        receive(service, world, world["desk"], 10)
        deliver(service, world, world["desk"], 8)

        adjustment = count_stock(service, world, world["desk"], 3)

        with pytest.raises(BusinessRuleError, match="reserved"):
            service.validate(adjustment.id, world["user"])

    def test_an_adjustment_skips_the_confirm_step(
        self, service: OperationService, world: dict
    ) -> None:
        adjustment = count_stock(service, world, world["desk"], 5)

        assert adjustment.status == OperationStatus.DRAFT
        service.validate(adjustment.id, world["user"])
        assert service.get(adjustment.id).status == OperationStatus.DONE


class TestStateMachine:
    def test_a_document_cannot_be_validated_twice(
        self, service: OperationService, world: dict
    ) -> None:
        """Two clicks on Validate must not move the stock twice."""
        operation = receive(service, world, world["desk"], 10)

        with pytest.raises(InvalidTransitionError, match="done"):
            service.validate(operation.id, world["user"])

    def test_a_draft_cannot_jump_straight_to_validated(
        self, service: OperationService, world: dict
    ) -> None:
        operation = receive(service, world, world["desk"], 10, validate=False)
        service.cancel(operation.id, world["user"])

        with pytest.raises(InvalidTransitionError):
            service.validate(operation.id, world["user"])

    def test_a_finished_document_cannot_be_cancelled(
        self, service: OperationService, world: dict
    ) -> None:
        operation = receive(service, world, world["desk"], 10)

        with pytest.raises(InvalidTransitionError):
            service.cancel(operation.id, world["user"])

    def test_only_drafts_can_be_edited(self, service: OperationService, world: dict) -> None:
        operation = receive(service, world, world["desk"], 10, validate=False)

        with pytest.raises(InvalidTransitionError, match="draft"):
            service.update(
                operation.id,
                OperationUpdate(
                    lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(99))]
                ),
                world["user"],
            )


class TestReferences:
    def test_references_follow_the_warehouse_and_type(
        self, service: OperationService, world: dict
    ) -> None:
        operation = receive(service, world, world["desk"], 1, validate=False)

        assert operation.reference == "WH/IN/0001"

    def test_each_type_has_its_own_counter(self, service: OperationService, world: dict) -> None:
        receive(service, world, world["desk"], 5)
        second_receipt = receive(service, world, world["desk"], 5, validate=False)
        delivery = deliver(service, world, world["desk"], 1, confirm=False)

        assert second_receipt.reference == "WH/IN/0002"
        assert delivery.reference == "WH/OUT/0001"

    def test_counters_are_separate_per_warehouse(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        other = factories.make_warehouse(db, short_code="WH2", name="Second")
        other_stock = factories.make_location(db, other, "Stock")

        receive(service, world, world["desk"], 5, validate=False)
        elsewhere = service.create(
            OperationCreate(
                type=OperationType.RECEIPT,
                dest_location_id=other_stock.id,
                partner_id=world["partner"].id,
                lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(5))],
            ),
            world["user"],
        )

        assert elsewhere.reference == "WH2/IN/0001"


class TestValidationRules:
    def test_a_countable_product_rejects_fractional_amounts(
        self, service: OperationService, world: dict
    ) -> None:
        with pytest.raises(BusinessRuleError, match="not a valid amount"):
            service.create(
                OperationCreate(
                    type=OperationType.RECEIPT,
                    dest_location_id=world["stock"].id,
                    partner_id=world["partner"].id,
                    lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal("2.5"))],
                ),
                world["user"],
            )

    def test_a_weighed_product_accepts_fractional_amounts(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        operation = service.create(
            OperationCreate(
                type=OperationType.RECEIPT,
                dest_location_id=world["stock"].id,
                partner_id=world["partner"].id,
                lines=[OperationLineIn(product_id=world["steel"].id, quantity=Decimal("2.5"))],
            ),
            world["user"],
        )
        service.confirm(operation.id, world["user"])
        service.validate(operation.id, world["user"])

        assert quantity_at(db, world["steel"].id, world["stock"].id)[0] == Decimal("2.5")

    def test_a_delivery_cannot_start_from_a_vendor(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        from app.repositories.warehouse_repo import LocationRepository

        vendors = LocationRepository(db).get_or_create_virtual(LocationType.VENDOR)

        with pytest.raises(BusinessRuleError, match="cannot start from"):
            service.create(
                OperationCreate(
                    type=OperationType.DELIVERY,
                    source_location_id=vendors.id,
                    partner_id=world["partner"].id,
                    lines=[OperationLineIn(product_id=world["desk"].id, quantity=Decimal(1))],
                ),
                world["user"],
            )

    def test_an_archived_product_cannot_be_used(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        world["desk"].is_active = False
        db.flush()

        with pytest.raises(BusinessRuleError, match="archived"):
            receive(service, world, world["desk"], 5, validate=False)


class TestLedgerIntegrity:
    def test_the_balance_always_matches_the_ledger(
        self, db: Session, service: OperationService, world: dict
    ) -> None:
        """Run the whole story from the brief, then reconcile the two stock tables."""
        receive(service, world, world["steel"], 100)

        transfer = service.create(
            OperationCreate(
                type=OperationType.INTERNAL,
                source_location_id=world["stock"].id,
                dest_location_id=world["rack"].id,
                lines=[OperationLineIn(product_id=world["steel"].id, quantity=Decimal(100))],
            ),
            world["user"],
        )
        service.confirm(transfer.id, world["user"])
        service.validate(transfer.id, world["user"])

        delivery = service.create(
            OperationCreate(
                type=OperationType.DELIVERY,
                source_location_id=world["rack"].id,
                partner_id=world["partner"].id,
                lines=[OperationLineIn(product_id=world["steel"].id, quantity=Decimal(20))],
            ),
            world["user"],
        )
        service.confirm(delivery.id, world["user"])
        service.validate(delivery.id, world["user"])

        damaged = service.create(
            OperationCreate(
                type=OperationType.ADJUSTMENT,
                source_location_id=world["rack"].id,
                lines=[OperationLineIn(product_id=world["steel"].id, counted_quantity=Decimal(77))],
            ),
            world["user"],
        )
        service.validate(damaged.id, world["user"])

        at_rack, _ = quantity_at(db, world["steel"].id, world["rack"].id)
        assert at_rack == Decimal(77)

        mismatches = db.execute(
            text(
                """
                WITH ledger AS (
                    SELECT product_id, to_location_id AS location_id, quantity FROM stock_moves
                    UNION ALL
                    SELECT product_id, from_location_id, -quantity FROM stock_moves
                )
                SELECT l.product_id, l.location_id
                FROM ledger l
                JOIN locations loc ON loc.id = l.location_id AND loc.type = 'internal'
                LEFT JOIN stock_quants q
                       ON q.product_id = l.product_id AND q.location_id = l.location_id
                GROUP BY l.product_id, l.location_id, q.quantity
                HAVING SUM(l.quantity) <> COALESCE(q.quantity, 0)
                """
            )
        ).all()
        assert mismatches == [], "the running balance drifted from the ledger"
