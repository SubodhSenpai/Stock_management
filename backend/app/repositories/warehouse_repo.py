"""Queries over warehouses and locations."""

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.enums import LocationType, OperationStatus
from app.models.operation import Operation
from app.models.stock import StockQuant
from app.models.warehouse import Location, Warehouse

# Virtual locations are global singletons: the counterparties in the double-entry ledger.
VIRTUAL_LOCATION_DEFAULTS = {
    LocationType.VENDOR: ("Vendors", "VENDOR"),
    LocationType.CUSTOMER: ("Customers", "CUSTOMER"),
    LocationType.ADJUSTMENT: ("Inventory Adjustment", "ADJUST"),
}


class WarehouseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, warehouse_id: int) -> Warehouse | None:
        return self.db.get(Warehouse, warehouse_id)

    def list_all(self, *, include_archived: bool = False) -> list[Warehouse]:
        stmt = select(Warehouse).order_by(Warehouse.name)
        if not include_archived:
            stmt = stmt.where(Warehouse.is_active)
        return list(self.db.execute(stmt).scalars())

    def code_exists(self, short_code: str) -> bool:
        stmt = select(Warehouse.id).where(Warehouse.short_code == short_code.upper())
        return self.db.execute(stmt).first() is not None

    def add(self, warehouse: Warehouse) -> Warehouse:
        self.db.add(warehouse)
        self.db.flush()
        return warehouse

    def has_stock(self, warehouse_id: int) -> bool:
        stmt = select(
            exists().where(
                StockQuant.location_id == Location.id,
                Location.warehouse_id == warehouse_id,
                StockQuant.quantity > 0,
            )
        )
        return bool(self.db.execute(stmt).scalar())

    def has_open_operations(self, warehouse_id: int) -> bool:
        stmt = select(
            exists().where(
                Operation.warehouse_id == warehouse_id,
                Operation.status.in_(
                    [OperationStatus.DRAFT, OperationStatus.WAITING, OperationStatus.READY]
                ),
            )
        )
        return bool(self.db.execute(stmt).scalar())


class LocationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, location_id: int) -> Location | None:
        stmt = (
            select(Location)
            .options(selectinload(Location.warehouse))
            .where(Location.id == location_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_many(self, location_ids: list[int]) -> dict[int, Location]:
        if not location_ids:
            return {}
        stmt = (
            select(Location)
            .options(selectinload(Location.warehouse))
            .where(Location.id.in_(location_ids))
        )
        return {location.id: location for location in self.db.execute(stmt).scalars()}

    def list_for(
        self,
        *,
        warehouse_id: int | None = None,
        location_type: LocationType | None = None,
        include_archived: bool = False,
    ) -> list[Location]:
        stmt = select(Location).options(selectinload(Location.warehouse))
        if warehouse_id is not None:
            stmt = stmt.where(Location.warehouse_id == warehouse_id)
        if location_type is not None:
            stmt = stmt.where(Location.type == location_type)
        if not include_archived:
            stmt = stmt.where(Location.is_active)
        return list(self.db.execute(stmt.order_by(Location.name)).scalars())

    def internal_ids_for_warehouse(self, warehouse_id: int) -> list[int]:
        stmt = select(Location.id).where(
            Location.warehouse_id == warehouse_id, Location.type == LocationType.INTERNAL
        )
        return list(self.db.execute(stmt).scalars())

    def code_exists(self, warehouse_id: int, short_code: str) -> bool:
        stmt = select(Location.id).where(
            Location.warehouse_id == warehouse_id,
            func.lower(Location.short_code) == short_code.lower(),
        )
        return self.db.execute(stmt).first() is not None

    def add(self, location: Location) -> Location:
        self.db.add(location)
        self.db.flush()
        return location

    def get_or_create_virtual(self, location_type: LocationType) -> Location:
        """Return the shared virtual location for this type, creating it if needed.

        Uses an upsert so two concurrent first-time callers cannot create duplicates.
        """
        name, short_code = VIRTUAL_LOCATION_DEFAULTS[location_type]
        self.db.execute(
            insert(Location)
            .values(name=name, short_code=short_code, type=location_type, warehouse_id=None)
            .on_conflict_do_nothing(index_elements=[Location.warehouse_id, Location.short_code])
        )
        stmt = select(Location).where(
            Location.warehouse_id.is_(None), Location.type == location_type
        )
        return self.db.execute(stmt).scalars().first()

    def has_stock(self, location_id: int) -> bool:
        stmt = select(
            exists().where(StockQuant.location_id == location_id, StockQuant.quantity > 0)
        )
        return bool(self.db.execute(stmt).scalar())
