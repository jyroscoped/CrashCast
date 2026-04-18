import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DriverRiskProfiles


DEFAULT_FACTORS = ["tailgating", "late_night"]


def calculate_risk_score(weighted_report_count: float) -> float:
    score = min(100.0, max(0.0, weighted_report_count * 8.0))
    return round(score, 2)


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
    profile.total_reports = int(weighted_report_count)
    profile.confidence_interval = confidence_interval
    profile.top_risk_factors = json.dumps(top_risk_factors or DEFAULT_FACTORS)
    profile.last_calculated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)
    return profile
