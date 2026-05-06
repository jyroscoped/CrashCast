from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "CrashCast API"
    api_prefix: str = "/api/v1"

    database_url: str = Field(default="postgresql+psycopg://localhost:5432/crashcast")
    redis_url: str = Field(default="redis://localhost:6379/0")

    aws_region: str = Field(default="us-east-1")
    s3_bucket: str = Field(default="crashcast-media")
    plate_hash_pepper: str = Field(default="change-me")
    public_plate_lookup_salt: str = Field(default="public_demo_salt_not_secret")
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
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(origin.strip() for origin in value.split(",") if origin.strip())
        return value

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
