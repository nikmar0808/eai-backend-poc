from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TransformMetadata(BaseModel):
    processed_asset: str
    regional_zone: str
    intervals_saved: int


class AnalyticsSummary(BaseModel):
    cumulative_kwh: float
    average_load_per_interval: float


class TransformResponse(BaseModel):
    message: str
    metadata: TransformMetadata
    analytics_summary: AnalyticsSummary


class ReadingOut(BaseModel):
    # Stored values are naive local date-times and are returned without an offset (finding D14, contract note).
    timestamp: datetime
    kwh_value: float
    voltage: Optional[float]


class ReadingsResponse(BaseModel):
    meter_id: str
    count: int
    readings: List[ReadingOut]