"""Liveness and readiness check."""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.core.exceptions import ServiceUnavailableError

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    """Report that the API is up and can reach the database."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError("The database is not reachable.") from exc
    return {"status": "ok", "database": "ok"}
