import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# These two lines run before any test module imports the application, which reads them at import time.
# 1. Tracing is optional and must never be switched on by a developer's shell during a test run.
os.environ.pop("APPLICATIONINSIGHTS_CONNECTION_STRING", None)
# 2. The service refuses to start without a token; a test value is supplied if the shell has none.
os.environ.setdefault("API_SECURITY_TOKEN", "test-token")


def pytest_sessionstart(session: pytest.Session) -> None:
    """Refuse to run against a database that is not clearly a test database."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.exit("DATABASE_URL is not set. Point it at a test database, for example .../smart_meter_test.", returncode=3)
    database = make_url(url).database or ""
    if not (database.endswith("_test") or os.environ.get("CI") == "true"):
        pytest.exit(
            f"Refusing to run: database '{database}' does not end in '_test' and CI is not set. "
            "Create a test database and point DATABASE_URL at it.",
            returncode=3,
        )


@pytest.fixture(scope="session")
def engine():
    """The application's own engine, with the tables created once (idempotent)."""
    from app.database import models  # noqa: F401  (importing registers the tables on Base)
    from app.database.connection import Base, engine as app_engine

    Base.metadata.create_all(bind=app_engine)
    yield app_engine
    app_engine.dispose()


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    """A session whose work is never committed.

    The session joins an outer transaction that is rolled back at the end of the test. The 'create_savepoint' mode
    makes the route's commit() release a savepoint and its rollback() roll back to one, so the code under test behaves
    exactly as in production while the outer transaction still discards everything.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """The application in memory (ASGI), using the rolling-back session in place of the real one."""
    from app.database.connection import get_db_session
    from app.main import app

    app.dependency_overrides[get_db_session] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    from app.config import settings

    return {"X-EAI-TOKEN": settings.API_SECURITY_TOKEN}
