"""Typed application errors.

Services raise these; `error_handlers` turns each one into the standard JSON error body.
The HTTP status lives here, so services never need to know about HTTP.
"""

from typing import Any


class AppError(Exception):
    """Base class for expected, user-facing errors."""

    status_code: int = 400
    code: str = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        details: list[dict[str, Any]] | None = None,
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class DuplicateError(AppError):
    status_code = 409
    code = "DUPLICATE"


class InvalidTransitionError(AppError):
    status_code = 409
    code = "INVALID_TRANSITION"


class InsufficientStockError(AppError):
    status_code = 409
    code = "INSUFFICIENT_STOCK"


class InUseError(AppError):
    status_code = 409
    code = "IN_USE"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE"


class AuthenticationError(AppError):
    status_code = 401
    code = "NOT_AUTHENTICATED"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class RateLimitedError(AppError):
    status_code = 429
    code = "TOO_MANY_REQUESTS"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class OtpError(AppError):
    """Invalid, expired or exhausted password-reset code."""

    status_code = 400
    code = "OTP_INVALID"
