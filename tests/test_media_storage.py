from pathlib import Path

from app.core.config import settings
from app.services.storage import presign_upload, store_local_upload


def test_presign_upload_returns_local_endpoint_in_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "media_storage_mode", "local")
    upload_url, object_key = presign_upload("incident.jpg", "image/jpeg")
    assert upload_url.startswith("/api/v1/media/local-upload/reports/")
    assert object_key.startswith("reports/")


def test_store_local_upload_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "local_upload_dir", str(tmp_path))
    media_url = store_local_upload("reports/test-file.jpg", "image/jpeg", b"test-bytes")
    assert media_url == "/uploads/test-file.jpg"
    assert (Path(tmp_path) / "test-file.jpg").read_bytes() == b"test-bytes"
