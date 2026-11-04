from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TransformMetadata(BaseModel):
    processed_asset: str
    regional_zone: str
    intervals_saved: int      # new readings stored by this request
    duplicates_ignored: int   # readings of this request whose meter and moment were already stored


class AnalyticsSummary(BaseModel):
    cumulative_kwh: float
    average_load_per_interval: float


class TransformResponse(BaseModel):
    message: str
    metadata: TransformMetadata
    analytics_summary: AnalyticsSummary


class ReadingOut(BaseModel):
    # An exact moment, always returned in UTC, whatever the database session's time zone is.
    timestamp: datetime
    kwh_value: float
    voltage: Optional[float]


class ReadingsResponse(BaseModel):
    meter_id: str
    count: int
    readings: List[ReadingOut]