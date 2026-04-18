import enum
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BehaviorCategory(str, enum.Enum):
    swerving = "swerving"
    tailgating = "tailgating"
    red_light = "red_light"
    aggressive_acceleration = "aggressive_acceleration"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    quarantined = "quarantined"


class Users(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    social_graph_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    reports: Mapped[list["Reports"]] = relationship(back_populates="reporter")


class Reports(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_license_plate: Mapped[str] = mapped_column(String(128), nullable=False)
    behavior_category: Mapped[BehaviorCategory] = mapped_column(Enum(BehaviorCategory), nullable=False)
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.pending, nullable=False
    )

    reporter: Mapped[Users] = relationship(back_populates="reports")


class DriverRiskProfiles(Base):
    __tablename__ = "driver_risk_profiles"

    hashed_license_plate: Mapped[str] = mapped_column(String(128), primary_key=True)
    current_risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_reports: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weighted_report_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence_interval: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    top_risk_factors: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class CredibilityAuditLog(Base):
    __tablename__ = "credibility_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    old_reputation_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_reputation_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
