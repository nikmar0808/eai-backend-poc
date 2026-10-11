import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
# for fixing mypy errors in legacy SQLAlchemy 2.0 style later in POC 3
# from sqlalchemy.orm import Mapped, mapped_column
from app.database.connection import Base


def _utc_now_naive() -> datetime.datetime:
    """Current UTC time without tzinfo: the same value utcnow() returned, without the deprecated call (finding D14)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class SmartMeterIntervalRecord(Base):
    """Relational schema map representing the persistent system of record."""

    __tablename__ = "smart_meter_intervals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    meter_id = Column(String(20), index=True, nullable=False)
    grid_zone = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    kwh_value = Column(Float, nullable=False)
    voltage = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utc_now_naive)
    # for fixing mypy errors in legacy SQLAlchemy 2.0 style later in POC 3
    # id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    # meter_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    # grid_zone: Mapped[str] = mapped_column(String(50), nullable=False)
    # timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    # kwh_value: Mapped[float] = mapped_column(Float, nullable=False)
    # voltage: Mapped[float] = mapped_column(Float, nullable=True)
    # created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_utc_now_naive)
