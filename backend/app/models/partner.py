"""Vendors and customers (the "contact" on receipts and deliveries)."""

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, pg_enum
from app.models.enums import PartnerType


class Partner(IdMixin, TimestampMixin, Base):
    __tablename__ = "partners"
    __table_args__ = (
        Index(
            "ix_partners_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[PartnerType] = mapped_column(pg_enum(PartnerType, "partner_type"))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
