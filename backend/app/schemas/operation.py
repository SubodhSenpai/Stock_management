"""Inventory operations: receipts, deliveries, internal transfers and adjustments."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, computed_field, field_validator, model_validator

from app.core.clock import today
from app.models.enums import OperationStatus, OperationType
from app.schemas.base import ReadModel, StrictModel
from app.schemas.catalog import ProductBrief
from app.schemas.partner import PartnerBrief
from app.schemas.warehouse import LocationBrief

MAX_LINES = 200


class OperationLineIn(StrictModel):
    """One product on a document.

    Receipts, deliveries and transfers set `quantity` (how much to move). Adjustments set
    `counted_quantity` (what was physically counted).
    """

    product_id: int = Field(gt=0)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    counted_quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)

    @model_validator(mode="after")
    def exactly_one_quantity(self) -> "OperationLineIn":
        if (self.quantity is None) == (self.counted_quantity is None):
            raise ValueError("Provide either quantity or counted_quantity, not both")
        return self


class OperationLineOut(ReadModel):
    id: int
    product: ProductBrief
    quantity: Decimal | None
    counted_quantity: Decimal | None
    system_quantity: Decimal | None


class OperationLineAvailability(OperationLineOut):
    """A line plus what can actually be met from stock, so the UI can flag short lines."""

    available_quantity: Decimal
    is_available: bool


class _OperationBase(StrictModel):
    source_location_id: int | None = Field(default=None, gt=0)
    dest_location_id: int | None = Field(default=None, gt=0)
    partner_id: int | None = Field(default=None, gt=0)
    delivery_address: str | None = Field(default=None, max_length=500)
    schedule_date: date | None = None
    responsible_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class OperationCreate(_OperationBase):
    type: OperationType
    lines: list[OperationLineIn] = Field(min_length=1, max_length=MAX_LINES)

    @field_validator("lines")
    @classmethod
    def products_must_be_unique(cls, lines: list[OperationLineIn]) -> list[OperationLineIn]:
        product_ids = [line.product_id for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product may appear only once; combine the quantities instead")
        return lines


class OperationUpdate(_OperationBase):
    """Edits are only allowed while a document is still a draft.

    Supplying `lines` replaces the whole set, which keeps the client simple and avoids
    half-applied edits.
    """

    lines: list[OperationLineIn] | None = Field(default=None, min_length=1, max_length=MAX_LINES)

    @field_validator("lines")
    @classmethod
    def products_must_be_unique(
        cls, lines: list[OperationLineIn] | None
    ) -> list[OperationLineIn] | None:
        if lines is None:
            return None
        product_ids = [line.product_id for line in lines]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product may appear only once; combine the quantities instead")
        return lines


class UserBrief(ReadModel):
    id: int
    login_id: str
    full_name: str | None


class OperationSummary(ReadModel):
    """Row shape for the operation lists and the kanban board."""

    id: int
    reference: str
    type: OperationType
    status: OperationStatus
    source_location: LocationBrief
    dest_location: LocationBrief
    partner: PartnerBrief | None
    schedule_date: date
    responsible: UserBrief | None
    created_at: datetime

    @computed_field
    @property
    def is_late(self) -> bool:
        """Overdue: still open and scheduled before today."""
        open_states = {OperationStatus.DRAFT, OperationStatus.WAITING, OperationStatus.READY}
        return self.status in open_states and self.schedule_date < today()


class OperationOut(OperationSummary):
    warehouse_id: int
    delivery_address: str | None
    notes: str | None
    validated_at: datetime | None
    lines: list[OperationLineAvailability]
    allowed_actions: list[str]


class StockAdjustRequest(StrictModel):
    """Set the on-hand quantity at one location, from the stock page."""

    product_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    counted_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
