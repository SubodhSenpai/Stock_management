"""Product catalog: categories, units of measure, products and reordering rules."""

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, QUANTITY, Base, CreatedAtMixin, IdMixin, TimestampMixin


class ProductCategory(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "product_categories"
    __table_args__ = (Index("ux_product_categories_name_lower", text("lower(name)"), unique=True),)

    name: Mapped[str] = mapped_column(String(80))


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(SmallInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(40))
    # False for countable units: you can't receive 2.5 chairs.
    allow_fraction: Mapped[bool] = mapped_column(default=False, server_default=false())


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("sku ~ '^[A-Z0-9][A-Z0-9-]{1,31}$'", name="sku_format"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        UniqueConstraint("sku"),
        # Trigram indexes let the search box use ILIKE '%term%' without a full table scan.
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_products_sku_trgm",
            "sku",
            postgresql_using="gin",
            postgresql_ops={"sku": "gin_trgm_ops"},
        ),
    )

    sku: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(150))
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_categories.id", ondelete="RESTRICT"), index=True
    )
    uom_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT")
    )
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0), server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    category: Mapped[ProductCategory] = relationship()
    uom: Mapped[UnitOfMeasure] = relationship()


class ReorderRule(IdMixin, TimestampMixin, Base):
    """Keep a product between min and max in one warehouse; below min it is 'low stock'."""

    __tablename__ = "reorder_rules"
    __table_args__ = (
        CheckConstraint("min_quantity >= 0", name="min_non_negative"),
        CheckConstraint("max_quantity >= min_quantity", name="max_gte_min"),
        UniqueConstraint("product_id", "warehouse_id"),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE")
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True
    )
    min_quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    max_quantity: Mapped[Decimal] = mapped_column(QUANTITY)

    product: Mapped[Product] = relationship()
