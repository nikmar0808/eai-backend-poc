import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.authenticator import authenticate_request
from app.database.connection import get_db_session
from app.database.models import SmartMeterIntervalRecord
from app.schemas.responses import ReadingOut, ReadingsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Readings"])


@router.get("/meters/{meter_id}/readings", responses={401: {"description": "Missing or invalid X-EAI-TOKEN"}})
def get_recent_readings(
    meter_id: Annotated[str, Path(min_length=5, max_length=20, description="Meter identifier, 5 to 20 characters.")],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of readings to return.")] = 20,
    authenticated: str = Depends(authenticate_request),
    db: Session = Depends(get_db_session),
) -> ReadingsResponse:
    stmt = (
        select(SmartMeterIntervalRecord)
        .where(SmartMeterIntervalRecord.meter_id == meter_id)
        .order_by(SmartMeterIntervalRecord.timestamp.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return ReadingsResponse(
        meter_id=meter_id,
        count=len(rows),
        readings=[ReadingOut(timestamp=r.timestamp, kwh_value=r.kwh_value, voltage=r.voltage) for r in rows],
    )
