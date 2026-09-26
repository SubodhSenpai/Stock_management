"""Warehouses and locations. Everyone can read them; only managers can change them."""

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, RequireManager, WarehouseServiceDep
from app.models.enums import LocationType
from app.schemas.common import MessageOut
from app.schemas.warehouse import (
    LocationCreate,
    LocationOut,
    LocationUpdate,
    WarehouseCreate,
    WarehouseOut,
    WarehouseUpdate,
)

router = APIRouter(tags=["warehouses"])


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(
    user: CurrentUser,
    service: WarehouseServiceDep,
    include_archived: bool = Query(default=False),
) -> list[WarehouseOut]:
    return service.list_warehouses(include_archived=include_archived)


@router.post("/warehouses", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    body: WarehouseCreate, user: RequireManager, service: WarehouseServiceDep
) -> WarehouseOut:
    """Create a warehouse. Its default Stock location is created at the same time."""
    return service.create_warehouse(body)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseOut)
def get_warehouse(
    warehouse_id: int, user: CurrentUser, service: WarehouseServiceDep
) -> WarehouseOut:
    return service.get_warehouse(warehouse_id)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: int,
    body: WarehouseUpdate,
    user: RequireManager,
    service: WarehouseServiceDep,
) -> WarehouseOut:
    return service.update_warehouse(warehouse_id, body)


@router.delete("/warehouses/{warehouse_id}", response_model=MessageOut)
def archive_warehouse(
    warehouse_id: int, user: RequireManager, service: WarehouseServiceDep
) -> MessageOut:
    """Archive rather than delete, because past documents still refer to this warehouse."""
    service.archive_warehouse(warehouse_id)
    return MessageOut(message="Warehouse archived.")


@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    user: CurrentUser,
    service: WarehouseServiceDep,
    warehouse_id: int | None = Query(default=None, gt=0),
    location_type: LocationType | None = Query(default=None, alias="type"),
    include_archived: bool = Query(default=False),
) -> list[LocationOut]:
    return service.list_locations(
        warehouse_id=warehouse_id,
        location_type=location_type,
        include_archived=include_archived,
    )


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    body: LocationCreate, user: RequireManager, service: WarehouseServiceDep
) -> LocationOut:
    return service.create_location(body)


@router.patch("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int, body: LocationUpdate, user: RequireManager, service: WarehouseServiceDep
) -> LocationOut:
    return service.update_location(location_id, body)


@router.delete("/locations/{location_id}", response_model=MessageOut)
def archive_location(
    location_id: int, user: RequireManager, service: WarehouseServiceDep
) -> MessageOut:
    service.archive_location(location_id)
    return MessageOut(message="Location archived.")
