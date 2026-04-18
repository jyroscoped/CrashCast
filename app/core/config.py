from pydantic import Field
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
