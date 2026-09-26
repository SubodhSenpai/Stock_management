"""Sign-up, login and the OTP password-reset flow.

Security decisions worth knowing:
* Login failures never say whether it was the id or the password that was wrong.
* "Forgot password" returns the same answer whether or not the email exists, so the
  endpoint cannot be used to discover who has an account.
* Reset codes are stored as an HMAC, never in plain text, and each one expires, has a
  limited number of attempts and can be used once.
* Refresh tokens rotate on every use. Presenting one that was already used means the
  token was copied, so every session for that user is revoked.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    DuplicateError,
    OtpError,
)
from app.core.security import hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    create_reset_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_refresh_token,
)
from app.core.tokens import token_subject as subject_from_token
from app.core.tokens import verify_otp as otp_matches
from app.models.user import PasswordResetOtp, RefreshToken, User
from app.repositories.user_repo import (
    OtpRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.schemas.auth import ChangePasswordRequest, SignupRequest, UpdateProfileRequest
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS_MESSAGE = "Invalid Login Id or Password"
INVALID_OTP_MESSAGE = "That code is not valid. Please check it and try again."


class AuthService:
    def __init__(
        self,
        db: Session,
        users: UserRepository,
        otps: OtpRepository,
        refresh_tokens: RefreshTokenRepository,
        email: EmailService,
        settings: Settings,
    ) -> None:
        self.db = db
        self.users = users
        self.otps = otps
        self.refresh_tokens = refresh_tokens
        self.email = email
        self.settings = settings

    def sign_up(self, data: SignupRequest) -> User:
        """Create an account. Login id and email must be free (both compared case-insensitively)."""
        if self.users.login_id_exists(data.login_id):
            raise DuplicateError(
                "That login ID is already taken.",
                [{"field": "login_id", "message": "Already taken"}],
            )
        if self.users.email_exists(data.email):
            raise DuplicateError(
                "That email address is already registered.",
                [{"field": "email", "message": "Already registered"}],
            )

        user = User(
            login_id=data.login_id,
            email=data.email.lower(),
            full_name=data.full_name,
            role=data.role,
            password_hash=hash_password(data.password),
        )
        self.users.add(user)
        self.db.commit()
        logger.info("New account created: user_id=%s role=%s", user.id, user.role.value)
        return user

    def authenticate(self, login_id: str, password: str) -> User:
        """Return the user for valid credentials, or raise with a deliberately vague message."""
        user = self.users.get_by_login_id(login_id)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE, code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.", code="ACCOUNT_DISABLED")
        return user

    def issue_access_token(self, user: User) -> str:
        return create_access_token(user.id)

    def start_session(self, user: User, *, user_agent: str | None = None) -> tuple[str, str]:
        """Return a fresh (access token, refresh token) pair for a signed-in user."""
        refresh = generate_refresh_token()
        self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh),
                expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_expire_days),
                user_agent=(user_agent or "")[:200] or None,
            )
        )
        self.db.commit()
        return create_access_token(user.id), refresh

    def refresh_session(
        self, refresh_token: str, *, user_agent: str | None = None
    ) -> tuple[User, str, str]:
        """Exchange a refresh token for a new pair, retiring the one presented.

        Rotating on every use means a copied token is only good until the real client
        refreshes next. Seeing an already-used token is treated as theft: every session
        for that user is revoked, so both parties have to sign in again.
        """
        stored = self.refresh_tokens.get_by_hash(hash_refresh_token(refresh_token))
        if stored is None:
            raise AuthenticationError("Your session has expired. Please sign in again.")

        if stored.revoked_at is not None:
            revoked = self.refresh_tokens.revoke_all_for_user(stored.user_id)
            self.db.commit()
            logger.warning(
                "Reused refresh token for user_id=%s; revoked %d session(s)",
                stored.user_id,
                revoked,
            )
            raise AuthenticationError("Your session has expired. Please sign in again.")

        if stored.expires_at <= datetime.now(UTC):
            raise AuthenticationError("Your session has expired. Please sign in again.")

        user = self.users.get(stored.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Your session has expired. Please sign in again.")

        self.refresh_tokens.revoke(stored)
        access, refresh = self.start_session(user, user_agent=user_agent)
        return user, access, refresh

    def end_session(self, refresh_token: str | None) -> None:
        """Sign out. Missing or unknown tokens are ignored so logout always succeeds."""
        if not refresh_token:
            return
        stored = self.refresh_tokens.get_by_hash(hash_refresh_token(refresh_token))
        if stored is not None:
            self.refresh_tokens.revoke(stored)
            self.db.commit()

    def end_all_sessions(self, user: User) -> int:
        """Sign the user out everywhere, used after a password change."""
        count = self.refresh_tokens.revoke_all_for_user(user.id)
        self.db.commit()
        return count

    def request_password_reset(self, email: str) -> None:
        """Email a one-time code, if the address belongs to an active account.

        Returns without a sign of what happened in every case, including unknown addresses
        and codes requested too soon, so the caller learns nothing about who has an account.
        """
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("Password reset requested for an unknown address")
            return

        existing = self.otps.get_active(user.id)
        if existing is not None and self._within_resend_cooldown(existing):
            logger.info("Password reset re-requested during cooldown: user_id=%s", user.id)
            return

        self.otps.consume_active(user.id)
        code = generate_otp()
        self.otps.add(
            PasswordResetOtp(
                user_id=user.id,
                otp_hash=hash_otp(code),
                expires_at=datetime.now(UTC) + timedelta(minutes=self.settings.otp_expire_minutes),
            )
        )
        self.db.commit()

        self.email.send_password_reset_otp(user.email, code, self.settings.otp_expire_minutes)
        logger.info("Password reset code sent: user_id=%s", user.id)

    def verify_reset_otp(self, email: str, code: str) -> str:
        """Check a reset code and return a short-lived token that authorises the new password."""
        user = self.users.get_by_email(email)
        if user is None:
            raise OtpError(INVALID_OTP_MESSAGE)

        otp = self.otps.get_active(user.id)
        if otp is None:
            raise OtpError(INVALID_OTP_MESSAGE)

        if otp.expires_at <= datetime.now(UTC):
            self._consume(otp)
            raise OtpError("That code has expired. Please request a new one.", code="OTP_EXPIRED")

        if otp.attempts >= self.settings.otp_max_attempts:
            self._consume(otp)
            raise OtpError(
                "Too many incorrect attempts. Please request a new code.", code="OTP_EXPIRED"
            )

        otp.attempts += 1
        if not otp_matches(code, otp.otp_hash):
            self.db.commit()
            raise OtpError(INVALID_OTP_MESSAGE)

        self.db.commit()
        return create_reset_token(user.id)

    def reset_password(self, reset_token: str, new_password: str) -> None:
        """Set a new password using a token from `verify_reset_otp`, then burn the code."""
        user_id = subject_from_token(reset_token, "reset")
        user = self.users.get(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Your session is invalid or has expired.")

        user.password_hash = hash_password(new_password)
        self.otps.consume_active(user.id)
        self.refresh_tokens.revoke_all_for_user(user.id)
        self.db.commit()
        logger.info("Password reset completed: user_id=%s", user.id)

    def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.password_hash):
            raise AuthenticationError(
                "Your current password is incorrect.",
                code="INVALID_CREDENTIALS",
            )
        user.password_hash = hash_password(data.password)
        # Any other session is now suspect, so force a fresh sign-in everywhere.
        self.refresh_tokens.revoke_all_for_user(user.id)
        self.db.commit()
        logger.info("Password changed: user_id=%s", user.id)

    def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        if data.email is not None and self.users.email_exists(data.email, exclude_user_id=user.id):
            raise DuplicateError(
                "That email address is already registered.",
                [{"field": "email", "message": "Already registered"}],
            )
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.email is not None:
            user.email = data.email.lower()
        self.db.commit()
        return user

    def _within_resend_cooldown(self, otp: PasswordResetOtp) -> bool:
        cooldown = timedelta(seconds=self.settings.otp_resend_cooldown_seconds)
        return datetime.now(UTC) - otp.created_at < cooldown

    def _consume(self, otp: PasswordResetOtp) -> None:
        otp.consumed_at = datetime.now(UTC)
        self.db.commit()
