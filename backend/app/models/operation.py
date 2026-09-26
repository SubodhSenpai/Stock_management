"""Inventory operations (receipts, deliveries, internal transfers, adjustments) and their lines."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import QUANTITY, Base, IdMixin, TimestampMixin, pg_enum
from app.models.catalog import Product
from app.models.enums import OperationStatus, OperationType
from app.models.partner import Partner
from app.models.user import User
from app.models.warehouse import Location, Warehouse

OPERATION_TYPE = pg_enum(OperationType, "operation_type")
OPERATION_STATUS = pg_enum(OperationStatus, "operation_status")


class OperationSequence(Base):
    """Per-warehouse, per-type counter behind references such as WH/IN/0001."""

    __tablename__ = "operation_sequences"
    __table_args__ = (CheckConstraint("next_number > 0", name="next_number_positive"),)

    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True
    )
    type: Mapped[OperationType] = mapped_column(OPERATION_TYPE, primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Operation(IdMixin, TimestampMixin, Base):
    """A stock document. Every type moves stock from `source_location` to `dest_location`."""

    __tablename__ = "operations"
    __table_args__ = (
        CheckConstraint("source_location_id <> dest_location_id", name="locations_differ"),
        CheckConstraint(
            "(status = 'done') = (validated_at IS NOT NULL)", name="done_iff_validated"
        ),
        CheckConstraint(
            "type NOT IN ('receipt', 'delivery') OR partner_id IS NOT NULL",
            name="partner_required",
        ),
        UniqueConstraint("reference"),
        Index("ix_operations_type_status", "type", "status"),
        Index(
            "ix_operations_pending_schedule_date",
            "schedule_date",
            postgresql_where=text("status IN ('draft', 'waiting', 'ready')"),
        ),
        Index(
            "ix_operations_reference_trgm",
            "reference",
            postgresql_using="gin",
            postgresql_ops={"reference": "gin_trgm_ops"},
        ),
    )

    reference: Mapped[str] = mapped_column(String(30))
    type: Mapped[OperationType] = mapped_column(OPERATION_TYPE)
    status: Mapped[OperationStatus] = mapped_column(
        OPERATION_STATUS, default=OperationStatus.DRAFT, server_default=OperationStatus.DRAFT.value
    )
    warehouse_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("warehouses.id"), index=True)
    source_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("locations.id"), index=True
    )
    dest_location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("locations.id"), index=True
    )
    partner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("partners.id"), index=True
    )
    delivery_address: Mapped[str | None] = mapped_column(Text)
    schedule_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    responsible_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    validated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    warehouse: Mapped[Warehouse] = relationship()
    source_location: Mapped[Location] = relationship(foreign_keys=[source_location_id])
    dest_location: Mapped[Location] = relationship(foreign_keys=[dest_location_id])
    partner: Mapped[Partner | None] = relationship()
    responsible: Mapped[User | None] = relationship(foreign_keys=[responsible_id])
    lines: Mapped[list["OperationLine"]] = relationship(
        back_populates="operation",
        cascade="all, delete-orphan",
        order_by="OperationLine.id",
    )


class OperationLine(IdMixin, Base):
    """One product on an operation.

    Receipts, deliveries and transfers use `quantity` (the demand). Adjustments use
    `counted_quantity` (the physical count) and record `system_quantity` when applied.
    """

    __tablename__ = "operation_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("counted_quantity >= 0", name="counted_quantity_non_negative"),
        CheckConstraint(
            "num_nonnulls(quantity, counted_quantity) = 1", name="exactly_one_quantity"
        ),
        # Also serves as the index on operation_id (leading column).
        UniqueConstraint("operation_id", "product_id"),
        Index("ix_operation_lines_product_id", "product_id"),
    )

    operation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("operations.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    counted_quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    system_quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)

    operation: Mapped[Operation] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
