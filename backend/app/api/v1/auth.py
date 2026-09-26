"""Authentication: sign up, sign in, refresh, sign out and the OTP password reset.

Sessions use two cookies. The access token is short-lived and sent with every request; the
refresh token is long-lived, revocable, and only ever sent to the refresh endpoint. Both are
httpOnly, so no script on the page can read either one.
"""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AppSettings, AuthServiceDep, CurrentUser
from app.core.config import Settings
from app.core.exceptions import AuthenticationError
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

# The refresh cookie is scoped to this path, so it is not attached to ordinary API calls.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _client_key(request: Request, identifier: str) -> str:
    """Rate-limit key: the caller's address plus who they are trying to be."""
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{identifier.lower()}"


def _set_session_cookies(
    response: Response, access_token: str, refresh_token: str, settings: Settings
) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_expire_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path=REFRESH_COOKIE_PATH)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def sign_up(
    body: SignupRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: AppSettings,
) -> UserOut:
    """Create an account and sign the new user in."""
    user = service.sign_up(body)
    access, refresh = service.start_session(user, user_agent=request.headers.get("user-agent"))
    _set_session_cookies(response, access, refresh, settings)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def log_in(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: AppSettings,
) -> UserOut:
    """Exchange credentials for a session. Throttled to slow down guessing."""
    key = _client_key(request, body.login_id)
    login_limiter.check(key)

    user = service.authenticate(body.login_id, body.password)
    login_limiter.reset(key)

    access, refresh = service.start_session(user, user_agent=request.headers.get("user-agent"))
    _set_session_cookies(response, access, refresh, settings)
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=UserOut)
def refresh_session(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: AppSettings,
) -> UserOut:
    """Issue a new access token, and rotate the refresh token that produced it.

    Returns 401 if the token is unknown, expired, revoked, or has already been used.
    """
    presented = request.cookies.get(settings.refresh_cookie_name)
    if not presented:
        _clear_session_cookies(response, settings)
        raise AuthenticationError("Your session has expired. Please sign in again.")

    user, access, refresh = service.refresh_session(
        presented, user_agent=request.headers.get("user-agent")
    )
    _set_session_cookies(response, access, refresh, settings)
    return UserOut.model_validate(user)


@router.post("/logout", response_model=MessageOut)
def log_out(
    request: Request, response: Response, service: AuthServiceDep, settings: AppSettings
) -> MessageOut:
    """Sign out, revoking the refresh token so it cannot be replayed."""
    service.end_session(request.cookies.get(settings.refresh_cookie_name))
    _clear_session_cookies(response, settings)
    return MessageOut(message="Signed out.")


@router.post("/logout-all", response_model=MessageOut)
def log_out_everywhere(
    response: Response, user: CurrentUser, service: AuthServiceDep, settings: AppSettings
) -> MessageOut:
    """Sign out of every device, for when an account may have been compromised."""
    count = service.end_all_sessions(user)
    _clear_session_cookies(response, settings)
    return MessageOut(message=f"Signed out of {count} session(s).")


@router.get("/me", response_model=UserOut)
def read_current_user(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordRequest, request: Request, service: AuthServiceDep, settings: AppSettings
) -> MessageOut:
    """Start a password reset by emailing a one-time code."""
    otp_request_limiter.check(_client_key(request, body.email))
    code = service.request_password_reset(body.email)
    msg = RESET_REQUEST_REPLY
    if settings.env == "dev" and code:
        msg = f"{RESET_REQUEST_REPLY} (Dev Mode OTP: {code})"
    return MessageOut(message=msg)


@router.post("/verify-otp", response_model=ResetTokenOut)
def verify_otp(body: VerifyOtpRequest, service: AuthServiceDep) -> ResetTokenOut:
    """Exchange a valid code for a short-lived token that authorises the new password."""
    return ResetTokenOut(reset_token=service.verify_reset_otp(body.email, body.otp))


@router.post("/reset-password", response_model=MessageOut)
def reset_password(
    body: ResetPasswordRequest, response: Response, service: AuthServiceDep, settings: AppSettings
) -> MessageOut:
    """Set a new password. Every existing session is signed out."""
    service.reset_password(body.reset_token, body.password)
    _clear_session_cookies(response, settings)
    return MessageOut(message="Your password has been changed. Please sign in.")
