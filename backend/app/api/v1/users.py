"""The signed-in user's own profile."""

from fastapi import APIRouter

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import ChangePasswordRequest, UpdateProfileRequest, UserOut
from app.schemas.common import MessageOut

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_my_profile(
    body: UpdateProfileRequest, user: CurrentUser, service: AuthServiceDep
) -> UserOut:
    return UserOut.model_validate(service.update_profile(user, body))


@router.post("/me/password", response_model=MessageOut)
def change_my_password(
    body: ChangePasswordRequest, user: CurrentUser, service: AuthServiceDep
) -> MessageOut:
    service.change_password(user, body)
    return MessageOut(message="Your password has been changed.")
