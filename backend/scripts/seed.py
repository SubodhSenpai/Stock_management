"""Load demo data.

Safe to run repeatedly: existing records are left alone rather than duplicated.

    python -m scripts.seed
"""

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.clock import today as utc_today  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.events import EventBus  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.catalog import Product, ProductCategory, ReorderRule, UnitOfMeasure  # noqa: E402
from app.models.enums import LocationType, OperationType, PartnerType, UserRole  # noqa: E402
from app.models.partner import Partner  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.warehouse import Location, Warehouse  # noqa: E402
from app.repositories.catalog_repo import ProductRepository  # noqa: E402
from app.repositories.operation_repo import OperationRepository  # noqa: E402
from app.repositories.partner_repo import PartnerRepository  # noqa: E402
from app.repositories.stock_repo import (  # noqa: E402
    MoveRepository,
    OperationLineRepository,
    QuantRepository,
)
from app.repositories.warehouse_repo import LocationRepository, WarehouseRepository  # noqa: E402
from app.schemas.operation import OperationCreate, OperationLineIn  # noqa: E402
from app.services.operation_service import OperationService  # noqa: E402
from app.services.stock_service import StockService  # noqa: E402

DEMO_USERS = [
    ("manager1", "manager@stocksense.local", "Priya Sharma", UserRole.MANAGER, "Manager@123"),
    ("staff001", "staff@stocksense.local", "Arjun Nair", UserRole.STAFF, "Staff@1234"),
]

UOMS = [
    ("pcs", "Pieces", False),
    ("kg", "Kilograms", True),
    ("m", "Metres", True),
    ("l", "Litres", True),
    ("box", "Boxes", False),
]

CATEGORIES = ["Furniture", "Raw Material", "Electronics"]

WAREHOUSES = [
    ("Main Warehouse", "WH", "12 MG Road, Pune", ["Stock2", "ProdRack"]),
    ("Secondary Warehouse", "WH2", "48 Ring Road, Nashik", []),
]

PARTNERS = [
    ("Azure Interior", PartnerType.BOTH, "contact@azure.example"),
    ("Steel Corp", PartnerType.VENDOR, "sales@steelcorp.example"),
    ("Deco Addict", PartnerType.CUSTOMER, "orders@deco.example"),
]

PRODUCTS = [
    ("DESK001", "Desk", "Furniture", "pcs", Decimal("3000.00")),
    ("TABLE001", "Table", "Furniture", "pcs", Decimal("3000.00")),
    ("CHAIR001", "Chair", "Furniture", "pcs", Decimal("1200.00")),
    ("STEEL001", "Steel Rod", "Raw Material", "kg", Decimal("85.50")),
    ("CABLE001", "Cable Reel", "Electronics", "m", Decimal("42.00")),
]

# product SKU -> (minimum, maximum)
REORDER_RULES = {"DESK001": (10, 50), "STEEL001": (100, 500)}

# Opening stock, kept deliberately tight on desks so a delivery below has to wait.
OPENING_STOCK = {"DESK001": 8, "TABLE001": 25, "CHAIR001": 40, "STEEL001": 250, "CABLE001": 120}


ModelT = TypeVar("ModelT")


def get_or_create(db: Session, model: type[ModelT], defaults: dict, **lookup) -> ModelT:
    """Fetch the matching row, or create it. Lets the seed script be re-run safely."""
    instance = db.execute(select(model).filter_by(**lookup)).scalars().first()
    if instance is not None:
        return instance
    instance = model(**lookup, **defaults)
    db.add(instance)
    db.flush()
    return instance


def build_operation_service(db: Session) -> OperationService:
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
        event_bus=EventBus(),  # detached: seeding should not broadcast to connected clients
    )


def seed_reference_data(db: Session) -> dict:
    users = {
        login_id: get_or_create(
            db,
            User,
            {
                "email": email,
                "full_name": full_name,
                "role": role,
                "password_hash": hash_password(password),
            },
            login_id=login_id,
        )
        for login_id, email, full_name, role, password in DEMO_USERS
    }
    uoms = {
        code: get_or_create(
            db, UnitOfMeasure, {"name": name, "allow_fraction": fraction}, code=code
        )
        for code, name, fraction in UOMS
    }
    categories = {name: get_or_create(db, ProductCategory, {}, name=name) for name in CATEGORIES}
    partners = {
        name: get_or_create(db, Partner, {"type": partner_type, "email": email}, name=name)
        for name, partner_type, email in PARTNERS
    }

    warehouses, locations = {}, {}
    for name, code, address, extra_locations in WAREHOUSES:
        warehouse = get_or_create(
            db, Warehouse, {"name": name, "address": address}, short_code=code
        )
        warehouses[code] = warehouse
        for location_code in ["Stock", *extra_locations]:
            locations[f"{code}/{location_code}"] = get_or_create(
                db,
                Location,
                {"name": location_code, "type": LocationType.INTERNAL},
                warehouse_id=warehouse.id,
                short_code=location_code,
            )

    products = {}
    for sku, name, category, uom_code, cost in PRODUCTS:
        products[sku] = get_or_create(
            db,
            Product,
            {
                "name": name,
                "category_id": categories[category].id,
                "uom_id": uoms[uom_code].id,
                "unit_cost": cost,
                "created_by": users["manager1"].id,
            },
            sku=sku,
        )

    for sku, (minimum, maximum) in REORDER_RULES.items():
        get_or_create(
            db,
            ReorderRule,
            {"min_quantity": Decimal(minimum), "max_quantity": Decimal(maximum)},
            product_id=products[sku].id,
            warehouse_id=warehouses["WH"].id,
        )

    db.commit()
    return {
        "users": users,
        "products": products,
        "partners": partners,
        "locations": locations,
        "warehouses": warehouses,
    }


def seed_operations(db: Session, data: dict) -> None:
    """Create documents covering every state, so the dashboard has something to show."""
    service = build_operation_service(db)
    manager = data["users"]["manager1"]
    products, partners, locations = data["products"], data["partners"], data["locations"]

    if OperationRepository(db).search(limit=1)[1] > 0:
        print("Operations already exist, skipping.")
        return

    main_stock = locations["WH/Stock"].id
    today = utc_today()

    # Opening stock, recorded as adjustments so the ledger explains every unit.
    opening = service.create(
        OperationCreate(
            type=OperationType.ADJUSTMENT,
            source_location_id=main_stock,
            schedule_date=today,
            notes="Opening stock",
            lines=[
                OperationLineIn(product_id=products[sku].id, counted_quantity=Decimal(quantity))
                for sku, quantity in OPENING_STOCK.items()
            ],
        ),
        manager,
    )
    service.validate(opening.id, manager)

    # A receipt still to be processed, scheduled in the future.
    service.confirm(
        service.create(
            OperationCreate(
                type=OperationType.RECEIPT,
                dest_location_id=main_stock,
                partner_id=partners["Steel Corp"].id,
                schedule_date=today + timedelta(days=2),
                lines=[OperationLineIn(product_id=products["STEEL001"].id, quantity=Decimal(100))],
            ),
            manager,
        ).id,
        manager,
    )

    # An overdue receipt, so the dashboard shows a late count.
    service.confirm(
        service.create(
            OperationCreate(
                type=OperationType.RECEIPT,
                dest_location_id=main_stock,
                partner_id=partners["Azure Interior"].id,
                schedule_date=today - timedelta(days=3),
                lines=[OperationLineIn(product_id=products["DESK001"].id, quantity=Decimal(20))],
            ),
            manager,
        ).id,
        manager,
    )

    # Two deliveries that can be filled from stock.
    for quantity in (Decimal(5), Decimal(10)):
        service.confirm(
            service.create(
                OperationCreate(
                    type=OperationType.DELIVERY,
                    source_location_id=main_stock,
                    partner_id=partners["Deco Addict"].id,
                    delivery_address="22 Residency Road, Bengaluru",
                    schedule_date=today + timedelta(days=1),
                    lines=[OperationLineIn(product_id=products["CHAIR001"].id, quantity=quantity)],
                ),
                manager,
            ).id,
            manager,
        )

    # A delivery for more desks than exist, so it lands in Waiting. Validating the late
    # receipt above releases it automatically.
    service.confirm(
        service.create(
            OperationCreate(
                type=OperationType.DELIVERY,
                source_location_id=main_stock,
                partner_id=partners["Azure Interior"].id,
                delivery_address="12 MG Road, Pune",
                schedule_date=today + timedelta(days=1),
                lines=[OperationLineIn(product_id=products["DESK001"].id, quantity=Decimal(15))],
            ),
            manager,
        ).id,
        manager,
    )

    # An internal transfer that has already been carried out.
    transfer = service.create(
        OperationCreate(
            type=OperationType.INTERNAL,
            source_location_id=main_stock,
            dest_location_id=locations["WH/ProdRack"].id,
            schedule_date=today,
            lines=[OperationLineIn(product_id=products["STEEL001"].id, quantity=Decimal(50))],
        ),
        manager,
    )
    service.confirm(transfer.id, manager)
    service.validate(transfer.id, manager)

    # A draft transfer, left unconfirmed.
    service.create(
        OperationCreate(
            type=OperationType.INTERNAL,
            source_location_id=main_stock,
            dest_location_id=locations["WH/Stock2"].id,
            schedule_date=today + timedelta(days=4),
            lines=[OperationLineIn(product_id=products["TABLE001"].id, quantity=Decimal(5))],
        ),
        manager,
    )


def main() -> None:
    with SessionLocal() as db:
        print("Seeding reference data...")
        data = seed_reference_data(db)
        print("Seeding operations...")
        seed_operations(db, data)

    print("\nDone. Sign in with:")
    for login_id, _, _, role, password in DEMO_USERS:
        print(f"  {login_id} / {password}  ({role.value})")


if __name__ == "__main__":
    main()
