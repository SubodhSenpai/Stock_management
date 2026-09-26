"""Authentication endpoints: sign up, log in, log out and the OTP password reset."""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AppSettings, AuthServiceDep, CurrentUser
from app.core.config import Settings
from app.core.rate_limit import login_limiter, otp_request_limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    ResetTokenOut,
    SignupRequest,
    UserOut,
    VerifyOtpRequest,
)
from app.schemas.common import MessageOut

router = APIRouter(prefix="/auth", tags=["auth"])

# The same reply whether or not the address exists, so nobody can probe for accounts.
RESET_REQUEST_REPLY = "If that email is registered, a verification code has been sent."


def _client_key(request: Request, identifier: str) -> str:
    """Rate-limit key: the caller's address plus who they are trying to be."""
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{identifier.lower()}"


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def sign_up(
    body: SignupRequest,
    response: Response,
    service: AuthServiceDep,
    settings: AppSettings,
) -> UserOut:
    """Create an account and sign the new user in."""
    user = service.sign_up(body)
    _set_session_cookie(response, service.issue_access_token(user), settings)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def log_in(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: AppSettings,
) -> UserOut:
    """Exchange credentials for a session cookie. Throttled to slow down guessing."""
    key = _client_key(request, body.login_id)
    login_limiter.check(key)

    user = service.authenticate(body.login_id, body.password)
    login_limiter.reset(key)

    _set_session_cookie(response, service.issue_access_token(user), settings)
    return UserOut.model_validate(user)


@router.post("/logout", response_model=MessageOut)
def log_out(response: Response, settings: AppSettings) -> MessageOut:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return MessageOut(message="Signed out.")


@router.get("/me", response_model=UserOut)
def read_current_user(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    service: AuthServiceDep,
) -> MessageOut:
    """Start a password reset by emailing a one-time code."""
    otp_request_limiter.check(_client_key(request, body.email))
    service.request_password_reset(body.email)
    return MessageOut(message=RESET_REQUEST_REPLY)


@router.post("/verify-otp", response_model=ResetTokenOut)
def verify_otp(body: VerifyOtpRequest, service: AuthServiceDep) -> ResetTokenOut:
    """Exchange a valid code for a short-lived token that authorises the new password."""
    return ResetTokenOut(reset_token=service.verify_reset_otp(body.email, body.otp))


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordRequest, service: AuthServiceDep) -> MessageOut:
    service.reset_password(body.reset_token, body.password)
    return MessageOut(message="Your password has been changed. Please sign in.")
