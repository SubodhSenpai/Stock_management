"""Queries over users, password-reset codes and refresh tokens.

No business rules and no commits: services decide what happens and when it is saved.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.user import PasswordResetOtp, RefreshToken, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_login_id(self, login_id: str) -> User | None:
        stmt = select(User).where(func.lower(User.login_id) == login_id.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()

    def login_id_exists(self, login_id: str) -> bool:
        stmt = select(User.id).where(func.lower(User.login_id) == login_id.lower())
        return self.db.execute(stmt).first() is not None

    def email_exists(self, email: str, *, exclude_user_id: int | None = None) -> bool:
        stmt = select(User.id).where(User.email == email.lower())
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        return self.db.execute(stmt).first() is not None

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user


class OtpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, otp: PasswordResetOtp) -> PasswordResetOtp:
        self.db.add(otp)
        self.db.flush()
        return otp

    def get_active(self, user_id: int) -> PasswordResetOtp | None:
        """The user's one live code, if any (a partial unique index guarantees at most one)."""
        stmt = select(PasswordResetOtp).where(
            PasswordResetOtp.user_id == user_id,
            PasswordResetOtp.consumed_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def consume_active(self, user_id: int) -> None:
        """Mark any live code as used, so a fresh one can be issued."""
        otp = self.get_active(user_id)
        if otp is not None:
            otp.consumed_at = datetime.now(UTC)
            self.db.flush()


class RefreshTokenRepository:
    """Refresh tokens are looked up by hash; the raw value is never stored."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.execute(stmt).scalar_one_or_none()

    def revoke(self, token: RefreshToken) -> None:
        if token.revoked_at is None:
            token.revoked_at = datetime.now(UTC)
            self.db.flush()

    def revoke_all_for_user(self, user_id: int) -> int:
        """Sign every session out. Used when a token appears to have been copied."""
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.db.flush()
        return result.rowcount

    def delete_expired(self) -> int:
        """Housekeeping: drop tokens that can no longer be used."""
        result = self.db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        )
        self.db.flush()
        return result.rowcount
