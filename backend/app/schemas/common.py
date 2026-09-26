"""Response envelopes shared by every endpoint."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class Page(BaseModel, Generic[ItemT]):
    """A page of results, used by every list endpoint except the ledger."""

    items: list[ItemT]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=MAX_PAGE_SIZE)


class Cursor(BaseModel, Generic[ItemT]):
    """Keyset-paginated results: `next_cursor` is null on the last page.

    Used for the stock ledger, which only grows, so OFFSET would get slower every page.
    """

    items: list[ItemT]
    next_cursor: str | None = None


class MessageOut(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class ErrorOut(BaseModel):
    """The single error shape returned by every failing request."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "INSUFFICIENT_STOCK",
                    "message": "Not enough stock at WH/Stock for 1 product.",
                    "details": [
                        {"field": "lines[0].quantity", "message": "[DESK001] Desk: asked 6, free 4"}
                    ],
                    "request_id": "7f3c9a1e",
                }
            }
        }
    )

    error: ErrorBody
