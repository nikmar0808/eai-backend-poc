from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base

READING_KEY = "smart_meter_intervals_meter_time_uk"


class SmartMeterIntervalRecord(Base):
    """One reading. Alembic builds this table (migrations/); this class must match it, which `alembic check` proves.

    Mapped[...] gives each attribute its Python type, which mypy can check: Mapped[float | None] may be None, and
    Mapped[datetime] may not. mapped_column(...) gives the column's database type and rules.
    """

    __tablename__ = "smart_meter_intervals"
    # One reading per meter per moment. Its index also serves the readings query (newest first, for one meter).
    __table_args__ = (UniqueConstraint("meter_id", "timestamp", name=READING_KEY),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(String(20))
    grid_zone: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))        # an exact moment: timestamptz
    kwh_value: Mapped[float] = mapped_column(Float)
    voltage: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKeyRecord(Base):
    """One client key: which request it was first used for, and the answer that request received."""

    __tablename__ = "idempotency_key"
    __table_args__ = (Index("idempotency_key_created_ix", "created_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())