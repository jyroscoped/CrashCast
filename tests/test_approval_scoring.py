from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, BehaviorCategory, Reports, Users, VerificationStatus
from app.services.scoring import compute_weighted_report_count


def test_weighted_count_only_includes_verified_reports():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = Session()
    try:
        reporter = Users(reputation_score=2.5, social_graph_verified=True)
        db.add(reporter)
        db.commit()
        db.refresh(reporter)

        hashed_plate = "a" * 64
        verified = Reports(
            reporter_id=reporter.id,
            target_license_plate=hashed_plate,
            behavior_category=BehaviorCategory.tailgating,
            location="POINT(-79.9959 40.4406)",
            latitude=40.4406,
            longitude=-79.9959,
            timestamp=datetime.now(timezone.utc),
            verification_status=VerificationStatus.verified,
        )
        pending = Reports(
            reporter_id=reporter.id,
            target_license_plate=hashed_plate,
            behavior_category=BehaviorCategory.tailgating,
            location="POINT(-79.9959 40.4406)",
            latitude=40.4406,
            longitude=-79.9959,
            timestamp=datetime.now(timezone.utc),
            verification_status=VerificationStatus.pending,
        )
        db.add_all([verified, pending])
        db.commit()

        assert compute_weighted_report_count(db, hashed_plate) == 2.5
    finally:
        db.close()
