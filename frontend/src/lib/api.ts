import type {
  AppSnapshotData,
  AuthResponse,
  CaptainDecision,
  DemoClearData,
  DashboardData,
  DemoLoadData,
  LoginFormValues,
  Parcel,
  ParcelFormValues,
  Recommendation,
  Ride,
  RideFormValues,
  SignupFormValues,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const rawMessage = await response.text();
    let message = rawMessage;

    try {
      const parsed = JSON.parse(rawMessage) as { detail?: string };
      if (parsed.detail) {
        message = parsed.detail;
      }
    } catch {
      // Ignore parse failures and use the raw response body instead.
    }

    throw new ApiError(response.status, message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function demoLogin() {
  return request<AuthResponse>("/auth/demo-login", {
    method: "POST",
  });
}

export async function signUp(payload: SignupFormValues) {
  return request<AuthResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function signIn(payload: LoginFormValues) {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function refreshAuthSession(refreshToken: string) {
  return request<AuthResponse>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutSession(token: string, refreshToken: string | null) {
  return request<{ message: string }>(
    "/auth/logout",
    {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    token,
  );
}

export async function loadDemo(token?: string) {
  return request<DemoLoadData>("/demo/load", { method: "GET" }, token);
}

export async function clearDemo(token?: string) {
  return request<DemoClearData>("/demo/clear", { method: "POST" }, token);
}

export async function getDashboard(token?: string) {
  return request<DashboardData>("/dashboard", { method: "GET" }, token);
}

export async function getSnapshot(token?: string) {
  return request<AppSnapshotData>("/snapshot", { method: "GET" }, token);
}

export async function pingHealth() {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, `Health check failed with status ${response.status}`);
  }
}

export async function getRecommendation(token?: string) {
  return request<Recommendation>("/captain/recommendations", { method: "GET" }, token);
}

export async function listRides(token?: string) {
  return request<Ride[]>("/ride", { method: "GET" }, token);
}

export async function listParcels(token?: string) {
  return request<Parcel[]>("/parcel", { method: "GET" }, token);
}

export async function createRide(payload: RideFormValues, token?: string) {
  return request<Ride>(
    "/ride",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export async function cancelRide(rideId: number, token?: string) {
  return request<{ message: string }>(
    `/ride/${rideId}`,
    {
      method: "DELETE",
    },
    token,
  );
}

export async function createParcel(payload: ParcelFormValues, token?: string) {
  return request<Parcel>(
    "/parcel",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export async function cancelParcel(parcelId: number, token?: string) {
  return request<{ message: string }>(
    `/parcel/${parcelId}`,
    {
      method: "DELETE",
    },
    token,
  );
}

export async function respondToRecommendation(decision: CaptainDecision, token?: string) {
  return request<{ message: string }>(
    "/captain/recommendations/respond",
    {
      method: "POST",
      body: JSON.stringify({ decision }),
    },
    token,
  );
}

export async function completeCaptainRecommendation(token?: string) {
  return request<{ message: string }>(
    "/captain/recommendations/complete",
    {
      method: "POST",
    },
    token,
  );
}
