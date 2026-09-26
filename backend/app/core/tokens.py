"""JWT access and reset tokens, plus one-time password (OTP) generation and hashing.

Two token purposes share one secret but never each other's audience: an access token
cannot be used to reset a password, and a reset token cannot call the API.
"""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

TokenPurpose = Literal["access", "reset"]

OTP_LENGTH = 6
RESET_TOKEN_MINUTES = 10
REFRESH_TOKEN_BYTES = 48


def _encode(subject: int, purpose: TokenPurpose, expires_in: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(user_id, "access", timedelta(minutes=settings.jwt_expire_minutes))


def create_reset_token(user_id: int) -> str:
    return _encode(user_id, "reset", timedelta(minutes=RESET_TOKEN_MINUTES))


def decode_token(token: str, expected_purpose: TokenPurpose) -> dict[str, Any]:
    """Return the payload, or raise AuthenticationError if invalid, expired or the wrong purpose."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Your session is invalid or has expired.") from exc

    if payload.get("purpose") != expected_purpose:
        raise AuthenticationError("Your session is invalid or has expired.")
    return payload


def token_subject(token: str, expected_purpose: TokenPurpose) -> int:
    payload = decode_token(token, expected_purpose)
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Your session is invalid or has expired.") from exc


def generate_otp() -> str:
    """A cryptographically random 6-digit code (leading zeros kept)."""
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(otp: str) -> str:
    """HMAC the code so a database leak never exposes usable reset codes."""
    settings = get_settings()
    return hmac.new(settings.otp_secret.encode(), otp.encode(), sha256).hexdigest()


def verify_otp(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), otp_hash)


def generate_refresh_token() -> str:
    """A random opaque token.

    Deliberately not a JWT: a refresh token must be revocable, and revoking a self-contained
    token means keeping a blocklist anyway. An opaque value looked up in the database is
    simpler and revocation is immediate.
    """
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Store only the hash, so a database leak cannot be used to resume sessions."""
    settings = get_settings()
    return hmac.new(settings.jwt_secret.encode(), token.encode(), sha256).hexdigest()
