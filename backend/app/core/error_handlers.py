"""Map every error to one JSON shape.

{"error": {"code": str, "message": str,
           "details": [{"field": str, "message": str}], "request_id": str}}
"""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

_REQUEST_PARTS = {"body", "query", "path", "header", "cookie"}
_HTTP_ERROR_CODES = {
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": getattr(request.state, "request_id", None),
        }
    }
    return JSONResponse(status_code=status_code, content=body)


def field_path(location: Sequence[str | int]) -> str:
    """Turn a Pydantic location into a form path: ('body','lines',0,'qty') -> 'lines[0].qty'."""
    parts = location[1:] if location and location[0] in _REQUEST_PARTS else location
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": field_path(err["loc"]), "message": err["msg"].removeprefix("Value error, ")}
        for err in exc.errors()
    ]
    return error_response(request, 422, "VALIDATION_ERROR", "Some fields are invalid.", details)


async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    return error_response(request, exc.status_code, code, str(exc.detail))


async def _handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    # Services check business rules first; reaching here means a race the DB constraint caught.
    logger.warning("Integrity constraint violated: %s", exc.orig)
    return error_response(request, 409, "CONFLICT", "The change conflicts with existing data.")


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(request, 500, "INTERNAL_ERROR", "Something went wrong. Please try again.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(IntegrityError, _handle_integrity_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
