"""Dashboard KPIs and low-stock alerts."""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DashboardServiceDep
from app.schemas.dashboard import DashboardSummary, LowStockItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    user: CurrentUser,
    service: DashboardServiceDep,
    warehouse_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
) -> DashboardSummary:
    """Stock counts plus a card per document type.

    Late means still open and scheduled before today; upcoming means scheduled after today.
    """
    return service.summary(warehouse_id=warehouse_id, category_id=category_id)


@router.get("/low-stock", response_model=list[LowStockItem])
def low_stock(
    user: CurrentUser,
    service: DashboardServiceDep,
    warehouse_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[LowStockItem]:
    """Products at or below their reorder level, with a suggested order quantity."""
    return service.low_stock(warehouse_id=warehouse_id, limit=limit)
