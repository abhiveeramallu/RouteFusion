export type UserRole = "rider" | "captain" | "operator" | "admin";

export type UserSession = {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_demo: boolean;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserSession;
};

export type LoginFormValues = {
  email: string;
  password: string;
};

export type SignupFormValues = {
  full_name: string;
  email: string;
  password: string;
  role: Exclude<UserRole, "admin">;
};

export type Ride = {
  id: number;
  pickup_name: string;
  drop_name: string;
  pickup_lat: number;
  pickup_lng: number;
  drop_lat: number;
  drop_lng: number;
  passenger_count: number;
  ride_type: string;
  status: string;
  created_at: string;
};

export type Parcel = {
  id: number;
  pickup_name: string;
  drop_name: string;
  pickup_lat: number;
  pickup_lng: number;
  drop_lat: number;
  drop_lng: number;
  parcel_weight: number;
  parcel_type: string;
  priority: string;
  status: string;
  created_at: string;
};

export type Driver = {
  id: number;
  display_name: string;
  vehicle_type: string;
  status: string;
  current_lat: number;
  current_lng: number;
};

export type RoutePoint = {
  name: string;
  lat: number;
  lng: number;
};

export type LocationSelection = {
  name: string;
  lat: number | null;
  lng: number | null;
};

export type RideDraftValues = {
  pickup_location: LocationSelection;
  drop_location: LocationSelection;
  passenger_count: number;
  ride_type: string;
};

export type ParcelDraftValues = {
  pickup_location: LocationSelection;
  drop_location: LocationSelection;
  parcel_weight: number;
  parcel_type: string;
  priority: "Low" | "Medium" | "High" | "Urgent";
};

export type RouteDecision = {
  id: number;
  efficiency_score: number;
  extra_distance: number;
  extra_time: number;
  overlap_distance: number;
  recommendation: string;
  decision_mode: "pending" | "combined" | "ride_only" | "parcel_only";
  accepted: boolean | null;
  created_at: string;
};

export type CaptainDecision = "accept_both" | "accept_ride" | "accept_parcel" | "reject";

export type Recommendation = {
  driver: Driver;
  ride: Ride | null;
  parcel: Parcel | null;
  efficiency_score: number;
  extra_distance: number;
  extra_time: number;
  overlap_distance: number;
  recommendation: string;
  decision_mode: "pending" | "combined" | "ride_only" | "parcel_only";
  route_confirmed: boolean;
  confirmation_status: string;
  ride_customer_price: number;
  parcel_customer_price: number;
  combined_customer_total: number;
  estimated_customer_savings: number;
  passenger_route: RoutePoint[];
  parcel_route: RoutePoint[];
  optimized_route: RoutePoint[];
  recent_decision: RouteDecision | null;
};

export type DashboardMetrics = {
  total_rides: number;
  total_parcels: number;
  total_combined_trips: number;
  active_captains: number;
  average_efficiency_score: number;
  estimated_fuel_saved: number;
  captain_total_earnings: number;
  captain_rides_handled: number;
  captain_parcels_handled: number;
  captain_combined_trips: number;
};

export type ActivityItem = {
  timestamp: string;
  activity_type: string;
  route_label: string;
  status: string;
  recommendation: string;
  efficiency_score: number | null;
};

export type DashboardData = {
  metrics: DashboardMetrics;
  recent_activity: ActivityItem[];
};

export type AppSnapshotData = {
  dashboard: DashboardData;
  recommendation: Recommendation | null;
  rides: Ride[];
  parcels: Parcel[];
};

export type DemoLoadData = {
  driver: Driver;
  ride: Ride;
  parcel: Parcel;
  message: string;
};

export type DemoClearData = {
  cleared_rides: number;
  cleared_parcels: number;
  cleared_decisions: number;
  message: string;
};

export type DemoLoginResponse = AuthResponse;

export type RideFormValues = {
  pickup_location: string;
  drop_location: string;
  pickup_point: RoutePoint | null;
  drop_point: RoutePoint | null;
  passenger_count: number;
  ride_type: string;
};

export type ParcelFormValues = {
  pickup_location: string;
  drop_location: string;
  pickup_point: RoutePoint | null;
  drop_point: RoutePoint | null;
  parcel_weight: number;
  parcel_type: string;
  priority: "Low" | "Medium" | "High" | "Urgent";
};

export type TripType = "Ride" | "Parcel" | "Combined";

export type BookingMode = "ride" | "parcel" | "captain";

export type MapScenarioStat = {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "accent" | "purple";
};

export type MapScenario = {
  id: string;
  title: string;
  subtitle: string;
  passengerRoute: RoutePoint[];
  parcelRoute: RoutePoint[];
  optimizedRoute: RoutePoint[];
  captainLocation: RoutePoint | null;
  currentLocation: RoutePoint | null;
  badge?: string;
  dockStats: MapScenarioStat[];
  animateCaptain?: boolean;
};
