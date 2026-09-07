from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["rider", "captain", "operator", "admin"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_demo: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


class SignupRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["rider", "captain", "operator"] = "rider"


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class LocationPoint(BaseModel):
    name: str
    lat: float
    lng: float


class DriverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    vehicle_type: str
    status: str
    current_lat: float
    current_lng: float


class RideCreate(BaseModel):
    pickup_location: str
    drop_location: str
    pickup_point: LocationPoint | None = None
    drop_point: LocationPoint | None = None
    passenger_count: int = Field(ge=1, le=6)
    ride_type: str


class RideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pickup_name: str
    drop_name: str
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    passenger_count: int
    ride_type: str
    status: str
    created_at: datetime


class ParcelCreate(BaseModel):
    pickup_location: str
    drop_location: str
    pickup_point: LocationPoint | None = None
    drop_point: LocationPoint | None = None
    parcel_weight: float = Field(gt=0, le=50)
    parcel_type: str
    priority: Literal["Low", "Medium", "High", "Urgent"]


class ParcelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pickup_name: str
    drop_name: str
    pickup_lat: float
    pickup_lng: float
    drop_lat: float
    drop_lng: float
    parcel_weight: float
    parcel_type: str
    priority: str
    status: str
    created_at: datetime


class RouteDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    efficiency_score: float
    extra_distance: float
    extra_time: float
    overlap_distance: float
    recommendation: str
    decision_mode: str
    accepted: bool | None
    created_at: datetime


class AcceptBothConstraint(BaseModel):
    key: str
    label: str
    actual: float
    threshold: float
    comparison: Literal["gte", "lte"]
    passed: bool


class AcceptBothAnalysis(BaseModel):
    passenger_baseline_distance: float
    combined_route_distance: float
    extra_distance: float
    extra_time: float
    passenger_delay: float
    overlap_distance: float
    efficiency_score: float
    route_sequence: list[LocationPoint]
    constraints: list[AcceptBothConstraint]
    all_constraints_passed: bool


class RecommendationResponse(BaseModel):
    driver: DriverRead
    ride: RideRead | None
    parcel: ParcelRead | None
    efficiency_score: float
    extra_distance: float
    extra_time: float
    overlap_distance: float
    recommendation: str
    decision_mode: str
    route_confirmed: bool
    confirmation_status: str
    ride_customer_price: float
    parcel_customer_price: float
    combined_customer_total: float
    estimated_customer_savings: float
    passenger_route: list[LocationPoint]
    parcel_route: list[LocationPoint]
    optimized_route: list[LocationPoint]
    recent_decision: RouteDecisionRead | None = None
    # Only present when a ride+parcel bundle was actually evaluated (i.e. not
    # for ride_only/parcel_only decision modes) — explains why ACCEPT BOTH
    # was or wasn't chosen, using the backend's own computed numbers.
    accept_both_analysis: AcceptBothAnalysis | None = None


class RecommendationAction(BaseModel):
    decision: Literal["accept_both", "accept_ride", "accept_parcel", "reject"]


class RecommendationActionResponse(BaseModel):
    message: str
    decision: RouteDecisionRead | None


class AssignmentEngineStats(BaseModel):
    drivers_considered: int
    rides_considered: int
    parcels_considered: int
    stage1_pairs_evaluated: int
    stage1_pairs_after_pruning: int
    stage2_pairs_evaluated: int
    stage2_pairs_after_pruning: int
    solve_time_ms: float
    optimal_cost: float
    greedy_cost: float
    improvement_pct: float
    optimal_matched_count: int
    greedy_matched_count: int


class ConcurrencyStats(BaseModel):
    conflicts_prevented: int
    stress_tests_run: int
    last_event_summary: str | None = None


class DashboardMetrics(BaseModel):
    total_rides: int
    total_parcels: int
    total_combined_trips: int
    active_captains: int
    average_efficiency_score: float
    estimated_fuel_saved: float
    captain_total_earnings: float
    captain_rides_handled: int
    captain_parcels_handled: int
    captain_combined_trips: int


class ActivityItem(BaseModel):
    timestamp: datetime
    activity_type: str
    route_label: str
    status: str
    recommendation: str
    efficiency_score: float | None = None


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    recent_activity: list[ActivityItem]
    assignment_engine: AssignmentEngineStats
    concurrency: ConcurrencyStats


class AppSnapshotResponse(BaseModel):
    dashboard: DashboardResponse
    recommendation: RecommendationResponse | None
    rides: list[RideRead]
    parcels: list[ParcelRead]


class DemoLoadResponse(BaseModel):
    driver: DriverRead
    ride: RideRead
    parcel: ParcelRead
    message: str


class DemoClearResponse(BaseModel):
    cleared_rides: int
    cleared_parcels: int
    cleared_decisions: int
    message: str


class SeedFleetRequest(BaseModel):
    captains: int = Field(default=5, ge=1, le=30)
    rides: int = Field(default=10, ge=0, le=30)
    parcels: int = Field(default=10, ge=0, le=30)


class SeedCaptainCredential(BaseModel):
    email: str
    password: str
    display_name: str


class SeedFleetResponse(BaseModel):
    captains: list[SeedCaptainCredential]
    created_rides: int
    created_parcels: int
    message: str


class ConcurrencyStressRequest(BaseModel):
    ride_id: int
    parcel_id: int
    attempts: int = Field(default=5, ge=2, le=20)


class ConcurrencyStressResponse(BaseModel):
    attempts: int
    succeeded: int
    conflicts: int
    winner_driver_id: int | None
    message: str
