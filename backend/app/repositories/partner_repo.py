"""Queries over vendors and customers."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import PartnerType
from app.models.partner import Partner


class PartnerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, partner_id: int) -> Partner | None:
        return self.db.get(Partner, partner_id)

    def add(self, partner: Partner) -> Partner:
        self.db.add(partner)
        self.db.flush()
        return partner

    def name_exists(self, name: str) -> bool:
        stmt = select(Partner.id).where(func.lower(Partner.name) == name.lower())
        return self.db.execute(stmt).first() is not None

    def search(
        self,
        *,
        query: str | None = None,
        partner_type: PartnerType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Partner], int]:
        stmt = select(Partner)
        count_stmt = select(func.count()).select_from(Partner)

        filters = []
        if query:
            filters.append(Partner.name.ilike(f"%{query}%"))
        if partner_type is not None:
            # A partner marked "both" can act as either a vendor or a customer.
            filters.append(Partner.type.in_([partner_type, PartnerType.BOTH]))

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.db.execute(count_stmt).scalar_one()
        rows = self.db.execute(stmt.order_by(Partner.name).limit(limit).offset(offset)).scalars()
        return list(rows), total

    def can_act_as(self, partner: Partner, required: PartnerType) -> bool:
        return partner.type in (required, PartnerType.BOTH)
