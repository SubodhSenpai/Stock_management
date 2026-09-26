"""Application entry point: `uvicorn app.main:app --reload`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.events import event_bus
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.schemas.common import ErrorOut

DESCRIPTION = """
StockSense is an inventory management API.

Every stock change is recorded as a move between two locations, so receipts, deliveries,
internal transfers and adjustments share one engine and one audit trail.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Give the event bus the running loop so synchronous services can broadcast changes."""
    event_bus.bind_loop(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan,
        responses={
            400: {"model": ErrorOut},
            401: {"model": ErrorOut},
            403: {"model": ErrorOut},
            404: {"model": ErrorOut},
            409: {"model": ErrorOut},
            422: {"model": ErrorOut},
        },
    )

    # Middleware runs bottom-up, so the request id is set before anything else uses it.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
