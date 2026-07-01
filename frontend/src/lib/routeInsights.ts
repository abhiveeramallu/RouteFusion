import { formatDistance, formatMinutes } from "./format";
import type { Recommendation, RoutePoint } from "../types";

const DEFAULT_SPEED_KMPH = 28;
const STOP_BUFFER_MINUTES = 2;

export type RouteTimelineStop = {
  point: RoutePoint;
  segmentDistanceKm: number;
  cumulativeDistanceKm: number;
  estimatedMinutes: number;
};

export function sameRoutePoint(left: RoutePoint | null | undefined, right: RoutePoint | null | undefined) {
  if (!left || !right) {
    return false;
  }

  return (
    Math.abs(left.lat - right.lat) < 0.0001 &&
    Math.abs(left.lng - right.lng) < 0.0001 &&
    left.name === right.name
  );
}

export function normalizeRoutePoints(points: RoutePoint[]) {
  return points.filter((point, index, route) => index === 0 || !sameRoutePoint(point, route[index - 1]));
}

export function buildAcceptedRoutePoints(
  recommendation: Recommendation,
  currentLocation: RoutePoint | null,
) {
  const acceptedRoute =
    recommendation.decision_mode === "ride_only"
      ? recommendation.passenger_route
      : recommendation.decision_mode === "parcel_only"
        ? recommendation.parcel_route
        : recommendation.optimized_route;

  if (!acceptedRoute.length) {
    return [];
  }

  const withOrigin =
    currentLocation && !sameRoutePoint(currentLocation, acceptedRoute[0])
      ? [currentLocation, ...acceptedRoute]
      : acceptedRoute;

  return normalizeRoutePoints(withOrigin);
}

export function haversineDistanceKm(start: RoutePoint, end: RoutePoint) {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRadians(end.lat - start.lat);
  const dLng = toRadians(end.lng - start.lng);
  const startLat = toRadians(start.lat);
  const endLat = toRadians(end.lat);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(startLat) * Math.cos(endLat) * Math.sin(dLng / 2) ** 2;

  return 2 * earthRadiusKm * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function calculateRouteDistanceKm(points: RoutePoint[]) {
  if (points.length < 2) {
    return 0;
  }

  return points.slice(1).reduce((total, point, index) => {
    return total + haversineDistanceKm(points[index], point);
  }, 0);
}

export function estimateRouteMinutes(distanceKm: number, stopCount: number) {
  const driveMinutes = (distanceKm / DEFAULT_SPEED_KMPH) * 60;
  const stopMinutes = Math.max(0, stopCount - 2) * STOP_BUFFER_MINUTES;
  return driveMinutes + stopMinutes;
}

export function buildRouteTimeline(points: RoutePoint[]) {
  let cumulativeDistanceKm = 0;
  let cumulativeMinutes = 0;

  return normalizeRoutePoints(points).map((point, index, route) => {
    if (index > 0) {
      const segmentDistanceKm = haversineDistanceKm(route[index - 1], point);
      cumulativeDistanceKm += segmentDistanceKm;
      cumulativeMinutes += estimateRouteMinutes(segmentDistanceKm, 2);
    }

    if (index > 1) {
      cumulativeMinutes += STOP_BUFFER_MINUTES;
    }

    return {
      point,
      segmentDistanceKm: index === 0 ? 0 : haversineDistanceKm(route[index - 1], point),
      cumulativeDistanceKm,
      estimatedMinutes: cumulativeMinutes,
    } satisfies RouteTimelineStop;
  });
}

export function buildRouteSummary(points: RoutePoint[]) {
  const normalizedPoints = normalizeRoutePoints(points);
  const distanceKm = calculateRouteDistanceKm(normalizedPoints);
  const estimatedMinutes = estimateRouteMinutes(distanceKm, normalizedPoints.length);

  return {
    distanceKm,
    estimatedMinutes,
    distanceText: formatDistance(distanceKm),
    durationText: formatMinutes(estimatedMinutes),
  };
}
