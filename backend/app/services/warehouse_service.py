"""Warehouses and locations.

Creating a warehouse also creates its default Stock location, so a new warehouse is
immediately usable without a second step.
"""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, InUseError, NotFoundError
from app.models.enums import LocationType
from app.models.warehouse import Location, Warehouse
from app.repositories.warehouse_repo import LocationRepository, WarehouseRepository
from app.schemas.warehouse import (
    LocationCreate,
    LocationUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)

logger = logging.getLogger(__name__)

DEFAULT_LOCATION_NAME = "Stock"
DEFAULT_LOCATION_CODE = "Stock"


class WarehouseService:
    def __init__(
        self, db: Session, warehouses: WarehouseRepository, locations: LocationRepository
    ) -> None:
        self.db = db
        self.warehouses = warehouses
        self.locations = locations

    def list_warehouses(self, *, include_archived: bool = False) -> list[Warehouse]:
        return self.warehouses.list_all(include_archived=include_archived)

    def get_warehouse(self, warehouse_id: int) -> Warehouse:
        warehouse = self.warehouses.get(warehouse_id)
        if warehouse is None:
            raise NotFoundError("That warehouse does not exist.")
        return warehouse

    def create_warehouse(self, data: WarehouseCreate) -> Warehouse:
        if self.warehouses.code_exists(data.short_code):
            raise DuplicateError(
                f"Short code {data.short_code} is already used by another warehouse.",
                [{"field": "short_code", "message": "Already in use"}],
            )

        warehouse = self.warehouses.add(
            Warehouse(name=data.name, short_code=data.short_code, address=data.address)
        )
        self.locations.add(
            Location(
                name=DEFAULT_LOCATION_NAME,
                short_code=DEFAULT_LOCATION_CODE,
                type=LocationType.INTERNAL,
                warehouse_id=warehouse.id,
            )
        )
        self.db.commit()
        logger.info("Created warehouse %s", warehouse.short_code)
        return warehouse

    def update_warehouse(self, warehouse_id: int, data: WarehouseUpdate) -> Warehouse:
        warehouse = self.get_warehouse(warehouse_id)
        if data.is_active is False:
            self._assert_warehouse_unused(warehouse_id)
        for field in ("name", "address", "is_active"):
            value = getattr(data, field)
            if value is not None:
                setattr(warehouse, field, value)
        self.db.commit()
        return warehouse

    def archive_warehouse(self, warehouse_id: int) -> None:
        """Warehouses are archived, never deleted, because history refers to them."""
        warehouse = self.get_warehouse(warehouse_id)
        self._assert_warehouse_unused(warehouse_id)
        warehouse.is_active = False
        self.db.commit()

    def list_locations(
        self,
        *,
        warehouse_id: int | None = None,
        location_type: LocationType | None = None,
        include_archived: bool = False,
    ) -> list[Location]:
        return self.locations.list_for(
            warehouse_id=warehouse_id,
            location_type=location_type,
            include_archived=include_archived,
        )

    def get_location(self, location_id: int) -> Location:
        location = self.locations.get(location_id)
        if location is None:
            raise NotFoundError("That location does not exist.")
        return location

    def create_location(self, data: LocationCreate) -> Location:
        self.get_warehouse(data.warehouse_id)
        if self.locations.code_exists(data.warehouse_id, data.short_code):
            raise DuplicateError(
                f"This warehouse already has a location coded {data.short_code}.",
                [{"field": "short_code", "message": "Already in use"}],
            )
        location = self.locations.add(
            Location(
                name=data.name,
                short_code=data.short_code,
                type=LocationType.INTERNAL,
                warehouse_id=data.warehouse_id,
            )
        )
        self.db.commit()
        return location

    def update_location(self, location_id: int, data: LocationUpdate) -> Location:
        location = self.get_location(location_id)
        if data.is_active is False and self.locations.has_stock(location_id):
            raise InUseError(f"{location.code} still holds stock, so it cannot be archived.")
        for field in ("name", "is_active"):
            value = getattr(data, field)
            if value is not None:
                setattr(location, field, value)
        self.db.commit()
        return location

    def archive_location(self, location_id: int) -> None:
        location = self.get_location(location_id)
        if self.locations.has_stock(location_id):
            raise InUseError(f"{location.code} still holds stock, so it cannot be archived.")
        location.is_active = False
        self.db.commit()

    def _assert_warehouse_unused(self, warehouse_id: int) -> None:
        if self.warehouses.has_stock(warehouse_id):
            raise InUseError("This warehouse still holds stock, so it cannot be archived.")
        if self.warehouses.has_open_operations(warehouse_id):
            raise InUseError("This warehouse has operations in progress.")
