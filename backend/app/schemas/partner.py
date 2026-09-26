"""Vendors and customers."""

from pydantic import EmailStr, Field

from app.models.enums import PartnerType
from app.schemas.base import ReadModel, StrictModel


class PartnerCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    type: PartnerType
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)


class PartnerUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: PartnerType | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)


class PartnerOut(ReadModel):
    id: int
    name: str
    type: PartnerType
    email: str | None
    phone: str | None
    address: str | None


class PartnerBrief(ReadModel):
    id: int
    name: str
