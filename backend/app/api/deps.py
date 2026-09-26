"""FastAPI dependencies: settings, database session, service wiring, authentication and roles."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.tokens import token_subject
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repo import OtpRepository, UserRepository
from app.services.auth_service import AuthService
from app.services.email_service import EmailService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_auth_service(db: DbSession, settings: AppSettings) -> AuthService:
    return AuthService(
        db=db,
        users=UserRepository(db),
        otps=OtpRepository(db),
        email=EmailService(settings),
        settings=settings,
    )


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    """Resolve the signed-in user from the httpOnly session cookie.

    The cookie is read server-side only; JavaScript can never see the token, so an XSS bug
    cannot steal a session.
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
    """Allow only the given roles. The UI hides forbidden actions; this is what enforces them."""

    def check_role(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("You do not have permission to do this.")
        return user

    return check_role


RequireManager = Annotated[User, Depends(require_role(UserRole.MANAGER))]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
