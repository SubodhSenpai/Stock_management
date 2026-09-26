"""The database defends its own invariants.

Services check these rules first so users get friendly messages, but these tests prove the
data stays correct even if a service is bypassed or a race slips past an application check.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductCategory, UnitOfMeasure
from app.models.enums import LocationType, OperationStatus, OperationType, UserRole
from app.models.operation import Operation, OperationLine
from app.models.stock import StockMove, StockQuant
from app.models.user import PasswordResetOtp, User
from app.models.warehouse import Location, Warehouse


@pytest.fixture
def user(db: Session) -> User:
    user = User(
        login_id="tester01",
        email="tester@example.com",
        password_hash="not-a-real-hash",
        role=UserRole.MANAGER,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def warehouse(db: Session) -> Warehouse:
    warehouse = Warehouse(name="Main Warehouse", short_code="WH")
    db.add(warehouse)
    db.flush()
    return warehouse


@pytest.fixture
def stock_location(db: Session, warehouse: Warehouse) -> Location:
    location = Location(
        name="Stock", short_code="Stock", type=LocationType.INTERNAL, warehouse_id=warehouse.id
    )
    db.add(location)
    db.flush()
    return location


@pytest.fixture
def vendor_location(db: Session) -> Location:
    location = Location(name="Vendors", short_code="VENDOR", type=LocationType.VENDOR)
    db.add(location)
    db.flush()
    return location


@pytest.fixture
def product(db: Session, user: User) -> Product:
    category = ProductCategory(name="Furniture")
    uom = UnitOfMeasure(code="pcs", name="Pieces", allow_fraction=False)
    db.add_all([category, uom])
    db.flush()

    product = Product(
        sku="DESK001",
        name="Desk",
        category_id=category.id,
        uom_id=uom.id,
        unit_cost=Decimal("3000.00"),
        created_by=user.id,
    )
    db.add(product)
    db.flush()
    return product


def _receipt(warehouse: Warehouse, source: Location, dest: Location, user: User) -> Operation:
    return Operation(
        reference=f"WH/IN/{datetime.now(UTC).timestamp()}",
        type=OperationType.RECEIPT,
        status=OperationStatus.DRAFT,
        warehouse_id=warehouse.id,
        source_location_id=source.id,
        dest_location_id=dest.id,
        partner_id=None,
        created_by=user.id,
    )


class TestStockQuantConstraints:
    def test_stock_cannot_go_negative(
        self, db: Session, product: Product, stock_location: Location
    ) -> None:
        db.add(
            StockQuant(product_id=product.id, location_id=stock_location.id, quantity=Decimal("-1"))
        )
        with pytest.raises(IntegrityError, match="quantity_non_negative"):
            db.flush()

    def test_reserved_cannot_exceed_quantity(
        self, db: Session, product: Product, stock_location: Location
    ) -> None:
        db.add(
            StockQuant(
                product_id=product.id,
                location_id=stock_location.id,
                quantity=Decimal("5"),
                reserved_quantity=Decimal("6"),
            )
        )
        with pytest.raises(IntegrityError, match="reserved_within_on_hand"):
            db.flush()

    def test_free_quantity_is_on_hand_minus_reserved(
        self, db: Session, product: Product, stock_location: Location
    ) -> None:
        quant = StockQuant(
            product_id=product.id,
            location_id=stock_location.id,
            quantity=Decimal("50"),
            reserved_quantity=Decimal("5"),
        )
        db.add(quant)
        db.flush()
        assert quant.free_quantity == Decimal("45")


class TestLocationConstraints:
    def test_internal_location_requires_a_warehouse(self, db: Session) -> None:
        db.add(Location(name="Orphan Rack", short_code="ORPH", type=LocationType.INTERNAL))
        with pytest.raises(IntegrityError, match="warehouse_iff_internal"):
            db.flush()

    def test_virtual_location_cannot_belong_to_a_warehouse(
        self, db: Session, warehouse: Warehouse
    ) -> None:
        db.add(
            Location(
                name="Vendors",
                short_code="VENDOR",
                type=LocationType.VENDOR,
                warehouse_id=warehouse.id,
            )
        )
        with pytest.raises(IntegrityError, match="warehouse_iff_internal"):
            db.flush()


class TestOperationConstraints:
    def test_source_and_destination_must_differ(
        self, db: Session, warehouse: Warehouse, stock_location: Location, user: User
    ) -> None:
        db.add(_receipt(warehouse, stock_location, stock_location, user))
        with pytest.raises(IntegrityError, match="locations_differ"):
            db.flush()

    def test_receipt_requires_a_contact(
        self,
        db: Session,
        warehouse: Warehouse,
        stock_location: Location,
        vendor_location: Location,
        user: User,
    ) -> None:
        db.add(_receipt(warehouse, vendor_location, stock_location, user))
        with pytest.raises(IntegrityError, match="partner_required"):
            db.flush()

    def test_done_requires_a_validation_timestamp(
        self,
        db: Session,
        warehouse: Warehouse,
        stock_location: Location,
        vendor_location: Location,
        user: User,
    ) -> None:
        operation = _receipt(warehouse, vendor_location, stock_location, user)
        operation.type = OperationType.INTERNAL
        operation.source_location_id = stock_location.id
        operation.dest_location_id = vendor_location.id
        operation.status = OperationStatus.DONE
        db.add(operation)
        with pytest.raises(IntegrityError, match="done_iff_validated"):
            db.flush()


class TestOperationLineConstraints:
    @pytest.fixture
    def operation(
        self,
        db: Session,
        warehouse: Warehouse,
        stock_location: Location,
        vendor_location: Location,
        user: User,
    ) -> Operation:
        operation = _receipt(warehouse, stock_location, vendor_location, user)
        operation.type = OperationType.INTERNAL
        db.add(operation)
        db.flush()
        return operation

    def test_line_carries_a_demand_or_a_count_but_not_both(
        self, db: Session, operation: Operation, product: Product
    ) -> None:
        db.add(
            OperationLine(
                operation_id=operation.id,
                product_id=product.id,
                quantity=Decimal("5"),
                counted_quantity=Decimal("5"),
            )
        )
        with pytest.raises(IntegrityError, match="exactly_one_quantity"):
            db.flush()

    def test_line_must_carry_at_least_one_quantity(
        self, db: Session, operation: Operation, product: Product
    ) -> None:
        db.add(OperationLine(operation_id=operation.id, product_id=product.id))
        with pytest.raises(IntegrityError, match="exactly_one_quantity"):
            db.flush()

    def test_a_product_appears_at_most_once_per_document(
        self, db: Session, operation: Operation, product: Product
    ) -> None:
        db.add(
            OperationLine(operation_id=operation.id, product_id=product.id, quantity=Decimal("5"))
        )
        db.flush()
        db.add(
            OperationLine(operation_id=operation.id, product_id=product.id, quantity=Decimal("3"))
        )
        with pytest.raises(IntegrityError, match="operation_id_product_id"):
            db.flush()


class TestLedgerIsAppendOnly:
    @pytest.fixture
    def move(
        self,
        db: Session,
        warehouse: Warehouse,
        stock_location: Location,
        vendor_location: Location,
        product: Product,
        user: User,
    ) -> StockMove:
        operation = _receipt(warehouse, stock_location, vendor_location, user)
        operation.type = OperationType.INTERNAL
        db.add(operation)
        db.flush()

        line = OperationLine(
            operation_id=operation.id, product_id=product.id, quantity=Decimal("10")
        )
        db.add(line)
        db.flush()

        move = StockMove(
            operation_id=operation.id,
            operation_line_id=line.id,
            product_id=product.id,
            from_location_id=stock_location.id,
            to_location_id=vendor_location.id,
            quantity=Decimal("10"),
            unit_cost=product.unit_cost,
            moved_by=user.id,
        )
        db.add(move)
        db.flush()
        return move

    def test_a_ledger_row_cannot_be_updated(self, db: Session, move: StockMove) -> None:
        move.quantity = Decimal("999")
        with pytest.raises(DBAPIError, match="append-only"):
            db.flush()

    def test_a_ledger_row_cannot_be_deleted(self, db: Session, move: StockMove) -> None:
        db.delete(move)
        with pytest.raises(DBAPIError, match="append-only"):
            db.flush()

    def test_a_line_can_only_be_executed_once(
        self,
        db: Session,
        move: StockMove,
        product: Product,
        stock_location: Location,
        vendor_location: Location,
        user: User,
    ) -> None:
        """This is what makes validating the same document twice impossible."""
        db.add(
            StockMove(
                operation_id=move.operation_id,
                operation_line_id=move.operation_line_id,
                product_id=product.id,
                from_location_id=stock_location.id,
                to_location_id=vendor_location.id,
                quantity=Decimal("10"),
                unit_cost=product.unit_cost,
                moved_by=user.id,
            )
        )
        with pytest.raises(IntegrityError, match="operation_line_id"):
            db.flush()


class TestUserConstraints:
    def test_login_id_is_unique_regardless_of_case(self, db: Session, user: User) -> None:
        db.add(
            User(
                login_id=user.login_id.upper(),
                email="other@example.com",
                password_hash="not-a-real-hash",
            )
        )
        with pytest.raises(IntegrityError, match="login_id"):
            db.flush()

    def test_email_must_be_stored_lowercase(self, db: Session) -> None:
        db.add(
            User(
                login_id="casetest",
                email="Mixed@Example.com",
                password_hash="not-a-real-hash",
            )
        )
        with pytest.raises(IntegrityError, match="email_lowercase"):
            db.flush()

    def test_login_id_must_match_the_required_format(self, db: Session) -> None:
        db.add(User(login_id="ab", email="short@example.com", password_hash="x"))
        with pytest.raises(IntegrityError, match="login_id_format"):
            db.flush()


class TestOtpConstraints:
    def test_only_one_live_reset_code_per_user(self, db: Session, user: User) -> None:
        expires = datetime.now(UTC)
        db.add(PasswordResetOtp(user_id=user.id, otp_hash="hash-one", expires_at=expires))
        db.flush()
        db.add(PasswordResetOtp(user_id=user.id, otp_hash="hash-two", expires_at=expires))
        with pytest.raises(IntegrityError, match="one_active"):
            db.flush()
