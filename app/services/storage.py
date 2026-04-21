import re
import uuid
from pathlib import Path, PurePath

import boto3
from botocore.exceptions import NoCredentialsError

from app.core.config import settings


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
BASE_DIR = Path(__file__).resolve().parents[2]


def _sanitize_filename(filename: str) -> str:
    safe_name = SAFE_FILENAME_RE.sub("_", PurePath(filename).name.strip())
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Invalid filename")
    return safe_name[:128]


def _resolve_local_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def _s3_client():
    return boto3.client("s3", region_name=settings.aws_region)


def _build_object_key(filename: str) -> str:
    safe_filename = _sanitize_filename(filename)
    return f"reports/{uuid.uuid4()}-{safe_filename}"


def _validate_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower()
    if normalized not in settings.allowed_media_content_types:
        raise ValueError("Unsupported content type")
    return normalized


def _validate_object_key(object_key: str) -> str:
    if not object_key.startswith("reports/"):
        raise ValueError("Invalid object_key")
    file_part = object_key.split("/", 1)[1]
    safe_name = _sanitize_filename(file_part)
    return f"reports/{safe_name}"


def presign_upload(filename: str, content_type: str) -> tuple[str, str]:
    normalized_type = _validate_content_type(content_type)
    object_key = _build_object_key(filename)
    if settings.media_storage_mode.strip().lower() == "local":
        return f"/api/v1/media/local-upload/{object_key}", object_key

    try:
        upload_url = _s3_client().generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": settings.s3_bucket, "Key": object_key, "ContentType": normalized_type},
            ExpiresIn=900,
        )
    except NoCredentialsError as exc:
        raise ValueError(
            "AWS credentials not found. Configure AWS credentials or set MEDIA_STORAGE_MODE=local."
        ) from exc
    return upload_url, object_key


def store_local_upload(object_key: str, content_type: str, payload: bytes) -> str:
    _validate_content_type(content_type)
    validated_key = _validate_object_key(object_key)
    if len(payload) > settings.max_upload_bytes:
        raise ValueError("Uploaded media is too large")

    local_dir = _resolve_local_path(settings.local_upload_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    file_name = validated_key.split("/", 1)[1]
    file_path = local_dir / file_name
    file_path.write_bytes(payload)
    return f"/uploads/{file_name}"
