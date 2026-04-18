from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.models import CredibilityAuditLog, Reports, Users
from app.db.session import SessionLocal
from app.services.scoring import upsert_risk_profile
from app.workers.celery_app import celery_app


@celery_app.task
def verify_media_task(report_id: str) -> dict:
    # TODO: replace with YOLO-based vehicle/license-plate verification.
    return {
        "report_id": report_id,
        "verified": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task
def recompute_risk_profile_task(hashed_plate: str) -> dict:
    db = SessionLocal()
    try:
        reports = db.execute(select(Reports).where(Reports.target_license_plate == hashed_plate)).scalars().all()
        weighted_count = 0.0
        for report in reports:
            reporter = db.get(Users, report.reporter_id)
            weighted_count += (
                reporter.reputation_score if reporter else settings.default_reporter_reputation
            )

        profile = upsert_risk_profile(db, hashed_plate, weighted_count)
        return {
            "hashed_plate": hashed_plate,
            "risk_score": profile.current_risk_score,
            "total_reports": profile.total_reports,
        }
    finally:
        db.close()


@celery_app.task
def nightly_credibility_update_task() -> dict:
    db = SessionLocal()
    updates = 0
    try:
        users = db.execute(select(Users)).scalars().all()
        for user in users:
            old_score = user.reputation_score
            user.reputation_score = min(
                settings.max_reputation_score,
                round(old_score * settings.nightly_reputation_growth, 4),
            )
            db.add(
                CredibilityAuditLog(
                    reporter_id=user.id,
                    old_reputation_score=old_score,
                    new_reputation_score=user.reputation_score,
                    reason="nightly_bayesian_adjustment",
                )
            )
            updates += 1

        db.commit()
        return {"updated_reporters": updates}
    finally:
        db.close()
