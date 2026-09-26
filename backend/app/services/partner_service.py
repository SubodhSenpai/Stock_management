"""Vendors and customers."""

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateError, NotFoundError
from app.models.enums import PartnerType
from app.models.partner import Partner
from app.repositories.partner_repo import PartnerRepository
from app.schemas.partner import PartnerCreate, PartnerUpdate


class PartnerService:
    def __init__(self, db: Session, partners: PartnerRepository) -> None:
        self.db = db
        self.partners = partners

    def search(
        self,
        *,
        query: str | None = None,
        partner_type: PartnerType | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Partner], int]:
        return self.partners.search(
            query=query, partner_type=partner_type, limit=limit, offset=offset
        )

    def get(self, partner_id: int) -> Partner:
        partner = self.partners.get(partner_id)
        if partner is None:
            raise NotFoundError("That contact does not exist.")
        return partner

    def create(self, data: PartnerCreate) -> Partner:
        if self.partners.name_exists(data.name):
            raise DuplicateError(
                f"A contact named {data.name} already exists.",
                [{"field": "name", "message": "Already exists"}],
            )
        partner = self.partners.add(
            Partner(
                name=data.name,
                type=data.type,
                email=data.email.lower() if data.email else None,
                phone=data.phone,
                address=data.address,
            )
        )
        self.db.commit()
        return partner

    def update(self, partner_id: int, data: PartnerUpdate) -> Partner:
        partner = self.get(partner_id)
        for field in ("name", "type", "phone", "address"):
            value = getattr(data, field)
            if value is not None:
                setattr(partner, field, value)
        if data.email is not None:
            partner.email = data.email.lower()
        self.db.commit()
        return partner
