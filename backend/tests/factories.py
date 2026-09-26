"""Helpers for building the records a test needs, without repeating setup everywhere."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.events import EventBus
from app.core.security import hash_password
from app.models.catalog import Product, ProductCategory, ReorderRule, UnitOfMeasure
from app.models.enums import LocationType, PartnerType, UserRole
from app.models.partner import Partner
from app.models.user import User
from app.models.warehouse import Location, Warehouse
from app.repositories.catalog_repo import ProductRepository
from app.repositories.operation_repo import OperationRepository
from app.repositories.partner_repo import PartnerRepository
from app.repositories.stock_repo import MoveRepository, OperationLineRepository, QuantRepository
from app.repositories.warehouse_repo import LocationRepository, WarehouseRepository
from app.services.operation_service import OperationService
from app.services.stock_service import StockService


def make_user(db: Session, login_id: str = "manager1", role: UserRole = UserRole.MANAGER) -> User:
    user = User(
        login_id=login_id,
        email=f"{login_id}@example.com",
        full_name="Test User",
        role=role,
        password_hash=hash_password("Str0ng!Password"),
    )
    db.add(user)
    db.flush()
    return user


def make_warehouse(db: Session, short_code: str = "WH", name: str = "Main Warehouse") -> Warehouse:
    warehouse = Warehouse(name=name, short_code=short_code)
    db.add(warehouse)
    db.flush()
    return warehouse


def make_location(db: Session, warehouse: Warehouse, short_code: str = "Stock") -> Location:
    location = Location(
        name=short_code,
        short_code=short_code,
        type=LocationType.INTERNAL,
        warehouse_id=warehouse.id,
    )
    db.add(location)
    db.flush()
    return location


def make_uom(db: Session, code: str = "pcs", *, allow_fraction: bool = False) -> UnitOfMeasure:
    uom = UnitOfMeasure(code=code, name=code.upper(), allow_fraction=allow_fraction)
    db.add(uom)
    db.flush()
    return uom


def make_category(db: Session, name: str = "Furniture") -> ProductCategory:
    category = ProductCategory(name=name)
    db.add(category)
    db.flush()
    return category


def make_product(
    db: Session,
    category: ProductCategory,
    uom: UnitOfMeasure,
    *,
    sku: str = "DESK001",
    name: str = "Desk",
    unit_cost: Decimal = Decimal("3000.00"),
) -> Product:
    product = Product(
        sku=sku, name=name, category_id=category.id, uom_id=uom.id, unit_cost=unit_cost
    )
    db.add(product)
    db.flush()
    return product


def make_partner(
    db: Session, name: str = "Azure Interior", partner_type: PartnerType = PartnerType.BOTH
) -> Partner:
    partner = Partner(name=name, type=partner_type)
    db.add(partner)
    db.flush()
    return partner


def make_reorder_rule(
    db: Session,
    product: Product,
    warehouse: Warehouse,
    *,
    minimum: Decimal = Decimal(10),
    maximum: Decimal = Decimal(50),
) -> ReorderRule:
    rule = ReorderRule(
        product_id=product.id,
        warehouse_id=warehouse.id,
        min_quantity=minimum,
        max_quantity=maximum,
    )
    db.add(rule)
    db.flush()
    return rule


def build_operation_service(db: Session, event_bus: EventBus | None = None) -> OperationService:
    stock = StockService(db, QuantRepository(db), MoveRepository(db), LocationRepository(db))
    return OperationService(
        db=db,
        operations=OperationRepository(db),
        lines=OperationLineRepository(db),
        locations=LocationRepository(db),
        warehouses=WarehouseRepository(db),
        products=ProductRepository(db),
        partners=PartnerRepository(db),
        stock=stock,
        event_bus=event_bus or EventBus(),
    )
