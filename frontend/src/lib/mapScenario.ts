import { defaultVelloreLocation, selectionToRoutePoint } from "./constants";
import { formatCurrency, formatDistance, formatMinutes, humanizeRecommendation } from "./format";
import type {
  LocationSelection,
  MapScenario,
  ParcelDraftValues,
  Recommendation,
  RideDraftValues,
  RoutePoint,
} from "../types";

function safeCurrentLocation(currentLocation: RoutePoint | null) {
  return currentLocation ?? defaultVelloreLocation;
}

function resolveTwoPointRoute(pickup: LocationSelection, drop: LocationSelection) {
  const pickupPoint = selectionToRoutePoint(pickup);
  const dropPoint = selectionToRoutePoint(drop);

  if (!pickupPoint || !dropPoint) {
    return [];
  }

  return [pickupPoint, dropPoint];
}

function samePoint(left: RoutePoint, right: RoutePoint) {
  return (
    Math.abs(left.lat - right.lat) < 0.0001 &&
    Math.abs(left.lng - right.lng) < 0.0001
  );
}

function routeFromCurrentLocation(route: RoutePoint[], currentLocation: RoutePoint | null) {
  const origin = safeCurrentLocation(currentLocation);

  if (!route.length) {
    return [];
  }

  if (samePoint(route[0], origin)) {
    return route;
  }

  return [origin, ...route];
}

function recommendationBadge(recommendation: Recommendation) {
  if (!recommendation.route_confirmed) {
    if (recommendation.decision_mode === "ride_only") {
      return "Ride ready for captain";
    }
    if (recommendation.decision_mode === "parcel_only") {
      return "Parcel ready for captain";
    }
    return `${recommendation.efficiency_score}% match`;
  }

  if (recommendation.decision_mode === "ride_only") {
    return "Ride only confirmed";
  }
  if (recommendation.decision_mode === "parcel_only") {
    return "Parcel only confirmed";
  }
  if (recommendation.decision_mode === "combined") {
    return "Combined route confirmed";
  }
  return `${recommendation.efficiency_score}% match`;
}

function recommendationDockStats(recommendation: Recommendation) {
  if (recommendation.decision_mode === "ride_only") {
    return [
      { label: "Efficiency", value: `${recommendation.efficiency_score}%`, tone: "purple" as const },
      { label: "Ride fare", value: formatCurrency(recommendation.ride_customer_price), tone: "success" as const },
      { label: "Mode", value: "Ride only", tone: "neutral" as const },
    ];
  }

  if (recommendation.decision_mode === "parcel_only") {
    return [
      { label: "Efficiency", value: `${recommendation.efficiency_score}%`, tone: "purple" as const },
      { label: "Parcel fee", value: formatCurrency(recommendation.parcel_customer_price), tone: "accent" as const },
      { label: "Mode", value: "Parcel only", tone: "neutral" as const },
    ];
  }

  if (recommendation.decision_mode === "combined") {
    return [
      { label: "Efficiency", value: `${recommendation.efficiency_score}%`, tone: "purple" as const },
      { label: "Total", value: formatCurrency(recommendation.combined_customer_total), tone: "neutral" as const },
      { label: "Savings", value: formatCurrency(recommendation.estimated_customer_savings), tone: "success" as const },
    ];
  }

  return [
    { label: "Efficiency", value: `${recommendation.efficiency_score}%`, tone: "purple" as const },
    { label: "Extra distance", value: formatDistance(recommendation.extra_distance), tone: "accent" as const },
    { label: "Extra time", value: formatMinutes(recommendation.extra_time), tone: "success" as const },
  ];
}

export function createHomeScenario(currentLocation: RoutePoint | null): MapScenario {
  const origin = safeCurrentLocation(currentLocation);

  return {
    id: "home-info",
    title: "Operational territory",
    subtitle: "Centered on the VIT service area",
    passengerRoute: [],
    parcelRoute: [],
    optimizedRoute: [],
    captainLocation: origin,
    currentLocation: origin,
    badge: "Platform view",
    dockStats: [
      { label: "Zone", value: "VIT service area", tone: "neutral" },
      { label: "Mode", value: "Informational", tone: "accent" },
      { label: "Map", value: "Google ready", tone: "success" },
    ],
  };
}

export function createRideScenario(input: {
  form: RideDraftValues;
  currentLocation: RoutePoint | null;
}): MapScenario {
  const passengerRoute = resolveTwoPointRoute(
    input.form.pickup_location,
    input.form.drop_location,
  );
  const origin = safeCurrentLocation(input.currentLocation);

  return {
    id: "booking-ride",
    title: "Ride booking route",
    subtitle:
      passengerRoute.length === 2
        ? `${passengerRoute[0].name} to ${passengerRoute[1].name}`
        : "Search pickup and drop to preview the live passenger route",
    passengerRoute,
    parcelRoute: [],
    optimizedRoute: [],
    captainLocation: origin,
    currentLocation: origin,
    badge: input.form.ride_type,
    dockStats: [
      { label: "Passengers", value: String(input.form.passenger_count), tone: "success" },
      { label: "Ride type", value: input.form.ride_type, tone: "neutral" },
      { label: "Route", value: "Passenger", tone: "accent" },
    ],
  };
}

export function createParcelScenario(input: {
  form: ParcelDraftValues;
  currentLocation: RoutePoint | null;
}): MapScenario {
  const parcelRoute = resolveTwoPointRoute(
    input.form.pickup_location,
    input.form.drop_location,
  );
  const origin = safeCurrentLocation(input.currentLocation);

  return {
    id: "booking-parcel",
    title: "Parcel delivery route",
    subtitle:
      parcelRoute.length === 2
        ? `${parcelRoute[0].name} to ${parcelRoute[1].name}`
        : "Search pickup and drop to preview the live parcel route",
    passengerRoute: [],
    parcelRoute,
    optimizedRoute: [],
    captainLocation: origin,
    currentLocation: origin,
    badge: input.form.priority,
    dockStats: [
      { label: "Weight", value: `${input.form.parcel_weight} kg`, tone: "accent" },
      { label: "Type", value: input.form.parcel_type, tone: "neutral" },
      { label: "Priority", value: input.form.priority, tone: "success" },
    ],
  };
}

export function createCaptainScenario(
  recommendation: Recommendation | null,
  currentLocation: RoutePoint | null,
): MapScenario {
  const origin = safeCurrentLocation(currentLocation);

  if (!recommendation) {
    return {
      id: "captain-empty",
      title: "Captain view",
      subtitle: "Create requests to review a recommendation",
      passengerRoute: [],
      parcelRoute: [],
      optimizedRoute: [],
      captainLocation: origin,
      currentLocation: origin,
      badge: "Awaiting demand",
      dockStats: [
        { label: "Status", value: "Idle", tone: "neutral" },
        { label: "Zone", value: "VIT service area", tone: "accent" },
      ],
    };
  }

  const optimizedBaseRoute =
    recommendation.decision_mode === "ride_only"
      ? recommendation.passenger_route
      : recommendation.decision_mode === "parcel_only"
        ? recommendation.parcel_route
        : recommendation.optimized_route;

  return {
    id: "captain-live",
    title: recommendation.route_confirmed
      ? recommendation.decision_mode === "ride_only"
        ? "Ride-only route"
        : recommendation.decision_mode === "parcel_only"
          ? "Parcel-only route"
          : "Confirmed route"
      : recommendation.decision_mode === "ride_only"
        ? "Ride-ready route"
        : recommendation.decision_mode === "parcel_only"
          ? "Parcel-ready route"
          : "Captain recommendation",
    subtitle: recommendation.route_confirmed
      ? recommendation.confirmation_status
      : humanizeRecommendation(recommendation.recommendation),
    passengerRoute: recommendation.passenger_route,
    parcelRoute: recommendation.parcel_route,
    optimizedRoute: routeFromCurrentLocation(optimizedBaseRoute, currentLocation),
    captainLocation: origin,
    currentLocation: origin,
    badge: recommendationBadge(recommendation),
    dockStats: recommendationDockStats(recommendation),
  };
}

export function createLiveMapScenario(
  recommendation: Recommendation | null,
  currentLocation: RoutePoint | null,
): MapScenario {
  if (!recommendation?.route_confirmed) {
    const origin = safeCurrentLocation(currentLocation);

    return {
      id: "live-map-empty",
      title: "Awaiting confirmed route",
      subtitle: "Accept a ride, parcel, or combined route to start live tracking",
      passengerRoute: [],
      parcelRoute: [],
      optimizedRoute: [],
      captainLocation: origin,
      currentLocation: origin,
      badge: "Idle",
      dockStats: [
        { label: "Status", value: "Waiting", tone: "neutral" },
        { label: "Zone", value: "VIT service area", tone: "accent" },
      ],
    };
  }

  const scenario = createCaptainScenario(recommendation, currentLocation);

  return {
    ...scenario,
    id: "live-map",
    title: recommendation?.route_confirmed
      ? recommendation.decision_mode === "ride_only"
        ? "Live ride-only route"
        : recommendation.decision_mode === "parcel_only"
          ? "Live parcel-only route"
          : "Confirmed live route"
      : "Live optimized route",
    subtitle: recommendation?.route_confirmed
      ? recommendation.confirmation_status
      : "Google road routing in progress",
    badge: recommendation?.route_confirmed
      ? recommendationBadge(recommendation)
      : "Live operations",
  };
}
