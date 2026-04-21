from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "CrashCast API"
    api_prefix: str = "/api/v1"

    database_url: str = Field(default="sqlite:///./crashcast.db")
    celery_broker_url: str = Field(default="filesystem://")
    celery_result_backend: str = Field(default="cache+memory://")
    celery_always_eager: bool = False

    aws_region: str = Field(default="us-east-1")
    s3_bucket: str = Field(default="crashcast-media")
    media_storage_mode: str = Field(default="local")
    plate_hash_pepper: str = Field(default="change-me")
    local_upload_dir: str = Field(default="uploads")
    max_upload_bytes: int = 25 * 1024 * 1024
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="change-me")
    admin_page_size: int = 100

    allowed_media_content_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "video/mp4",
        "video/quicktime",
    )
    max_future_report_skew_seconds: int = 300
    max_report_age_days: int = 30

    report_rate_limit_per_hour: int = 30
    duplicate_report_window_minutes: int = 10
    duplicate_report_distance_meters: float = 50.0
    proximity_tolerance_meters: float = 120.0
    meters_per_degree_lat: float = 111_000.0
    default_reporter_reputation: float = 0.1
    max_reputation_score: float = 5.0
    nightly_reputation_growth: float = 1.01
    default_top_risk_factors: str = "tailgating,late_night"


settings = Settings()
