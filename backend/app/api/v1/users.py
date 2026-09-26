"""The signed-in user's own profile and sessions.

Everything here is scoped to the caller. There is no way to read or change another user's
profile, so the id is never taken from the request.
"""

from fastapi import APIRouter

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import ChangePasswordRequest, UpdateProfileRequest, UserOut
from app.schemas.common import MessageOut

router = APIRouter(prefix="/users", tags=["profile"])


@router.get("/me", response_model=UserOut)
def read_my_profile(user: CurrentUser) -> UserOut:
    """The signed-in user's profile. Never includes the password hash."""
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_my_profile(
    body: UpdateProfileRequest, user: CurrentUser, service: AuthServiceDep
) -> UserOut:
    """Update the display name or email address."""
    return UserOut.model_validate(service.update_profile(user, body))


@router.post("/me/password", response_model=MessageOut)
def change_my_password(
    body: ChangePasswordRequest, user: CurrentUser, service: AuthServiceDep
) -> MessageOut:
    """Change the password, proving the current one first.

    Every other session is signed out, since a password change usually means the old one
    is no longer trusted.
    """
    service.change_password(user, body)
    return MessageOut(message="Your password has been changed. Other sessions were signed out.")
