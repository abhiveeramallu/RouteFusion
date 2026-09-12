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
  getNamedCaptains,
  getSnapshot,
  logoutSession,
  loadDemo,
  pingHealth,
  respondToRecommendation,
  runConcurrencyStressTest,
  seedFleet,
  signIn,
  signUp,
} from "../lib/api";
import { defaultVelloreLocation } from "../lib/constants";
import type {
  AuthResponse,
  CaptainDecision,
  ConcurrencyStressData,
  DashboardData,
  Driver,
  LoginFormValues,
  MapScenario,
  Parcel,
  ParcelFormValues,
  Recommendation,
  Ride,
  RideFormValues,
  RoutePoint,
  SeedFleetData,
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
  namedCaptains: Driver[];
  selectedCaptainId: number | null;
  activeCaptainId: number | null;
  selectCaptain: (driverId: number | null) => Promise<void>;
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
  seedDemoFleet: (captains: number, rides: number, parcels: number) => Promise<SeedFleetData>;
  runStressTest: (rideId: number, parcelId: number, attempts: number) => Promise<ConcurrencyStressData>;
  setMapScenario: (scenario: MapScenario | null) => void;
  clearBanner: () => void;
  clearLocationToast: () => void;
  clearRequests: () => Promise<void>;
};

const RouteFusionContext = createContext<RouteFusionContextValue | undefined>(undefined);

function driverRoutePoint(driver: Driver | null | undefined): RoutePoint | null {
  if (!driver) {
    return null;
  }

  return {
    name: driver.display_name,
    lat: driver.current_lat,
    lng: driver.current_lng,
  };
}

function recommendationDriverLocation(recommendation: Recommendation | null): RoutePoint | null {
  return driverRoutePoint(recommendation?.driver);
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

async function fetchSnapshot(token?: string | null, driverId?: number | null) {
  return getSnapshot(token ?? undefined, driverId);
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
  const [namedCaptains, setNamedCaptains] = useState<Driver[]>([]);
  const [selectedCaptainId, setSelectedCaptainId] = useState<number | null>(null);

  function applySession(session: AuthResponse) {
    setToken(session.access_token);
    setRefreshToken(session.refresh_token);
    setUser(session.user);
    writeStoredSession(session);
    // A captain-switcher override picked before logging in must not keep
    // shadowing this session's own driver on every later refresh.
    setSelectedCaptainId(null);
  }

  function clearSessionState() {
    setToken(null);
    setRefreshToken(null);
    setUser(publicUser);
    writeStoredSession(null);
    setSelectedCaptainId(null);
  }

  function applySnapshot(
    snapshot: {
      dashboard: DashboardData | null;
      recommendation: Recommendation | null;
      driver?: Driver | null;
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
        // Even with no active recommendation, /snapshot still reports this
        // captain's own driver row — keeps their marker sitting at their
        // real (just-updated, if a route just completed) position instead
        // of falling back to a generic default the moment their queue is
        // empty.
        ?? driverRoutePoint(snapshot.driver)
        ?? fallbackLocation
        ?? defaultVelloreLocation,
    );
  }

  async function refreshAll() {
    setRefreshing(true);
    setError(null);
    try {
      const snapshot = await fetchSnapshot(token, selectedCaptainId);
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
      const snapshot = await fetchSnapshot(token);
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
      const snapshot = await fetchSnapshot(session.access_token);
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
      const snapshot = await fetchSnapshot(session.access_token);
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
      const response = await respondToRecommendation(decision, token ?? undefined, selectedCaptainId);
      setBannerMessage(response.message);
      await refreshAll();
    } catch (decisionError) {
      // 400 here specifically means this decision no longer matches what
      // build_recommendation would compute right now (e.g. accept_both was
      // clicked but another captain just took the parcel half of the same
      // bundle) — a staleness case exactly like 404/409, not a real
      // validation error the captain caused, so it gets the same
      // refresh-and-recover treatment.
      if (
        decisionError instanceof ApiError &&
        (decisionError.status === 404 || decisionError.status === 409 || decisionError.status === 400)
      ) {
        setBannerMessage(
          decisionError.status === 409
            ? "Another captain just took this request. RouteFusion refreshed the queue."
            : "Recommendation already changed. RouteFusion refreshed the queue.",
        );
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
      const response = await completeCaptainRecommendation(token ?? undefined, selectedCaptainId);
      setBannerMessage(response.message);
      const snapshot = await fetchSnapshot(token, selectedCaptainId);
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

  async function seedDemoFleet(captains: number, rides: number, parcels: number) {
    setError(null);
    try {
      const result = await seedFleet({ captains, rides, parcels }, token ?? undefined);
      setBannerMessage(result.message);
      await refreshAll();
      return result;
    } catch (seedError) {
      setError(seedError instanceof Error ? seedError.message : "Unable to seed the demo fleet.");
      throw seedError;
    }
  }

  async function runStressTest(rideId: number, parcelId: number, attempts: number) {
    setError(null);
    try {
      const result = await runConcurrencyStressTest({ ride_id: rideId, parcel_id: parcelId, attempts }, token ?? undefined);
      setBannerMessage(result.message);
      await refreshAll();
      return result;
    } catch (stressError) {
      setError(stressError instanceof Error ? stressError.message : "Unable to run the concurrency stress test.");
      throw stressError;
    }
  }

  async function selectCaptain(driverId: number | null) {
    setError(null);
    setRefreshing(true);
    try {
      setSelectedCaptainId(driverId);
      const snapshot = await fetchSnapshot(token, driverId);
      applySnapshot(snapshot);
    } catch (selectError) {
      setError(selectError instanceof Error ? selectError.message : "Unable to load that captain's recommendation.");
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function clearRequests() {
    setRefreshing(true);
    setError(null);
    try {
      const response = await clearDemo();
      setBannerMessage(response.message);
      const snapshot = await fetchSnapshot(token).catch(() => ({
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
        const snapshot = await fetchSnapshot(storedSession?.access_token);
        applySnapshot(snapshot);
        const captains = await getNamedCaptains().catch(() => []);
        setNamedCaptains(captains);
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

  const activeCaptainId = selectedCaptainId ?? recommendation?.driver.id ?? null;

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
        namedCaptains,
        selectedCaptainId,
        activeCaptainId,
        selectCaptain,
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
        seedDemoFleet,
        runStressTest,
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
