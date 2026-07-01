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
