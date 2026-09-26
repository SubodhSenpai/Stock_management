"""Users and password-reset codes."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, TimestampMixin, pg_enum
from app.models.enums import UserRole


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("login_id ~ '^[A-Za-z0-9_.]{6,12}$'", name="login_id_format"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        UniqueConstraint("email"),
        Index("ux_users_login_id_lower", text("lower(login_id)"), unique=True),
    )

    login_id: Mapped[str] = mapped_column(String(12))
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), default=UserRole.STAFF, server_default=UserRole.STAFF.value
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class PasswordResetOtp(IdMixin, CreatedAtMixin, Base):
    """A one-time reset code. Only its HMAC is stored; at most one unconsumed code per user."""

    __tablename__ = "password_reset_otps"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_password_reset_otps_user_id_created_at", "user_id", "created_at"),
        Index(
            "ux_password_reset_otps_one_active",
            "user_id",
            unique=True,
            postgresql_where=text("consumed_at IS NULL"),
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    otp_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
