import hashlib
import hmac
import json
import logging
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from geoalchemy2.shape import from_shape
from PIL import UnidentifiedImageError
from shapely.geometry import Point
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DriverRiskProfiles, PlateLookupAliases, Reports, Users, VerificationStatus
from app.db.session import get_db
from app.schemas import (
    MediaAutoFillResponse,
    MediaPresignRequest,
    MediaPresignResponse,
    ReportCreate,
    ReportResponse,
    ReporterCreate,
    ReporterResponse,
    RiskProfileResponse,
)
from app.services.anti_gaming import is_duplicate_report, validate_reporter_proximity
from app.services.media_intel import extract_media_autofill
from app.services.storage import presign_upload
from app.workers.tasks import recompute_risk_profile_task, verify_media_task


router = APIRouter()
logger = logging.getLogger(__name__)


def hash_plate(raw_plate: str) -> str:
    normalized = raw_plate.strip().upper().encode("utf-8")
    pepper = settings.plate_hash_pepper.encode("utf-8")
    return hmac.new(pepper, normalized, hashlib.sha256).hexdigest()


def public_lookup_hash(raw_plate: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", raw_plate.strip().upper())
    payload = f"{settings.public_plate_lookup_salt}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


@router.post("/media/extract", response_model=MediaAutoFillResponse)
async def extract_media_fields(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload")

    try:
        extracted = extract_media_autofill(image_bytes, filename=file.filename)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image file") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Image metadata format is invalid") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Unable to decode image bytes") from exc
    except Exception as exc:
        logger.exception("Unexpected failure during media extraction")
        raise HTTPException(status_code=500, detail="Unexpected image processing failure") from exc

    return MediaAutoFillResponse(**extracted)


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
    lookup_alias_hash = public_lookup_hash(payload.target_license_plate)
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
    alias = db.get(PlateLookupAliases, lookup_alias_hash)
    if alias is None:
        db.add(PlateLookupAliases(alias_hash=lookup_alias_hash, canonical_hash=hashed_plate))
    elif alias.canonical_hash != hashed_plate:
        alias.canonical_hash = hashed_plate

    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        if payload.media_url:
            verify_media_task.delay(str(report.id))
        recompute_risk_profile_task.delay(hashed_plate)
    except Exception:
        logger.warning("Failed to enqueue background tasks for report %s", report.id)

    return ReportResponse(id=report.id, verification_status=report.verification_status)


@router.get("/reports/feed")
def get_reports_feed(limit: int = 150, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 500))
    reports = db.execute(select(Reports).order_by(Reports.timestamp.desc()).limit(safe_limit)).scalars().all()
    return [
        {
            "id": str(report.id),
            "reporter_id": str(report.reporter_id),
            "target_license_plate": report.target_license_plate,
            "behavior_category": report.behavior_category.value,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "timestamp": report.timestamp.isoformat(),
            "media_url": report.media_url,
            "verification_status": report.verification_status.value,
        }
        for report in reports
    ]


@router.get("/risk-profile/{hashed_plate}", response_model=RiskProfileResponse)
def get_risk_profile(hashed_plate: str, db: Session = Depends(get_db)):
    canonical_hash = hashed_plate
    profile = db.get(DriverRiskProfiles, canonical_hash)
    if profile is None:
        alias = db.get(PlateLookupAliases, hashed_plate)
        if alias is not None:
            canonical_hash = alias.canonical_hash
            profile = db.get(DriverRiskProfiles, canonical_hash)

    if profile is None:
        return RiskProfileResponse(
            hashed_plate=hashed_plate,
            current_score=0.0,
            total_reports=0,
            last_calculated_at=None,
            behavior_counts={},
            risk_score=0.0,
            confidence_interval=0.0,
            top_risk_factors=[],
        )

    factors = json.loads(profile.top_risk_factors) if profile.top_risk_factors else []
    behavior_counts_stmt = (
        select(Reports.behavior_category, func.count(Reports.id))
        .where(
            and_(
                Reports.target_license_plate == canonical_hash,
                Reports.verification_status == VerificationStatus.verified,
            )
        )
        .group_by(Reports.behavior_category)
    )
    behavior_counts = {
        category.value: count
        for category, count in db.execute(behavior_counts_stmt).all()
    }

    return RiskProfileResponse(
        hashed_plate=hashed_plate,
        current_score=profile.current_risk_score,
        total_reports=profile.total_reports,
        last_calculated_at=profile.last_calculated_at,
        behavior_counts=behavior_counts,
        risk_score=profile.current_risk_score,
        confidence_interval=profile.confidence_interval,
        top_risk_factors=factors,
    )
