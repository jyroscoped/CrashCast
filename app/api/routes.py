import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_admin
from app.db.models import DriverRiskProfiles, Reports, Users, VerificationStatus
from app.db.session import get_db
from app.schemas import (
    MediaPresignRequest,
    MediaPresignResponse,
    MediaUploadResponse,
    ReportCreate,
    ReportDetailResponse,
    ReportResponse,
    ReporterCreate,
    ReporterResponse,
    RiskProfileResponse,
)
from app.services.anti_gaming import is_duplicate_report, validate_reporter_proximity
from app.services.storage import presign_upload, store_local_upload
from app.workers.tasks import recompute_risk_profile_task, verify_media_task


router = APIRouter()
HASHED_PLATE_RE = re.compile(r"^[a-f0-9]{64}$")


def hash_plate(raw_plate: str) -> str:
    normalized = raw_plate.strip().upper().encode("utf-8")
    pepper = settings.plate_hash_pepper.encode("utf-8")
    return hmac.new(pepper, normalized, hashlib.sha256).hexdigest()


def _validate_report_timestamp(timestamp: datetime) -> datetime:
    normalized = timestamp.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if normalized > now + timedelta(seconds=settings.max_future_report_skew_seconds):
        raise HTTPException(status_code=400, detail="Report timestamp is too far in the future")
    if normalized < now - timedelta(days=settings.max_report_age_days):
        raise HTTPException(status_code=400, detail="Report timestamp is too old")
    return normalized


@router.post("/auth/reporters", response_model=ReporterResponse, status_code=status.HTTP_201_CREATED)
def create_reporter(payload: ReporterCreate, db: Session = Depends(get_db)):
    reporter = Users(social_graph_verified=payload.social_graph_verified)
    db.add(reporter)
    db.commit()
    db.refresh(reporter)
    return ReporterResponse.model_validate(reporter)


@router.post("/media/presign", response_model=MediaPresignResponse)
def create_upload_url(payload: MediaPresignRequest):
    try:
        url, object_key = presign_upload(payload.filename, payload.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaPresignResponse(upload_url=url, object_key=object_key)


@router.put("/media/local-upload/{object_key:path}", response_model=MediaUploadResponse)
async def local_upload_media(object_key: str, request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if not content_type:
        raise HTTPException(status_code=400, detail="Content-Type header is required")

    payload = await request.body()
    try:
        media_url = store_local_upload(object_key, content_type, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(media_url=media_url, object_key=object_key)


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    reporter = db.get(Users, payload.reporter_id)
    if reporter is None:
        raise HTTPException(status_code=404, detail="Reporter not found")

    event_timestamp = _validate_report_timestamp(payload.timestamp)
    hour_start = event_timestamp.replace(minute=0, second=0, microsecond=0)
    hourly_count_stmt = select(func.count(Reports.id)).where(
        and_(
            Reports.reporter_id == payload.reporter_id,
            Reports.timestamp >= hour_start,
            Reports.timestamp <= event_timestamp,
        )
    )
    hourly_count = db.execute(hourly_count_stmt).scalar_one()
    if hourly_count >= settings.report_rate_limit_per_hour:
        raise HTTPException(status_code=429, detail="Hourly report limit exceeded")

    if not validate_reporter_proximity(
        payload.reporter_latitude, payload.reporter_longitude, payload.latitude, payload.longitude
    ):
        raise HTTPException(status_code=400, detail="Reporter location mismatch")

    hashed_plate = hash_plate(payload.target_license_plate)
    if is_duplicate_report(
        db,
        payload.reporter_id,
        hashed_plate,
        payload.behavior_category,
        event_timestamp,
        payload.latitude,
        payload.longitude,
    ):
        raise HTTPException(status_code=409, detail="Duplicate report detected")

    report = Reports(
        reporter_id=payload.reporter_id,
        target_license_plate=hashed_plate,
        behavior_category=payload.behavior_category,
        location=f"POINT({payload.longitude} {payload.latitude})",
        latitude=payload.latitude,
        longitude=payload.longitude,
        timestamp=event_timestamp,
        media_url=payload.media_url,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    if payload.media_url:
        verify_media_task.delay(str(report.id))
    recompute_risk_profile_task.delay(hashed_plate)

    return ReportResponse(id=report.id, verification_status=report.verification_status)


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
def get_report(report_id: UUID, db: Session = Depends(get_db)):
    report = db.get(Reports, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportDetailResponse.model_validate(report)


@router.patch("/admin/reports/{report_id}/verification", response_model=ReportDetailResponse)
def update_report_verification(
    report_id: UUID,
    verification_status: VerificationStatus,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    report = db.get(Reports, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.verification_status = verification_status
    db.add(report)
    db.commit()
    db.refresh(report)
    recompute_risk_profile_task.delay(report.target_license_plate)
    return ReportDetailResponse.model_validate(report)


@router.get("/risk-profile/{hashed_plate}", response_model=RiskProfileResponse)
def get_risk_profile(hashed_plate: str, db: Session = Depends(get_db)):
    if not HASHED_PLATE_RE.fullmatch(hashed_plate):
        raise HTTPException(status_code=400, detail="hashed_plate must be a 64-char lowercase SHA-256 hex")

    profile = db.get(DriverRiskProfiles, hashed_plate)
    if profile is None:
        return RiskProfileResponse(risk_score=0.0, confidence_interval=0.0, top_risk_factors=[])

    factors = json.loads(profile.top_risk_factors) if profile.top_risk_factors else []
    return RiskProfileResponse(
        risk_score=profile.current_risk_score,
        confidence_interval=profile.confidence_interval,
        top_risk_factors=factors,
    )
