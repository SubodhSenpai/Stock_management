"""Stock levels and the move ledger."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.schemas.base import ReadModel
from app.schemas.catalog import ProductBrief
from app.schemas.warehouse import LocationBrief


class MoveDirection(StrEnum):
    """How a move looks from the warehouse's point of view. Drives the row colour in the UI."""

    IN = "in"
    OUT = "out"
    INTERNAL = "internal"


class StockRow(ReadModel):
    """One row of the stock page: a product at a location."""

    product: ProductBrief
    location: LocationBrief
    unit_cost: Decimal
    on_hand: Decimal
    reserved: Decimal
    free_to_use: Decimal


class MoveOut(ReadModel):
    """One line of the ledger. Quantity is always positive; direction comes from the locations."""

    id: int
    operation_id: int
    reference: str
    product: ProductBrief
    from_location: LocationBrief
    to_location: LocationBrief
    quantity: Decimal
    direction: MoveDirection
    contact: str | None
    moved_at: datetime
