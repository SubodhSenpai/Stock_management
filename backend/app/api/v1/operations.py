"""Inventory operations: receipts, deliveries, internal transfers and adjustments.

State changes are commands (`POST /{id}/validate`), not a status field the client may set.
Illegal jumps such as draft straight to done are therefore impossible to express, and each
response carries `allowed_actions` so the UI can render buttons without repeating the rules.
"""

from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, OperationServiceDep, PageParams
from app.models.enums import OperationStatus, OperationType
from app.models.operation import Operation
from app.schemas.common import Page
from app.schemas.operation import (
    OperationCreate,
    OperationLineAvailability,
    OperationOut,
    OperationSummary,
    OperationUpdate,
)
from app.services.operation_service import OperationService
from app.services.state_machine import allowed_actions

router = APIRouter(prefix="/operations", tags=["operations"])

ZERO = Decimal(0)


def _to_detail(operation: Operation, service: OperationService) -> OperationOut:
    """Attach per-line availability so the UI can mark lines that cannot be filled."""
    available = service.availability_for(operation)
    lines = []
    for line in operation.lines:
        demand = line.quantity if line.quantity is not None else ZERO
        free = available.get(line.product_id, ZERO)
        lines.append(
            OperationLineAvailability(
                id=line.id,
                product=line.product,
                quantity=line.quantity,
                counted_quantity=line.counted_quantity,
                system_quantity=line.system_quantity,
                available_quantity=free,
                # Adjustments have no demand to satisfy, so their lines are always fine.
                is_available=line.quantity is None or free >= demand,
            )
        )

    summary = OperationSummary.model_validate(operation).model_dump()
    return OperationOut(
        **summary,
        warehouse_id=operation.warehouse_id,
        delivery_address=operation.delivery_address,
        notes=operation.notes,
        validated_at=operation.validated_at,
        lines=lines,
        allowed_actions=allowed_actions(operation),
    )


@router.get("", response_model=Page[OperationSummary])
def list_operations(
    user: CurrentUser,
    service: OperationServiceDep,
    page: PageParams,
    operation_type: OperationType | None = Query(default=None, alias="type"),
    operation_status: list[OperationStatus] | None = Query(default=None, alias="status"),
    warehouse_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    partner_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=100, description="Reference or contact"),
    late: bool = Query(default=False, description="Only overdue, still-open documents"),
) -> Page[OperationSummary]:
    operations, total = service.operations.search(
        operation_type=operation_type,
        statuses=operation_status,
        warehouse_id=warehouse_id,
        location_id=location_id,
        partner_id=partner_id,
        query=q,
        late_only=late,
        limit=page.page_size,
        offset=page.offset,
    )
    return Page(
        items=[OperationSummary.model_validate(operation) for operation in operations],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post("", response_model=OperationOut, status_code=status.HTTP_201_CREATED)
def create_operation(
    body: OperationCreate, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Create a draft document and assign it a reference such as WH/IN/0001."""
    return _to_detail(service.create(body, user), service)


@router.get("/{operation_id}", response_model=OperationOut)
def get_operation(
    operation_id: int, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    return _to_detail(service.get(operation_id), service)


@router.patch("/{operation_id}", response_model=OperationOut)
def update_operation(
    operation_id: int, body: OperationUpdate, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Edit a draft. Supplying `lines` replaces the whole set."""
    return _to_detail(service.update(operation_id, body, user), service)


@router.post("/{operation_id}/confirm", response_model=OperationOut)
def confirm_operation(
    operation_id: int, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Mark as to-do. Outgoing documents reserve stock, or wait if there is not enough."""
    return _to_detail(service.confirm(operation_id, user), service)


@router.post("/{operation_id}/check-availability", response_model=OperationOut)
def check_availability(
    operation_id: int, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Retry the reservation for a waiting document."""
    return _to_detail(service.check_availability(operation_id, user), service)


@router.post("/{operation_id}/validate", response_model=OperationOut)
def validate_operation(
    operation_id: int, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Execute the document: move the stock and write the ledger entries."""
    return _to_detail(service.validate(operation_id, user), service)


@router.post("/{operation_id}/cancel", response_model=OperationOut)
def cancel_operation(
    operation_id: int, user: CurrentUser, service: OperationServiceDep
) -> OperationOut:
    """Cancel the document, releasing any stock it had reserved."""
    return _to_detail(service.cancel(operation_id, user), service)
