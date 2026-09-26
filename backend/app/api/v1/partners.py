"""Vendors and customers."""

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, PageParams, PartnerServiceDep
from app.models.enums import PartnerType
from app.schemas.common import Page
from app.schemas.partner import PartnerCreate, PartnerOut, PartnerUpdate

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("", response_model=Page[PartnerOut])
def search_partners(
    user: CurrentUser,
    service: PartnerServiceDep,
    page: PageParams,
    q: str | None = Query(default=None, max_length=100),
    partner_type: PartnerType | None = Query(default=None, alias="type"),
) -> Page[PartnerOut]:
    """Search contacts. Filtering by type also returns partners marked as both."""
    partners, total = service.search(
        query=q, partner_type=partner_type, limit=page.page_size, offset=page.offset
    )
    return Page(items=partners, total=total, page=page.page, page_size=page.page_size)


@router.post("", response_model=PartnerOut, status_code=status.HTTP_201_CREATED)
def create_partner(
    body: PartnerCreate, user: CurrentUser, service: PartnerServiceDep
) -> PartnerOut:
    """Create a contact, including inline from a receipt or delivery form."""
    return service.create(body)


@router.get("/{partner_id}", response_model=PartnerOut)
def get_partner(partner_id: int, user: CurrentUser, service: PartnerServiceDep) -> PartnerOut:
    return service.get(partner_id)


@router.patch("/{partner_id}", response_model=PartnerOut)
def update_partner(
    partner_id: int, body: PartnerUpdate, user: CurrentUser, service: PartnerServiceDep
) -> PartnerOut:
    return service.update(partner_id, body)
