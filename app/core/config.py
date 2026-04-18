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

    report_rate_limit_per_hour: int = 30
    duplicate_report_window_minutes: int = 10
    duplicate_report_distance_meters: float = 50.0
    proximity_tolerance_meters: float = 120.0


settings = Settings()
