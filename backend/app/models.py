from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="rider")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver = relationship("Driver", back_populates="user", uselist=False)
    rides = relationship("Ride", back_populates="created_by_user")
    parcels = relationship("Parcel", back_populates="created_by_user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    blacklisted_tokens = relationship("TokenBlacklist", back_populates="user")


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (
        Index("ix_drivers_current_location", "current_lat", "current_lng"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    vehicle_type: Mapped[str] = mapped_column(String(100), default="Hybrid Cab")
    status: Mapped[str] = mapped_column(String(50), default="available", index=True)
    current_lat: Mapped[float] = mapped_column(Float)
    current_lng: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="driver")
    route_decisions = relationship("RouteDecision", back_populates="driver")


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    pickup_name: Mapped[str] = mapped_column(String(255))
    drop_name: Mapped[str] = mapped_column(String(255))
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lng: Mapped[float] = mapped_column(Float)
    drop_lat: Mapped[float] = mapped_column(Float)
    drop_lng: Mapped[float] = mapped_column(Float)
    passenger_count: Mapped[int] = mapped_column(Integer)
    ride_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assigned_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    created_by_user = relationship("User", back_populates="rides")
    route_decisions = relationship("RouteDecision", back_populates="ride")


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    pickup_name: Mapped[str] = mapped_column(String(255))
    drop_name: Mapped[str] = mapped_column(String(255))
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lng: Mapped[float] = mapped_column(Float)
    drop_lat: Mapped[float] = mapped_column(Float)
    drop_lng: Mapped[float] = mapped_column(Float)
    parcel_weight: Mapped[float] = mapped_column(Float)
    parcel_type: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="open", index=True)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assigned_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    created_by_user = relationship("User", back_populates="parcels")
    route_decisions = relationship("RouteDecision", back_populates="parcel")


class RouteDecision(Base):
    __tablename__ = "route_decisions"
    __table_args__ = (
        Index("ix_route_decisions_trip_pair_created_at", "ride_id", "parcel_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    ride_id: Mapped[int] = mapped_column(ForeignKey("rides.id"))
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"))
    efficiency_score: Mapped[float] = mapped_column(Float)
    extra_distance: Mapped[float] = mapped_column(Float)
    extra_time: Mapped[float] = mapped_column(Float)
    overlap_distance: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(50))
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    driver = relationship("Driver", back_populates="route_decisions")
    ride = relationship("Ride", back_populates="route_decisions")
    parcel = relationship("Parcel", back_populates="route_decisions")


class DriverDecline(Base):
    """A captain's solo decline of one specific ride or parcel — excludes
    that request from being re-offered to this same driver (see
    assignment_engine's stage1/stage2 cost functions), so it naturally falls
    through to the next available captain instead of looping back to
    whoever just turned it down. Exactly one of ride_id/parcel_id is set.
    """

    __tablename__ = "driver_declines"
    __table_args__ = (
        Index("ix_driver_declines_driver_ride", "driver_id", "ride_id"),
        Index("ix_driver_declines_driver_parcel", "driver_id", "parcel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    ride_id: Mapped[int] = mapped_column(ForeignKey("rides.id"), nullable=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ConcurrencyEvent(Base):
    __tablename__ = "concurrency_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ride_id: Mapped[int] = mapped_column(ForeignKey("rides.id"))
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"))
    attempts: Mapped[int] = mapped_column(Integer)
    succeeded: Mapped[int] = mapped_column(Integer)
    conflicts: Mapped[int] = mapped_column(Integer)
    winner_driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="refresh_tokens")


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String(20), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="blacklisted_tokens")
