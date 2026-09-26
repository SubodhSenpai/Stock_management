"""Warehouses and the locations (racks, rooms, virtual counterparties) that hold stock."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, pg_enum
from app.models.enums import LocationType


class Warehouse(IdMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint("short_code ~ '^[A-Z0-9]{1,5}$'", name="short_code_format"),
        UniqueConstraint("short_code"),
    )

    name: Mapped[str] = mapped_column(String(100))
    short_code: Mapped[str] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    locations: Mapped[list["Location"]] = relationship(back_populates="warehouse")


class Location(IdMixin, TimestampMixin, Base):
    """A place stock can be. Internal locations belong to a warehouse; virtual ones never do."""

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("short_code ~ '^[A-Za-z0-9-]{1,20}$'", name="short_code_format"),
        CheckConstraint(
            "(type = 'internal') = (warehouse_id IS NOT NULL)", name="warehouse_iff_internal"
        ),
        UniqueConstraint("warehouse_id", "short_code", postgresql_nulls_not_distinct=True),
    )

    name: Mapped[str] = mapped_column(String(100))
    short_code: Mapped[str] = mapped_column(String(20))
    type: Mapped[LocationType] = mapped_column(
        pg_enum(LocationType, "location_type"),
        default=LocationType.INTERNAL,
        server_default=LocationType.INTERNAL.value,
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    warehouse: Mapped[Warehouse | None] = relationship(back_populates="locations")

    @property
    def code(self) -> str:
        """Display code, e.g. 'WH/Stock'. Virtual locations show their name."""
        if self.warehouse is None:
            return self.name
        return f"{self.warehouse.short_code}/{self.short_code}"
