"""Stock balance (quants), the append-only stock ledger (moves) and the stock_levels read view."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, QUANTITY, Base, IdMixin
from app.models.catalog import Product
from app.models.warehouse import Location


class StockQuant(Base):
    """Current quantity of one product at one internal location.

    A cache of the ledger, updated in the same transaction as each move, so reads are O(1).
    """

    __tablename__ = "stock_quants"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="reserved_within_on_hand",
        ),
        Index("ix_stock_quants_location_id", "location_id"),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal(0), server_default="0")
    reserved_quantity: Mapped[Decimal] = mapped_column(
        QUANTITY, default=Decimal(0), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped[Product] = relationship()
    location: Mapped[Location] = relationship()

    @property
    def free_quantity(self) -> Decimal:
        return self.quantity - self.reserved_quantity


class StockMove(IdMixin, Base):
    """One executed movement of stock between two locations. Rows are never updated or deleted
    (a database trigger enforces this), so the ledger is a trustworthy audit trail."""

    __tablename__ = "stock_moves"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("from_location_id <> to_location_id", name="locations_differ"),
        # One line can be executed at most once: the DB itself blocks double validation.
        UniqueConstraint("operation_line_id"),
        Index("ix_stock_moves_product_id_moved_at", "product_id", "moved_at"),
        Index("ix_stock_moves_from_location_id", "from_location_id"),
        Index("ix_stock_moves_to_location_id", "to_location_id"),
        Index("ix_stock_moves_operation_id", "operation_id"),
        # Keyset pagination for Move History; B-tree scans backwards for DESC order.
        Index("ix_stock_moves_moved_at_id", "moved_at", "id"),
    )

    operation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("operations.id"))
    operation_line_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("operation_lines.id"))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    from_location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id"))
    to_location_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("locations.id"))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    moved_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship()
    from_location: Mapped[Location] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped[Location] = relationship(foreign_keys=[to_location_id])


# Read-only view created by migration 0001: on hand / reserved / free per product per warehouse.
# Kept on its own MetaData so Alembic never tries to create it as a table.
stock_levels = Table(
    "stock_levels",
    MetaData(),
    Column("product_id", BigInteger),
    Column("warehouse_id", BigInteger),
    Column("on_hand", QUANTITY),
    Column("reserved", QUANTITY),
    Column("free_to_use", QUANTITY),
)
