"""Products, categories, units of measure and reordering rules."""

from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.base import ReadModel, StrictModel
from app.schemas.fields import Sku

Quantity = Field(max_digits=14, decimal_places=3)


class CategoryCreate(StrictModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryOut(ReadModel):
    id: int
    name: str


class UomOut(ReadModel):
    id: int
    code: str
    name: str
    allow_fraction: bool


class InitialStock(StrictModel):
    """Optional opening balance, recorded as a stock adjustment so the ledger stays complete."""

    location_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class ProductCreate(StrictModel):
    sku: Sku
    name: str = Field(min_length=1, max_length=150)
    category_id: int = Field(gt=0)
    uom_id: int = Field(gt=0)
    unit_cost: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=2)
    initial_stock: InitialStock | None = None

    @field_validator("sku")
    @classmethod
    def uppercase(cls, value: str) -> str:
        return value.upper()


class ProductUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category_id: int | None = Field(default=None, gt=0)
    uom_id: int | None = Field(default=None, gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None


class ProductBrief(ReadModel):
    id: int
    sku: str
    name: str

    @property
    def label(self) -> str:
        return f"[{self.sku}] {self.name}"


class ProductOut(ReadModel):
    id: int
    sku: str
    name: str
    category: CategoryOut
    uom: UomOut
    unit_cost: Decimal
    is_active: bool


class ProductStockOut(ProductOut):
    """A product with its stock totals, used by the products list and the stock page."""

    on_hand: Decimal
    reserved: Decimal
    free_to_use: Decimal
    is_low_stock: bool


class ProductLocationStock(ReadModel):
    location: "LocationBrief"
    on_hand: Decimal
    reserved: Decimal
    free_to_use: Decimal


class ReorderRuleCreate(StrictModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    min_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    max_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)


class ReorderRuleUpdate(StrictModel):
    min_quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    max_quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)


class ReorderRuleOut(ReadModel):
    id: int
    product_id: int
    warehouse_id: int
    min_quantity: Decimal
    max_quantity: Decimal


from app.schemas.warehouse import LocationBrief  # noqa: E402  (resolves the forward reference)

ProductLocationStock.model_rebuild()
