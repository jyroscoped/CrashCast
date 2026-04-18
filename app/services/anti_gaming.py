import math
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Reports


EARTH_RADIUS_M = 6_371_000


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def validate_reporter_proximity(
    reporter_lat: float, reporter_lon: float, report_lat: float, report_lon: float
) -> bool:
    return (
        haversine_meters(reporter_lat, reporter_lon, report_lat, report_lon)
        <= settings.proximity_tolerance_meters
    )


def is_duplicate_report(
    db: Session,
    reporter_id,
    target_license_plate: str,
    behavior_category,
    timestamp: datetime,
    latitude: float,
    longitude: float,
) -> bool:
    window_start = timestamp - timedelta(minutes=settings.duplicate_report_window_minutes)
    lon_scale = max(0.01, math.cos(math.radians(latitude)))
    distance_expr = func.sqrt(
        func.pow((Reports.latitude - latitude) * settings.meters_per_degree_lat, 2)
        + func.pow((Reports.longitude - longitude) * settings.meters_per_degree_lat * lon_scale, 2)
    )
    stmt = (
        select(Reports.id)
        .where(
            and_(
                Reports.reporter_id == reporter_id,
                Reports.target_license_plate == target_license_plate,
                Reports.behavior_category == behavior_category,
                Reports.timestamp >= window_start,
                Reports.timestamp <= timestamp,
                distance_expr <= settings.duplicate_report_distance_meters,
            )
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None
