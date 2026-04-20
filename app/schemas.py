from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import BehaviorCategory, VerificationStatus


class ReporterCreate(BaseModel):
    social_graph_verified: bool = False


class ReporterResponse(BaseModel):
    id: UUID
    reputation_score: float
    social_graph_verified: bool
    created_at: datetime


class ReportCreate(BaseModel):
    reporter_id: UUID
    target_license_plate: str = Field(min_length=3, max_length=64)
    behavior_category: BehaviorCategory
    latitude: float
    longitude: float
    reporter_latitude: float
    reporter_longitude: float
    timestamp: datetime
    media_url: str | None = None


class ReportResponse(BaseModel):
    id: UUID
    verification_status: VerificationStatus


class RiskProfileResponse(BaseModel):
    risk_score: float
    confidence_interval: float
    top_risk_factors: list[str]


class MediaPresignRequest(BaseModel):
    filename: str
    content_type: str


class MediaPresignResponse(BaseModel):
    upload_url: str
    object_key: str


class MediaAutoFillResponse(BaseModel):
    detected_license_plate: str | None
    detected_latitude: float | None
    detected_longitude: float | None
    detected_timestamp: datetime | None
