"""Request and response models for sign-up, login, profile and password reset."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import UserRole
from app.schemas.fields import LoginId, Password, validate_password_strength

OTP_LENGTH = 6


class _StrictModel(BaseModel):
    """Reject unknown fields, so a typo or an injected field fails loudly."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SignupRequest(_StrictModel):
    login_id: LoginId
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=100)
    role: UserRole = UserRole.STAFF
    password: Password
    confirm_password: str

    _check_strength = field_validator("password")(validate_password_strength)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(_StrictModel):
    # No format rules here: a wrong login id must fail authentication, not validation,
    # otherwise the error reveals which field was wrong.
    login_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(_StrictModel):
    email: EmailStr


class VerifyOtpRequest(_StrictModel):
    email: EmailStr
    otp: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH, pattern=r"^\d{6}$")


class ResetTokenOut(BaseModel):
    reset_token: str


class ResetPasswordRequest(_StrictModel):
    reset_token: str = Field(min_length=1, max_length=2048)
    password: Password
    confirm_password: str

    _check_strength = field_validator("password")(validate_password_strength)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordRequest(_StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    password: Password
    confirm_password: str

    _check_strength = field_validator("password")(validate_password_strength)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ChangePasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UpdateProfileRequest(_StrictModel):
    full_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None


class UserOut(BaseModel):
    """A user as returned by the API. `password_hash` is deliberately absent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    email: str
    full_name: str | None
    role: UserRole
    created_at: datetime
