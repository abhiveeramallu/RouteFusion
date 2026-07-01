import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  cancelParcel,
  cancelRide,
  clearDemo,
  completeCaptainRecommendation,
  createParcel,
  createRide,
  getSnapshot,
  logoutSession,
  loadDemo,
  pingHealth,
  respondToRecommendation,
  signIn,
  signUp,
} from "../lib/api";
import { defaultVelloreLocation } from "../lib/constants";
import type {
  AuthResponse,
  CaptainDecision,
  DashboardData,
  LoginFormValues,
  MapScenario,
  Parcel,
  ParcelFormValues,
  Recommendation,
  Ride,
  RideFormValues,
  RoutePoint,
  SignupFormValues,
  UserSession,
} from "../types";

const SESSION_STORAGE_KEY = "routefusion.session";
const publicUser: UserSession = {
  id: 0,
  email: "public@routefusion.app",
  full_name: "Public Access",
  role: "operator",
  is_demo: false,
};

type RouteFusionContextValue = {
  dashboard: DashboardData | null;
  recommendation: Recommendation | null;
  rides: Ride[];
  parcels: Parcel[];
  token: string | null;
  user: UserSession | null;
  isAuthenticated: boolean;
  currentLocation: RoutePoint | null;
  locationStatus: "demo" | "pending" | "available" | "unsupported" | "denied";
  loading: boolean;
  wakingServer: boolean;
  refreshing: boolean;
  error: string | null;
  bannerMessage: string | null;
  locationToast: string | null;
  mapScenario: MapScenario | null;
  refreshAll: () => Promise<void>;
  login: (payload: LoginFormValues) => Promise<UserSession>;
  signup: (payload: SignupFormValues) => Promise<UserSession>;
  logout: () => Promise<void>;
  loadDemoMode: () => Promise<void>;
  submitRide: (payload: RideFormValues) => Promise<Ride>;
  submitParcel: (payload: ParcelFormValues) => Promise<Parcel>;
  cancelRideRequest: (rideId: number) => Promise<void>;
  cancelParcelRequest: (parcelId: number) => Promise<void>;
  respondToCaptainDecision: (decision: CaptainDecision) => Promise<void>;
  completeCaptainRoute: () => Promise<void>;
  setMapScenario: (scenario: MapScenario | null) => void;
  clearBanner: () => void;
  clearLocationToast: () => void;
  clearRequests: () => Promise<void>;
};

const RouteFusionContext = createContext<RouteFusionContextValue | undefined>(undefined);

function recommendationDriverLocation(recommendation: Recommendation | null): RoutePoint | null {
  if (!recommendation) {
    return null;
  }

  return {
    name: recommendation.driver.display_name,
    lat: recommendation.driver.current_lat,
    lng: recommendation.driver.current_lng,
  };
}

function finalCaptainLocation(recommendation: Recommendation | null): RoutePoint | null {
  if (!recommendation) {
    return null;
  }

  const route =
    recommendation.decision_mode === "ride_only"
      ? recommendation.passenger_route
      : recommendation.decision_mode === "parcel_only"
        ? recommendation.parcel_route
        : recommendation.optimized_route;

  return route.length ? route[route.length - 1] : null;
}

function readStoredSession(): AuthResponse | null {
  try {
    const rawSession = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!rawSession) {
      return null;
    }
    return JSON.parse(rawSession) as AuthResponse;
  } catch {
    return null;
  }
}

function writeStoredSession(session: AuthResponse | null) {
  try {
    if (!session) {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Ignore storage failures and keep the in-memory session active.
  }
}

async function fetchSnapshot() {
  return getSnapshot();
}

export function RouteFusionProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserSession | null>(publicUser);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [rides, setRides] = useState<Ride[]>([]);
  const [parcels, setParcels] = useState<Parcel[]>([]);
  const [currentLocation, setCurrentLocation] = useState<RoutePoint | null>(defaultVelloreLocation);
  const [locationStatus] = useState<"demo" | "pending" | "available" | "unsupported" | "denied">(
    "demo",
  );
  const [loading, setLoading] = useState(true);
  const [wakingServer, setWakingServer] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bannerMessage, setBannerMessage] = useState<string | null>(null);
  const [locationToast, setLocationToast] = useState<string | null>(null);
  const [mapScenario, setMapScenario] = useState<MapScenario | null>(null);

  function applySession(session: AuthResponse) {
    setToken(session.access_token);
    setRefreshToken(session.refresh_token);
    setUser(session.user);
    writeStoredSession(session);
  }

  function clearSessionState() {
    setToken(null);
    setRefreshToken(null);
    setUser(publicUser);
    writeStoredSession(null);
  }

  function applySnapshot(
    snapshot: {
      dashboard: DashboardData | null;
      recommendation: Recommendation | null;
      rides: Ride[];
      parcels: Parcel[];
    },
    fallbackLocation: RoutePoint | null = null,
  ) {
    setDashboard(snapshot.dashboard);
    setRecommendation(snapshot.recommendation);
    setRides(snapshot.rides);
    setParcels(snapshot.parcels);
    setCurrentLocation(
      recommendationDriverLocation(snapshot.recommendation)
        ?? fallbackLocation
        ?? defaultVelloreLocation,
    );
  }

  async function refreshAll() {
    setRefreshing(true);
    setError(null);
    try {
      const snapshot = await fetchSnapshot();
      applySnapshot(snapshot, currentLocation);
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Unable to refresh RouteFusion.");
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function loadDemoMode() {
    setRefreshing(true);
    setError(null);
    try {
      const result = await loadDemo();
      setBannerMessage(result.message);
      const snapshot = await fetchSnapshot();
      applySnapshot(snapshot);
    } catch (demoError) {
      setError(demoError instanceof Error ? demoError.message : "Unable to load demo mode.");
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function login(payload: LoginFormValues) {
    setRefreshing(true);
    setError(null);
    try {
      const session = await signIn(payload);
      applySession(session);
      const snapshot = await fetchSnapshot();
      applySnapshot(snapshot);
      setBannerMessage(`Signed in as ${session.user.full_name}.`);
      return session.user;
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in.");
      throw loginError;
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function signup(payload: SignupFormValues) {
    setRefreshing(true);
    setError(null);
    try {
      const session = await signUp(payload);
      applySession(session);
      const snapshot = await fetchSnapshot();
      applySnapshot(snapshot);
      setBannerMessage(`Account created for ${session.user.full_name}.`);
      return session.user;
    } catch (signupError) {
      setError(signupError instanceof Error ? signupError.message : "Unable to create the account.");
      throw signupError;
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function logout() {
    setRefreshing(true);
    setError(null);
    try {
      if (token) {
        await logoutSession(token, refreshToken);
      }
    } catch {
      // If logout fails remotely, still clear the local session so the user exits authenticated mode here.
    } finally {
      clearSessionState();
      setBannerMessage("Signed out. RouteFusion remains available in public access mode.");
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function submitRide(payload: RideFormValues) {
    setError(null);
    try {
      const ride = await createRide(payload);
      setBannerMessage("Ride requested successfully.");
      await refreshAll();
      return ride;
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to create the ride request.");
      throw submitError;
    }
  }

  async function submitParcel(payload: ParcelFormValues) {
    setError(null);
    try {
      const parcel = await createParcel(payload);
      setBannerMessage("Parcel requested successfully.");
      await refreshAll();
      return parcel;
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to create the parcel request.");
      throw submitError;
    }
  }

  async function cancelRideRequest(rideId: number) {
    setError(null);
    try {
      const response = await cancelRide(rideId);
      setBannerMessage(response.message);
      await refreshAll();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Unable to cancel the ride request.");
      throw cancelError;
    }
  }

  async function cancelParcelRequest(parcelId: number) {
    setError(null);
    try {
      const response = await cancelParcel(parcelId);
      setBannerMessage(response.message);
      await refreshAll();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Unable to cancel the parcel request.");
      throw cancelError;
    }
  }

  async function respondToCaptainDecision(decision: CaptainDecision) {
    setError(null);
    try {
      const response = await respondToRecommendation(decision);
      setBannerMessage(response.message);
      await refreshAll();
    } catch (decisionError) {
      if (decisionError instanceof ApiError && decisionError.status === 404) {
        setBannerMessage("Recommendation already changed. RouteFusion refreshed the queue.");
        await refreshAll();
        return;
      }
      setError(decisionError instanceof Error ? decisionError.message : "Unable to save the captain decision.");
      throw decisionError;
    }
  }

  async function completeCaptainRoute() {
    setError(null);
    try {
      const completedLocation = finalCaptainLocation(recommendation);
      if (completedLocation) {
        setCurrentLocation(completedLocation);
      }
      const response = await completeCaptainRecommendation();
      setBannerMessage(response.message);
      const snapshot = await fetchSnapshot();
      applySnapshot(snapshot, completedLocation ?? currentLocation);
    } catch (completionError) {
      if (completionError instanceof ApiError && completionError.status === 404) {
        setBannerMessage("Captain route was already closed. RouteFusion refreshed the queue.");
        await refreshAll();
        return;
      }
      setError(completionError instanceof Error ? completionError.message : "Unable to complete the captain route.");
      throw completionError;
    }
  }

  async function clearRequests() {
    setRefreshing(true);
    setError(null);
    try {
      const response = await clearDemo();
      setBannerMessage(response.message);
      const snapshot = await fetchSnapshot().catch(() => ({
        dashboard: null,
        recommendation: null,
        rides: [],
        parcels: [],
      }));
      applySnapshot(snapshot);
    } catch (clearError) {
      setError(clearError instanceof Error ? clearError.message : "Unable to clear RouteFusion requests.");
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  function clearBanner() {
    setBannerMessage(null);
  }

  function clearLocationToast() {
    setLocationToast(null);
  }

  useEffect(() => {
    async function bootstrap() {
      const storedSession = readStoredSession();
      if (storedSession) {
        applySession(storedSession);
      } else {
        setUser(publicUser);
      }

      const wakeupTimer = window.setTimeout(() => {
        setWakingServer(true);
      }, 3000);

      try {
        await pingHealth().catch(() => undefined);
        const snapshot = await fetchSnapshot();
        applySnapshot(snapshot);
      } catch (bootstrapError) {
        setError(
          bootstrapError instanceof Error ? bootstrapError.message : "Unable to load RouteFusion.",
        );
      } finally {
        window.clearTimeout(wakeupTimer);
        setWakingServer(false);
        setLoading(false);
      }
    }

    void bootstrap();
  }, []);

  return (
    <RouteFusionContext.Provider
      value={{
        dashboard,
        recommendation,
        rides,
        parcels,
        token,
        user,
        isAuthenticated: Boolean(token),
        currentLocation,
        locationStatus,
        loading,
        wakingServer,
        refreshing,
        error,
        bannerMessage,
        locationToast,
        mapScenario,
        refreshAll,
        login,
        signup,
        logout,
        loadDemoMode,
        submitRide,
        submitParcel,
        cancelRideRequest,
        cancelParcelRequest,
        respondToCaptainDecision,
        completeCaptainRoute,
        clearRequests,
        setMapScenario,
        clearBanner,
        clearLocationToast,
      }}
    >
      {children}
    </RouteFusionContext.Provider>
  );
}

export function useRouteFusion() {
  const context = useContext(RouteFusionContext);
  if (!context) {
    throw new Error("useRouteFusion must be used within RouteFusionProvider.");
  }
  return context;
}
