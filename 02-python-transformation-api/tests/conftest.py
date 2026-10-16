import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient      # runs the FastAPI app in memory through ASGI (A5)
from sqlalchemy.engine import make_url         # parses a database URL so its database NAME can be read
from sqlalchemy.orm import Session             # the unit of work that the routes use

# ---- Environment adjustments. These run when pytest loads this file, BEFORE any test module imports the
# ---- application, which reads the environment at import time (A6).
# 1. Tracing is optional and must never be switched on by a developer's shell during a test run.
os.environ.pop("APPLICATIONINSIGHTS_CONNECTION_STRING", None)
# 2. The service refuses to start without a token (config.py has no default); supply one if the shell has none.
#    setdefault leaves a value that is already set untouched.
os.environ.setdefault("API_SECURITY_TOKEN", "test-token")


def pytest_sessionstart(session: pytest.Session) -> None:
    """A pytest HOOK: a function with this exact name is called once, before collection starts.

    Refuse to run against a database that is not clearly a test database (A5, "the guard")."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.exit("DATABASE_URL is not set. Point it at a test database, for example .../smart_meter_test.", returncode=3)
    database = make_url(url).database or ""
    # The name must end in _test, OR the run is on GitHub's disposable runner (which sets CI=true).
    if not (database.endswith("_test") or os.environ.get("CI") == "true"):
        pytest.exit(
            f"Refusing to run: database '{database}' does not end in '_test' and CI is not set. "
            "Create a test database and point DATABASE_URL at it.",
            returncode=3,
        )


@pytest.fixture(scope="session")      # built ONCE per test run: the engine holds no per-test state
def engine():
    """The application's own engine, with the tables created once (idempotent)."""
    # Imports are INSIDE the function on purpose (A6): the application is imported only when a test needs it.
    from app.database import models  # noqa: F401  (importing registers the table classes on Base)
    from app.database.connection import Base, engine as app_engine

    Base.metadata.create_all(bind=app_engine)   # creates the table if absent; does nothing if present
    yield app_engine                            # everything before yield = set-up; everything after = tear-down
    app_engine.dispose()                        # close the pool at the end of the run


@pytest.fixture()                     # default scope: a fresh session for EVERY test
def db_session(engine) -> Iterator[Session]:    # "engine" as a parameter: pytest builds that fixture first
    """A session whose work is never committed (the isolation design of A5).

    The session joins an outer transaction that is rolled back at the end of the test. The 'create_savepoint' mode
    makes the route's commit() release a savepoint and its rollback() roll back to one, so the code under test behaves
    exactly as in production while the outer transaction still discards everything.
    """
    connection = engine.connect()                # one connection for the whole test
    outer = connection.begin()                   # the OUTER transaction: nothing may ever commit it
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session                            # the test (and the route it calls) use this session
    finally:                                     # runs whether the test passed or failed
        session.close()
        outer.rollback()                         # discard every row the test wrote
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """The application in memory (ASGI), using the rolling-back session in place of the real one."""
    from app.database.connection import get_db_session
    from app.main import app

    # "When a route asks for get_db_session, call this lambda instead." The lambda returns the test's own session,
    # so the route and the test share one view of the data.
    app.dependency_overrides[get_db_session] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()         # never leave an override behind for the next test


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """The header that authenticates a request, built from the same setting the application checks against."""
    from app.config import settings

    return {"X-EAI-TOKEN": settings.API_SECURITY_TOKEN}
