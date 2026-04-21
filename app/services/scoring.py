import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DriverRiskProfiles, Reports, Users, VerificationStatus


def _default_factors() -> list[str]:
    return [item.strip() for item in settings.default_top_risk_factors.split(",") if item.strip()]


def calculate_risk_score(weighted_report_count: float) -> float:
    score = min(100.0, max(0.0, weighted_report_count * 8.0))
    return round(score, 2)


def compute_weighted_report_count(db: Session, hashed_plate: str) -> float:
    reports = (
        db.execute(
            select(Reports).where(
                Reports.target_license_plate == hashed_plate,
                Reports.verification_status == VerificationStatus.verified,
            )
        )
        .scalars()
        .all()
    )
    weighted_count = 0.0
    for report in reports:
        reporter = db.get(Users, report.reporter_id)
        weighted_count += reporter.reputation_score if reporter else settings.default_reporter_reputation
    return round(weighted_count, 6)


def upsert_risk_profile(
    db: Session,
    hashed_plate: str,
    weighted_report_count: float,
    confidence_interval: float = 0.75,
    top_risk_factors: list[str] | None = None,
) -> DriverRiskProfiles:
    profile = db.get(DriverRiskProfiles, hashed_plate)
    if profile is None:
        profile = DriverRiskProfiles(hashed_license_plate=hashed_plate)
        db.add(profile)

    profile.current_risk_score = calculate_risk_score(weighted_report_count)
    profile.total_reports = max(0, int(round(weighted_report_count)))
    profile.weighted_report_total = round(weighted_report_count, 4)
    profile.confidence_interval = confidence_interval
    profile.top_risk_factors = json.dumps(top_risk_factors or _default_factors())
    profile.last_calculated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)
    return profile
