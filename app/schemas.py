from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import BehaviorCategory, VerificationStatus


class ReporterCreate(BaseModel):
    social_graph_verified: bool = False


class ReporterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reputation_score: float
    social_graph_verified: bool
    created_at: datetime


class ReportCreate(BaseModel):
    reporter_id: UUID
    target_license_plate: str = Field(min_length=3, max_length=64)
    behavior_category: BehaviorCategory
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    reporter_latitude: float = Field(ge=-90.0, le=90.0)
    reporter_longitude: float = Field(ge=-180.0, le=180.0)
    timestamp: datetime
    media_url: str | None = Field(default=None, max_length=2048)

    @field_validator("target_license_plate")
    @classmethod
    def normalize_plate(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("timestamp must include timezone information")
        return value


class ReportResponse(BaseModel):
    id: UUID
    verification_status: VerificationStatus


class ReportDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reporter_id: UUID
    target_license_plate: str
    behavior_category: BehaviorCategory
    latitude: float
    longitude: float
    timestamp: datetime
    media_url: str | None
    verification_status: VerificationStatus


class RiskProfileResponse(BaseModel):
    risk_score: float
    confidence_interval: float
    top_risk_factors: list[str]


class MediaPresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100, pattern=r"^[\w.+-]+\/[\w.+-]+$")


class MediaPresignResponse(BaseModel):
    upload_url: str
    object_key: str


class MediaUploadResponse(BaseModel):
    media_url: str
    object_key: str


class MediaAutoFillResponse(BaseModel):
    detected_license_plate: str | None
    detected_latitude: float | None
    detected_longitude: float | None
    detected_timestamp: datetime | None
