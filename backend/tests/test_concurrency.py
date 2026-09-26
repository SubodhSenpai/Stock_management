"""What happens when several people act at the same moment.

These run against a real database with real threads and real connections, because the
protection being tested is row locking, which no mock can reproduce. Unlike the rest of
the suite these tests commit, so the tables are truncated around them.
"""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.enums import OperationStatus, OperationType
from app.models.stock import StockMove, StockQuant
from app.models.user import User
from app.schemas.operation import OperationCreate, OperationLineIn
from tests import factories

WORKERS = 8

# TRUNCATE rather than DELETE: the ledger has a trigger that refuses row deletions, and
# TRUNCATE does not fire row-level triggers.
ALL_TABLES = """
TRUNCATE stock_moves, operation_lines, operations, operation_sequences, stock_quants,
         reorder_rules, products, product_categories, units_of_measure,
         locations, warehouses, partners, refresh_tokens, password_reset_otps, users
RESTART IDENTITY CASCADE
"""

OPERATIONAL_TABLES = """
TRUNCATE stock_moves, operation_lines, operations, operation_sequences, stock_quants
RESTART IDENTITY CASCADE
"""


def _truncate(engine: Engine, statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


@pytest.fixture(scope="module")
def seeded(engine: Engine) -> Iterator[dict]:
    """Master data, committed so every worker thread can see it.

    The usual rolled-back session will not do here: each thread opens its own connection,
    and one connection cannot see another's uncommitted work.
    """
    _truncate(engine, ALL_TABLES)

    with Session(engine) as db:
        warehouse = factories.make_warehouse(db, short_code="CW", name="Concurrency WH")
        location = factories.make_location(db, warehouse, "Stock")
        uom = factories.make_uom(db, "pcs")
        category = factories.make_category(db, "Concurrency")
        product = factories.make_product(db, category, uom, sku="CONC001", name="Widget")
        partner = factories.make_partner(db, "Concurrency Partner")
        user = factories.make_user(db, "concuser")
        db.commit()
        ids = {
            "location_id": location.id,
            "product_id": product.id,
            "partner_id": partner.id,
            "user_id": user.id,
        }

    yield ids

    # Leave the database as it was found, so the rolled-back tests elsewhere still see
    # the empty tables they expect.
    _truncate(engine, ALL_TABLES)


@pytest.fixture(autouse=True)
def clean_operations(engine: Engine) -> None:
    """Clear documents and balances between tests, keeping the master data."""
    _truncate(engine, OPERATIONAL_TABLES)


def stock_at(engine: Engine, product_id: int, location_id: int) -> tuple[Decimal, Decimal]:
    with Session(engine) as db:
        quant = db.get(StockQuant, (product_id, location_id))
        if quant is None:
            return Decimal(0), Decimal(0)
        return quant.quantity, quant.reserved_quantity


def receive_stock(engine: Engine, seeded: dict, quantity: int) -> None:
    """Put stock on the shelf before the workers start competing for it."""
    with Session(engine) as db:
        service = factories.build_operation_service(db)
        actor = db.get(User, seeded["user_id"])
        operation = service.create(
            OperationCreate(
                type=OperationType.RECEIPT,
                dest_location_id=seeded["location_id"],
                partner_id=seeded["partner_id"],
                lines=[
                    OperationLineIn(product_id=seeded["product_id"], quantity=Decimal(quantity))
                ],
            ),
            actor,
        )
        service.confirm(operation.id, actor)
        service.validate(operation.id, actor)


def confirm_a_delivery(engine: Engine, seeded: dict, quantity: int) -> str:
    """One worker's job: create a delivery and try to reserve stock for it."""
    with Session(engine) as db:
        service = factories.build_operation_service(db)
        actor = db.get(User, seeded["user_id"])
        try:
            operation = service.create(
                OperationCreate(
                    type=OperationType.DELIVERY,
                    source_location_id=seeded["location_id"],
                    partner_id=seeded["partner_id"],
                    lines=[
                        OperationLineIn(product_id=seeded["product_id"], quantity=Decimal(quantity))
                    ],
                ),
                actor,
            )
            return service.confirm(operation.id, actor).status.value
        except AppError as error:
            return f"error:{error.code}"


def validate_operation(engine: Engine, seeded: dict, operation_id: int) -> str:
    with Session(engine) as db:
        service = factories.build_operation_service(db)
        actor = db.get(User, seeded["user_id"])
        try:
            return service.validate(operation_id, actor).status.value
        except AppError as error:
            return f"error:{error.code}"


class TestNoOverselling:
    def test_parallel_reservations_cannot_exceed_what_exists(
        self, engine: Engine, seeded: dict
    ) -> None:
        """10 in stock, eight people each want 2. Exactly five should win."""
        receive_stock(engine, seeded, 10)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            outcomes = list(
                pool.map(lambda _: confirm_a_delivery(engine, seeded, 2), range(WORKERS))
            )

        ready = outcomes.count(OperationStatus.READY.value)
        on_hand, reserved = stock_at(engine, seeded["product_id"], seeded["location_id"])

        assert ready == 5, f"expected 5 winners, got {ready}: {outcomes}"
        assert reserved == Decimal(10), "every unit reserved exactly once"
        assert reserved <= on_hand, "reservations must never exceed stock"

    def test_losers_are_told_to_wait_rather_than_failing(
        self, engine: Engine, seeded: dict
    ) -> None:
        receive_stock(engine, seeded, 4)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            outcomes = list(
                pool.map(lambda _: confirm_a_delivery(engine, seeded, 2), range(WORKERS))
            )

        assert set(outcomes) <= {OperationStatus.READY.value, OperationStatus.WAITING.value}
        assert outcomes.count(OperationStatus.READY.value) == 2

    def test_stock_never_goes_negative_under_load(self, engine: Engine, seeded: dict) -> None:
        receive_stock(engine, seeded, 6)

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(lambda _: confirm_a_delivery(engine, seeded, 3), range(WORKERS)))

        on_hand, reserved = stock_at(engine, seeded["product_id"], seeded["location_id"])
        assert on_hand >= Decimal(0)
        assert reserved <= on_hand


class TestDoubleValidation:
    def test_many_simultaneous_validations_move_stock_once(
        self, engine: Engine, seeded: dict
    ) -> None:
        """The impatient double-click, multiplied by eight."""
        receive_stock(engine, seeded, 100)
        with Session(engine) as db:
            service = factories.build_operation_service(db)
            actor = db.get(User, seeded["user_id"])
            delivery = service.create(
                OperationCreate(
                    type=OperationType.DELIVERY,
                    source_location_id=seeded["location_id"],
                    partner_id=seeded["partner_id"],
                    lines=[OperationLineIn(product_id=seeded["product_id"], quantity=Decimal(10))],
                ),
                actor,
            )
            service.confirm(delivery.id, actor)
            delivery_id = delivery.id

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            outcomes = list(
                pool.map(lambda _: validate_operation(engine, seeded, delivery_id), range(WORKERS))
            )

        assert outcomes.count(OperationStatus.DONE.value) == 1, outcomes
        assert all(outcome.startswith("error:") for outcome in outcomes if outcome != "done")

        on_hand, _ = stock_at(engine, seeded["product_id"], seeded["location_id"])
        assert on_hand == Decimal(90), "stock moved exactly once"

        with Session(engine) as db:
            moves = (
                db.execute(select(StockMove).where(StockMove.operation_id == delivery_id))
                .scalars()
                .all()
            )
        assert len(moves) == 1, "the ledger must record one move, not several"


class TestReferenceNumbering:
    def test_parallel_creates_never_reuse_a_reference(self, engine: Engine, seeded: dict) -> None:
        """The sequence counter is the other place a race would show up."""

        def create_one(_: int) -> str:
            with Session(engine) as db:
                service = factories.build_operation_service(db)
                actor = db.get(User, seeded["user_id"])
                operation = service.create(
                    OperationCreate(
                        type=OperationType.RECEIPT,
                        dest_location_id=seeded["location_id"],
                        partner_id=seeded["partner_id"],
                        lines=[
                            OperationLineIn(product_id=seeded["product_id"], quantity=Decimal(1))
                        ],
                    ),
                    actor,
                )
                return operation.reference

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            references = list(pool.map(create_one, range(WORKERS)))

        assert len(set(references)) == WORKERS, f"duplicate references: {references}"
        assert all(reference.startswith("CW/IN/") for reference in references)
