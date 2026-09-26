"""Declarative base, constraint naming convention and shared column types."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, Identity, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names keep migrations readable and stable across environments.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

QUANTITY = Numeric(14, 3)
MONEY = Numeric(12, 2)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Map a StrEnum to a native PostgreSQL enum that stores the lowercase values."""
    return Enum(enum_cls, name=name, values_callable=lambda members: [m.value for m in members])
