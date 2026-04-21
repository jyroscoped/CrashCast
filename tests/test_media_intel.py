from datetime import datetime, timezone
from fractions import Fraction

from app.services.media_intel import (
    extract_gps_from_exif,
    extract_plate_from_text,
    extract_timestamp_from_exif,
)


def test_extract_plate_from_text_normalizes_plate():
    detected = extract_plate_from_text("Vehicle observed: abc-1234 near intersection")
    assert detected == "ABC1234"


def test_extract_plate_from_text_returns_none_when_no_candidate():
    assert extract_plate_from_text("No readable identifier in this OCR text") is None


def test_extract_gps_from_exif_converts_dms_to_decimal():
    exif_data = {
        34853: {
            1: "N",
            2: (Fraction(40, 1), Fraction(26, 1), Fraction(4368, 100)),
            3: "W",
            4: (Fraction(79, 1), Fraction(58, 1), Fraction(4344, 100)),
        }
    }
    latitude, longitude = extract_gps_from_exif(exif_data)
    assert latitude is not None and round(latitude, 4) == 40.4455
    assert longitude is not None and round(longitude, 4) == -79.9787


def test_extract_timestamp_from_exif():
    exif_data = {36867: "2026:04:20 12:34:56"}
    timestamp = extract_timestamp_from_exif(exif_data)
    assert timestamp == datetime(2026, 4, 20, 12, 34, 56, tzinfo=timezone.utc)
