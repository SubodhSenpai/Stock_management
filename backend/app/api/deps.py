"""FastAPI dependencies: settings, database session, service wiring, authentication and roles."""

from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.events import EventBus, event_bus
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.tokens import token_subject
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.catalog_repo import (
    CategoryRepository,
    ProductRepository,
    ReorderRuleRepository,
    UomRepository,
)
from app.repositories.dashboard_repo import DashboardRepository
from app.repositories.operation_repo import OperationRepository
from app.repositories.partner_repo import PartnerRepository
from app.repositories.stock_repo import MoveRepository, OperationLineRepository, QuantRepository
from app.repositories.user_repo import (
    OtpRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.repositories.warehouse_repo import LocationRepository, WarehouseRepository
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService
from app.services.email_service import EmailService
from app.services.operation_service import OperationService
from app.services.partner_service import PartnerService
from app.services.product_service import ProductService
from app.services.stock_query_service import StockQueryService
from app.services.stock_service import StockService
from app.services.warehouse_service import WarehouseService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_event_bus() -> EventBus:
    return event_bus


EventBusDep = Annotated[EventBus, Depends(get_event_bus)]


class Pagination:
    """Shared page/page_size query parameters, with an offset ready for the repositories."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


PageParams = Annotated[Pagination, Depends(Pagination)]


# ---------- authentication ----------


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    """Resolve the signed-in user from the httpOnly session cookie.

    The cookie is read server-side only, so a script on the page can never reach the token.
    """
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise AuthenticationError("Please log in to continue.")

    user = UserRepository(db).get(token_subject(token, "access"))
    if user is None or not user.is_active:
        raise AuthenticationError("Please log in to continue.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """Allow only the given roles. The UI hides forbidden actions; this enforces them."""

    def check_role(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("You do not have permission to do this.")
        return user

    return check_role


RequireManager = Annotated[User, Depends(require_role(UserRole.MANAGER))]


# ---------- services ----------


def get_auth_service(db: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(
        db=db,
        users=UserRepository(db),
        otps=OtpRepository(db),
        refresh_tokens=RefreshTokenRepository(db),
        email=EmailService(settings),
        settings=settings,
    )


def get_warehouse_service(db: DbSession) -> WarehouseService:
    return WarehouseService(db, WarehouseRepository(db), LocationRepository(db))


def get_product_service(db: DbSession) -> ProductService:
    return ProductService(
        db,
        ProductRepository(db),
        CategoryRepository(db),
        UomRepository(db),
        ReorderRuleRepository(db),
    )


def get_partner_service(db: DbSession) -> PartnerService:
    return PartnerService(db, PartnerRepository(db))


def get_stock_service(db: DbSession) -> StockService:
    return StockService(db, QuantRepository(db), MoveRepository(db), LocationRepository(db))


def get_operation_service(
    db: DbSession,
    stock: Annotated[StockService, Depends(get_stock_service)],
    bus: EventBusDep,
) -> OperationService:
    return OperationService(
        db=db,
        operations=OperationRepository(db),
        lines=OperationLineRepository(db),
        locations=LocationRepository(db),
        warehouses=WarehouseRepository(db),
        products=ProductRepository(db),
        partners=PartnerRepository(db),
        stock=stock,
        event_bus=bus,
    )


def get_stock_query_service(db: DbSession) -> StockQueryService:
    return StockQueryService(QuantRepository(db), MoveRepository(db))


def get_dashboard_service(db: DbSession) -> DashboardService:
    return DashboardService(DashboardRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
WarehouseServiceDep = Annotated[WarehouseService, Depends(get_warehouse_service)]
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
PartnerServiceDep = Annotated[PartnerService, Depends(get_partner_service)]
OperationServiceDep = Annotated[OperationService, Depends(get_operation_service)]
StockQueryServiceDep = Annotated[StockQueryService, Depends(get_stock_query_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
