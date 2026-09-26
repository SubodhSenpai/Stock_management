"""Stock levels, quick adjustments and the move history."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, OperationServiceDep, PageParams, StockQueryServiceDep
from app.models.enums import OperationType
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Cursor, Page
from app.schemas.operation import (
    OperationCreate,
    OperationLineIn,
    OperationOut,
    StockAdjustRequest,
)
from app.schemas.stock import MoveOut, StockRow

router = APIRouter(tags=["stock"])


@router.get("/stock", response_model=Page[StockRow])
def list_stock(
    user: CurrentUser,
    service: StockQueryServiceDep,
    page: PageParams,
    warehouse_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=100, description="Match on name or SKU"),
) -> Page[StockRow]:
    """On hand and free to use, per product per location."""
    items, total = service.stock_rows(
        warehouse_id=warehouse_id,
        location_id=location_id,
        category_id=category_id,
        query=q,
        limit=page.page_size,
        offset=page.offset,
    )
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/stock/adjust", response_model=OperationOut)
def adjust_stock(
    body: StockAdjustRequest, user: CurrentUser, operations: OperationServiceDep
) -> OperationOut:
    """Set the counted quantity at one location, straight from the stock page.

    This creates and applies an adjustment document, so the correction is recorded in the
    ledger like any other stock change instead of quietly overwriting the balance.
    """
    from app.api.v1.operations import _to_detail

    draft = operations.create(
        OperationCreate(
            type=OperationType.ADJUSTMENT,
            source_location_id=body.location_id,
            lines=[
                OperationLineIn(product_id=body.product_id, counted_quantity=body.counted_quantity)
            ],
            notes="Stock count",
        ),
        user,
    )
    return _to_detail(operations.validate(draft.id, user), operations)


@router.get("/moves", response_model=Cursor[MoveOut])
def move_history(
    user: CurrentUser,
    service: StockQueryServiceDep,
    product_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None, max_length=100, description="Document reference"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Cursor[MoveOut]:
    """The stock ledger, newest first.

    Paginated by cursor rather than page number: the ledger only grows, and an offset would
    get slower with every page.
    """
    items, next_cursor = service.move_history(
        product_id=product_id,
        location_id=location_id,
        warehouse_id=warehouse_id,
        query=q,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )
    return Cursor(items=items, next_cursor=next_cursor)
