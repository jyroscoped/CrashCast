from __future__ import annotations

import re
from datetime import datetime, timezone
from fractions import Fraction
from io import BytesIO
from typing import Any

from PIL import Image


GPS_LATITUDE_TAG = 2
GPS_LATITUDE_REF_TAG = 1
GPS_LONGITUDE_TAG = 4
GPS_LONGITUDE_REF_TAG = 3


LICENSE_PLATE_PATTERN = re.compile(r"\b([A-Z0-9]{2,4}[-\s]?[A-Z0-9]{2,4})\b")


def _to_float(value: Any) -> float:
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        if denominator == 0:
            raise ValueError("Invalid EXIF fraction denominator")
        return float(numerator) / float(denominator)
    if isinstance(value, Fraction):
        return float(value)
    return float(value)


def _dms_to_decimal(dms: tuple[Any, Any, Any], ref: str) -> float:
    degrees = _to_float(dms[0])
    minutes = _to_float(dms[1])
    seconds = _to_float(dms[2])
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    ref_value = ref.decode("utf-8") if isinstance(ref, bytes) else ref
    if ref_value.upper() in {"S", "W"}:
        decimal *= -1
    return decimal


def extract_gps_from_exif(exif_data: dict[int, Any]) -> tuple[float | None, float | None]:
    gps_ifd = exif_data.get(34853)
    if not isinstance(gps_ifd, dict):
        return None, None

    latitude_raw = gps_ifd.get(GPS_LATITUDE_TAG)
    latitude_ref = gps_ifd.get(GPS_LATITUDE_REF_TAG)
    longitude_raw = gps_ifd.get(GPS_LONGITUDE_TAG)
    longitude_ref = gps_ifd.get(GPS_LONGITUDE_REF_TAG)
    if not (latitude_raw and latitude_ref and longitude_raw and longitude_ref):
        return None, None

    latitude = _dms_to_decimal(latitude_raw, latitude_ref)
    longitude = _dms_to_decimal(longitude_raw, longitude_ref)
    return latitude, longitude


def extract_timestamp_from_exif(exif_data: dict[int, Any]) -> datetime | None:
    datetime_original = exif_data.get(36867) or exif_data.get(306)
    if not datetime_original or not isinstance(datetime_original, str):
        return None

    parsed = datetime.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
    return parsed.replace(tzinfo=timezone.utc)


def extract_plate_from_text(text: str) -> str | None:
    for match in LICENSE_PLATE_PATTERN.findall(text.upper()):
        normalized = re.sub(r"[-\s]", "", match)
        if (
            5 <= len(normalized) <= 8
            and any(ch.isalpha() for ch in normalized)
            and any(ch.isdigit() for ch in normalized)
        ):
            return normalized
    return None


def extract_plate_from_image_bytes(image_bytes: bytes) -> str | None:
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        image = Image.open(BytesIO(image_bytes))
        detected_text = pytesseract.image_to_string(image)
    except Exception:
        return None

    return extract_plate_from_text(detected_text)


def extract_media_autofill(image_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    image = Image.open(BytesIO(image_bytes))
    exif_data = image.getexif() or {}

    latitude, longitude = extract_gps_from_exif(exif_data)
    timestamp = extract_timestamp_from_exif(exif_data)
    plate = extract_plate_from_image_bytes(image_bytes)

    if plate is None and filename:
        plate = extract_plate_from_text(filename)

    return {
        "detected_license_plate": plate,
        "detected_latitude": latitude,
        "detected_longitude": longitude,
        "detected_timestamp": timestamp,
    }
