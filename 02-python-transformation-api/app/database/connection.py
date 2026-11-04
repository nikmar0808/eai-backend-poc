from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

DATABASE_URL = os.environ["DATABASE_URL"]   # KeyError at start-up if absent (fail fast)

# Production-ready connection pooling engine
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """The parent of every table class. A real class, which mypy can follow; declarative_base() was not."""


def get_db_session():
    """Injects thread-isolated database sessions into API routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()