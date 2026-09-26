"""Shared test fixtures.

The suite runs against a real PostgreSQL database, because the rules being tested live in
the database: check constraints, partial unique indexes and the append-only ledger trigger.
The schema is built by running the real migrations, so the tests also prove the migrations work.

Each test runs inside a transaction that is rolled back afterwards, so tests stay isolated
even though the services under test call `commit()`.
"""

from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.api.deps import get_db
from app.core.config import get_settings
from app.main import create_app

pytest_plugins = ["tests.qa_report"]


def _test_database_url() -> str:
    settings = get_settings()
    if not settings.test_database_url:
        pytest.fail("TEST_DATABASE_URL is not set; see backend/.env.example")
    return settings.test_database_url


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Rebuild the test schema from the migrations, once per test session."""
    url = _test_database_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_config, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose work is always rolled back.

    `join_transaction_mode="create_savepoint"` turns the service's `commit()` into a
    savepoint release, so the outer transaction can still be discarded.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """An API client that shares the test's rolled-back session."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
