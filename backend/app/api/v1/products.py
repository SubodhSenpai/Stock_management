"""Products, categories, units of measure and reordering rules."""

from fastapi import APIRouter, Query, status

from app.api.deps import (
    CurrentUser,
    OperationServiceDep,
    PageParams,
    ProductServiceDep,
    RequireManager,
)
from app.schemas.catalog import (
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductLocationStock,
    ProductOut,
    ProductStockOut,
    ProductUpdate,
    ReorderRuleCreate,
    ReorderRuleOut,
    ReorderRuleUpdate,
    UomOut,
)
from app.schemas.common import MessageOut, Page
from app.schemas.warehouse import LocationBrief

router = APIRouter(tags=["products"])


@router.get("/products", response_model=Page[ProductStockOut])
def search_products(
    user: CurrentUser,
    service: ProductServiceDep,
    page: PageParams,
    q: str | None = Query(default=None, max_length=100, description="Match on name or SKU"),
    category_id: int | None = Query(default=None, gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    include_archived: bool = Query(default=False),
) -> Page[ProductStockOut]:
    """Search products, with stock totals for the selected warehouse (or all warehouses)."""
    rows, total = service.search(
        query=q,
        category_id=category_id,
        warehouse_id=warehouse_id,
        include_archived=include_archived,
        limit=page.page_size,
        offset=page.offset,
    )
    items = [
        ProductStockOut(
            **ProductOut.model_validate(product).model_dump(),
            on_hand=on_hand,
            reserved=reserved,
            free_to_use=on_hand - reserved,
            is_low_stock=is_low,
        )
        for product, on_hand, reserved, is_low in rows
    ]
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    user: RequireManager,
    service: ProductServiceDep,
    operations: OperationServiceDep,
) -> ProductOut:
    """Create a product.

    Any opening stock is recorded as an adjustment document rather than written straight
    into the balance, so the ledger still explains where those units came from.
    """
    product, opening_stock = service.create(body, user)
    if opening_stock is not None:
        adjustment = operations.create(opening_stock, user)
        operations.validate(adjustment.id, user)
    return service.get(product.id)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, user: CurrentUser, service: ProductServiceDep) -> ProductOut:
    return service.get(product_id)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, body: ProductUpdate, user: RequireManager, service: ProductServiceDep
) -> ProductOut:
    return service.update(product_id, body)


@router.delete("/products/{product_id}", response_model=MessageOut)
def archive_product(
    product_id: int, user: RequireManager, service: ProductServiceDep
) -> MessageOut:
    service.archive(product_id)
    return MessageOut(message="Product archived.")


@router.get("/products/{product_id}/stock", response_model=list[ProductLocationStock])
def product_stock(
    product_id: int, user: CurrentUser, service: ProductServiceDep
) -> list[ProductLocationStock]:
    """Where this product is held, and how much of it is free to use."""
    return [
        ProductLocationStock(
            location=LocationBrief.model_validate(location),
            on_hand=quant.quantity,
            reserved=quant.reserved_quantity,
            free_to_use=quant.quantity - quant.reserved_quantity,
        )
        for location, quant in service.stock_by_location(product_id)
    ]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, service: ProductServiceDep) -> list[CategoryOut]:
    return service.list_categories()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate, user: RequireManager, service: ProductServiceDep
) -> CategoryOut:
    return service.create_category(body)


@router.delete("/categories/{category_id}", response_model=MessageOut)
def delete_category(
    category_id: int, user: RequireManager, service: ProductServiceDep
) -> MessageOut:
    service.delete_category(category_id)
    return MessageOut(message="Category deleted.")


@router.get("/uoms", response_model=list[UomOut])
def list_uoms(user: CurrentUser, service: ProductServiceDep) -> list[UomOut]:
    return service.list_uoms()


@router.get("/reorder-rules", response_model=list[ReorderRuleOut])
def list_reorder_rules(
    user: CurrentUser,
    service: ProductServiceDep,
    product_id: int | None = Query(default=None, gt=0),
) -> list[ReorderRuleOut]:
    return service.list_rules(product_id=product_id)


@router.post("/reorder-rules", response_model=ReorderRuleOut, status_code=status.HTTP_201_CREATED)
def create_reorder_rule(
    body: ReorderRuleCreate, user: RequireManager, service: ProductServiceDep
) -> ReorderRuleOut:
    return service.create_rule(body)


@router.patch("/reorder-rules/{rule_id}", response_model=ReorderRuleOut)
def update_reorder_rule(
    rule_id: int, body: ReorderRuleUpdate, user: RequireManager, service: ProductServiceDep
) -> ReorderRuleOut:
    return service.update_rule(rule_id, body)


@router.delete("/reorder-rules/{rule_id}", response_model=MessageOut)
def delete_reorder_rule(
    rule_id: int, user: RequireManager, service: ProductServiceDep
) -> MessageOut:
    service.delete_rule(rule_id)
    return MessageOut(message="Reordering rule deleted.")
