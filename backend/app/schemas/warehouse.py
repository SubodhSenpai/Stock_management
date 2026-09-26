"""Warehouses and the locations inside them."""

from pydantic import Field, field_validator

from app.models.enums import LocationType
from app.schemas.base import ReadModel, StrictModel
from app.schemas.fields import LocationCode, WarehouseCode


class WarehouseCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    short_code: WarehouseCode
    address: str | None = Field(default=None, max_length=500)

    @field_validator("short_code")
    @classmethod
    def uppercase(cls, value: str) -> str:
        """Codes appear in references such as WH/IN/0001, so they are stored upper-case."""
        return value.upper()


class WarehouseUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class WarehouseOut(ReadModel):
    id: int
    name: str
    short_code: str
    address: str | None
    is_active: bool


class LocationCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    short_code: LocationCode
    warehouse_id: int = Field(gt=0)


class LocationUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class LocationOut(ReadModel):
    id: int
    name: str
    short_code: str
    code: str  # display form: "WH/Stock" for internal, the plain name for virtual locations
    type: LocationType
    warehouse_id: int | None
    is_active: bool


class LocationBrief(ReadModel):
    """Just enough to label a location on a document."""

    id: int
    code: str
    name: str
    type: LocationType
