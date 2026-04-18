import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DriverRiskProfiles, Reports, Users
from app.db.session import get_db
from app.schemas import (
    MediaPresignRequest,
    MediaPresignResponse,
    ReportCreate,
    ReportResponse,
    ReporterCreate,
    ReporterResponse,
    RiskProfileResponse,
)
from app.services.anti_gaming import is_duplicate_report, validate_reporter_proximity
from app.services.storage import presign_upload
from app.workers.tasks import recompute_risk_profile_task, verify_media_task


router = APIRouter()


def hash_plate(raw_plate: str) -> str:
    return hashlib.sha256(raw_plate.strip().upper().encode("utf-8")).hexdigest()


@router.post("/auth/reporters", response_model=ReporterResponse, status_code=status.HTTP_201_CREATED)
def create_reporter(payload: ReporterCreate, db: Session = Depends(get_db)):
    reporter = Users(social_graph_verified=payload.social_graph_verified)
    db.add(reporter)
    db.commit()
    db.refresh(reporter)
    return reporter


@router.post("/media/presign", response_model=MediaPresignResponse)
def create_upload_url(payload: MediaPresignRequest):
    url, object_key = presign_upload(payload.filename, payload.content_type)
    return MediaPresignResponse(upload_url=url, object_key=object_key)


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    reporter = db.get(Users, payload.reporter_id)
    if reporter is None:
        raise HTTPException(status_code=404, detail="Reporter not found")

    hour_start = payload.timestamp.replace(minute=0, second=0, microsecond=0)
    hourly_count_stmt = select(func.count(Reports.id)).where(
        and_(
            Reports.reporter_id == payload.reporter_id,
            Reports.timestamp >= hour_start,
            Reports.timestamp <= payload.timestamp,
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
        payload.timestamp,
        payload.latitude,
        payload.longitude,
    ):
        raise HTTPException(status_code=409, detail="Duplicate report detected")

    report = Reports(
        reporter_id=payload.reporter_id,
        target_license_plate=hashed_plate,
        behavior_category=payload.behavior_category,
        location=from_shape(Point(payload.longitude, payload.latitude), srid=4326),
        latitude=payload.latitude,
        longitude=payload.longitude,
        timestamp=payload.timestamp,
        media_url=payload.media_url,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    if payload.media_url:
        verify_media_task.delay(str(report.id))
    recompute_risk_profile_task.delay(hashed_plate)

    return ReportResponse(id=report.id, verification_status=report.verification_status)


@router.get("/risk-profile/{hashed_plate}", response_model=RiskProfileResponse)
def get_risk_profile(hashed_plate: str, db: Session = Depends(get_db)):
    profile = db.get(DriverRiskProfiles, hashed_plate)
    if profile is None:
        return RiskProfileResponse(risk_score=0.0, confidence_interval=0.0, top_risk_factors=[])

    factors = json.loads(profile.top_risk_factors) if profile.top_risk_factors else []
    return RiskProfileResponse(
        risk_score=profile.current_risk_score,
        confidence_interval=profile.confidence_interval,
        top_risk_factors=factors,
    )
