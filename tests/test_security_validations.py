from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import BehaviorCategory
from app.schemas import ReportCreate
from app.services.storage import _sanitize_filename, presign_upload


def test_report_create_requires_timezone_aware_timestamp():
    with pytest.raises(ValidationError):
        ReportCreate(
            reporter_id=uuid4(),
            target_license_plate="ABC123",
            behavior_category=BehaviorCategory.tailgating,
            latitude=40.0,
            longitude=-79.0,
            reporter_latitude=40.0,
            reporter_longitude=-79.0,
            timestamp=datetime.now(),
        )


def test_report_create_normalizes_plate():
    payload = ReportCreate(
        reporter_id=uuid4(),
        target_license_plate="  abc123  ",
        behavior_category=BehaviorCategory.tailgating,
        latitude=40.0,
        longitude=-79.0,
        reporter_latitude=40.0,
        reporter_longitude=-79.0,
        timestamp=datetime.now(timezone.utc),
    )
    assert payload.target_license_plate == "ABC123"


def test_presign_upload_rejects_unsupported_content_type():
    with pytest.raises(ValueError, match="Unsupported content type"):
        presign_upload("evidence.jpg", "application/pdf")


def test_sanitize_filename_drops_path_segments():
    assert _sanitize_filename(r"..\..\secret\camera shot.jpg") == "camera_shot.jpg"
