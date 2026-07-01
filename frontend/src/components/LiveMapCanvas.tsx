import { DirectionsRenderer, GoogleMap, MarkerF, PolylineF } from "@react-google-maps/api";
import { LoaderCircle, LocateFixed, MapPinned } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { defaultVelloreLocation } from "../lib/constants";
import {
  freeServiceModeMessage,
  useGoogleMapsLoader,
} from "../lib/googleMaps";
import { buildRouteSummary, haversineDistanceKm, normalizeRoutePoints } from "../lib/routeInsights";
import type { MapScenario, MapScenarioStat, RoutePoint } from "../types";
import { DockStat } from "./DockStat";
import { MapLegend } from "./MapLegend";

type LiveMapCanvasProps = {
  scenario: MapScenario;
};

type PreviewViewport = {
  zoom: number;
  originX: number;
  originY: number;
};

type DirectionsSummary = {
  distanceMeters: number;
  durationSeconds: number;
  distanceText: string;
  durationText: string;
};

type DirectionsOverlayState = {
  directions: google.maps.DirectionsResult | null;
  requested: boolean;
  status: string | null;
  summary: DirectionsSummary | null;
};

declare const google: typeof window.google;

const PREVIEW_WIDTH = 1200;
const PREVIEW_HEIGHT = 860;
const PREVIEW_PADDING = 90;
const TILE_SIZE = 256;
const MIN_MERCATOR_LAT = -85.05112878;
const MAX_MERCATOR_LAT = 85.05112878;
const GOOGLE_MAPS_WHITE_THEME: google.maps.MapTypeStyle[] = [
  {
    elementType: "geometry",
    stylers: [{ color: "#f7f7f8" }],
  },
  {
    elementType: "labels.icon",
    stylers: [{ visibility: "off" }],
  },
  {
    elementType: "labels.text.fill",
    stylers: [{ color: "#667085" }],
  },
  {
    elementType: "labels.text.stroke",
    stylers: [{ color: "#ffffff" }],
  },
  {
    featureType: "administrative",
    elementType: "geometry.stroke",
    stylers: [{ color: "#d9dde4" }],
  },
  {
    featureType: "poi",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#ffffff" }],
  },
  {
    featureType: "road",
    elementType: "geometry.stroke",
    stylers: [{ color: "#e6e8ec" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#eef2ff" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry.stroke",
    stylers: [{ color: "#d9defa" }],
  },
  {
    featureType: "transit",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#edf3ff" }],
  },
];

function serializePoints(points: RoutePoint[]) {
  return points.map((point) => `${point.lat}:${point.lng}:${point.name}`).join("|");
}

function uniquePoints(points: RoutePoint[]) {
  return points.filter(
    (point, index, list) =>
      list.findIndex(
        (entry) =>
          Math.abs(entry.lat - point.lat) < 0.0001 &&
          Math.abs(entry.lng - point.lng) < 0.0001 &&
          entry.name === point.name,
      ) === index,
  );
}

function allScenarioPoints(scenario: MapScenario) {
  const points = uniquePoints([
    ...(scenario.passengerRoute ?? []),
    ...(scenario.parcelRoute ?? []),
    ...(scenario.optimizedRoute ?? []),
    ...(scenario.currentLocation ? [scenario.currentLocation] : []),
  ]);

  return points.length ? points : [scenario.currentLocation ?? defaultVelloreLocation];
}

function clampMercatorLatitude(lat: number) {
  return Math.min(MAX_MERCATOR_LAT, Math.max(MIN_MERCATOR_LAT, lat));
}

function latLngToWorldPoint(point: RoutePoint, zoom: number) {
  const scale = TILE_SIZE * 2 ** zoom;
  const lat = clampMercatorLatitude(point.lat);
  const sinLat = Math.sin((lat * Math.PI) / 180);

  return {
    x: ((point.lng + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale,
  };
}

function chooseTileZoom(points: RoutePoint[]) {
  if (points.length <= 1) {
    return 14;
  }

  for (let zoom = 16; zoom >= 1; zoom -= 1) {
    const projected = points.map((point) => latLngToWorldPoint(point, zoom));
    const minX = Math.min(...projected.map((point) => point.x));
    const maxX = Math.max(...projected.map((point) => point.x));
    const minY = Math.min(...projected.map((point) => point.y));
    const maxY = Math.max(...projected.map((point) => point.y));

    if (
      maxX - minX <= PREVIEW_WIDTH - PREVIEW_PADDING * 2 &&
      maxY - minY <= PREVIEW_HEIGHT - PREVIEW_PADDING * 2
    ) {
      return zoom;
    }
  }

  return 1;
}

function buildPreviewViewport(points: RoutePoint[]): PreviewViewport {
  const zoom = chooseTileZoom(points);
  const projected = points.map((point) => latLngToWorldPoint(point, zoom));
  const minX = Math.min(...projected.map((point) => point.x));
  const maxX = Math.max(...projected.map((point) => point.x));
  const minY = Math.min(...projected.map((point) => point.y));
  const maxY = Math.max(...projected.map((point) => point.y));
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const originX = centerX - PREVIEW_WIDTH / 2;
  const originY = centerY - PREVIEW_HEIGHT / 2;

  return {
    zoom,
    originX,
    originY,
  };
}

function projectPoint(point: RoutePoint, viewport: PreviewViewport) {
  const worldPoint = latLngToWorldPoint(point, viewport.zoom);

  return {
    x: worldPoint.x - viewport.originX,
    y: worldPoint.y - viewport.originY,
  };
}

function pointsToPolyline(points: RoutePoint[], viewport: PreviewViewport) {
  return points
    .map((point) => {
      const projected = projectPoint(point, viewport);
      return `${projected.x},${projected.y}`;
    })
    .join(" ");
}

function pointsToMapPath(points: RoutePoint[]) {
  return points.map((point) => ({ lat: point.lat, lng: point.lng }));
}

function summarizeDirections(
  directions: google.maps.DirectionsResult,
): DirectionsSummary | null {
  const route = directions.routes?.[0];

  if (!route?.legs?.length) {
    return null;
  }

  const distanceMeters = route.legs.reduce(
    (sum, leg) => sum + (leg.distance?.value ?? 0),
    0,
  );
  const durationSeconds = route.legs.reduce(
    (sum, leg) => sum + (leg.duration?.value ?? 0),
    0,
  );

  return {
    distanceMeters,
    durationSeconds,
    distanceText:
      distanceMeters >= 1000
        ? `${(distanceMeters / 1000).toFixed(1)} km`
        : `${distanceMeters} m`,
    durationText:
      durationSeconds >= 3600
        ? `${Math.round(durationSeconds / 60)} min`
        : `${Math.max(1, Math.round(durationSeconds / 60))} min`,
  };
}

function pickAnimatedRoute(scenario: MapScenario) {
  if (scenario.optimizedRoute.length > 1) {
    return normalizeRoutePoints(scenario.optimizedRoute);
  }

  if (scenario.passengerRoute.length > 1) {
    return normalizeRoutePoints(scenario.passengerRoute);
  }

  if (scenario.parcelRoute.length > 1) {
    return normalizeRoutePoints(scenario.parcelRoute);
  }

  return [];
}

function buildFallbackDirectionsSummary(points: RoutePoint[]): DirectionsSummary | null {
  if (points.length < 2) {
    return null;
  }

  const summary = buildRouteSummary(points);

  return {
    distanceMeters: Math.round(summary.distanceKm * 1000),
    durationSeconds: Math.round(summary.estimatedMinutes * 60),
    distanceText: summary.distanceText,
    durationText: summary.durationText,
  };
}

function interpolateRoutePoint(points: RoutePoint[], progress: number) {
  const route = normalizeRoutePoints(points);

  if (!route.length) {
    return null;
  }

  if (route.length === 1) {
    return route[0];
  }

  const segmentDistances = route.slice(1).map((point, index) => haversineDistanceKm(route[index], point));
  const totalDistance = segmentDistances.reduce((sum, value) => sum + value, 0);

  if (totalDistance <= 0) {
    return route[0];
  }

  const targetDistance = totalDistance * progress;
  let travelled = 0;

  for (let index = 1; index < route.length; index += 1) {
    const segmentDistance = segmentDistances[index - 1];

    if (travelled + segmentDistance >= targetDistance) {
      const ratio = (targetDistance - travelled) / Math.max(segmentDistance, 0.0001);
      const start = route[index - 1];
      const end = route[index];
      return {
        name: `${start.name} to ${end.name}`,
        lat: start.lat + (end.lat - start.lat) * ratio,
        lng: start.lng + (end.lng - start.lng) * ratio,
      };
    }

    travelled += segmentDistance;
  }

  return route[route.length - 1];
}

function useRouteTraversal(points: RoutePoint[]) {
  const serialized = serializePoints(points);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (points.length < 2) {
      setProgress(0);
      return;
    }

    const totalMinutes = buildRouteSummary(points).estimatedMinutes;
    const durationMs = Math.max(6000, Math.min(18000, totalMinutes * 900));
    let frameId = 0;
    let startedAt = 0;

    const animate = (timestamp: number) => {
      if (!startedAt) {
        startedAt = timestamp;
      }

      const elapsed = (timestamp - startedAt) % durationMs;
      setProgress(elapsed / durationMs);
      frameId = window.requestAnimationFrame(animate);
    };

    frameId = window.requestAnimationFrame(animate);

    return () => window.cancelAnimationFrame(frameId);
  }, [serialized]);

  return progress;
}

function useDirectionsOverlay(points: RoutePoint[], enabled: boolean) {
  const serialized = serializePoints(points);
  const [state, setState] = useState<DirectionsOverlayState>({
    directions: null,
    requested: false,
    status: null,
    summary: null,
  });

  useEffect(() => {
    if (!enabled || points.length < 2 || typeof google === "undefined") {
      setState({
        directions: null,
        requested: false,
        status: null,
        summary: null,
      });
      return;
    }

    let cancelled = false;
    const directionsService = new google.maps.DirectionsService();

    directionsService.route(
      {
        origin: { lat: points[0].lat, lng: points[0].lng },
        destination: {
          lat: points[points.length - 1].lat,
          lng: points[points.length - 1].lng,
        },
        waypoints: points.slice(1, -1).map((point) => ({
          location: { lat: point.lat, lng: point.lng },
          stopover: true,
        })),
        optimizeWaypoints: false,
        travelMode: google.maps.TravelMode.DRIVING,
      },
      (result, status) => {
        if (cancelled) {
          return;
        }

        if (status === "OK" && result) {
          setState({
            directions: result,
            requested: true,
            status,
            summary: summarizeDirections(result),
          });
          return;
        }

        setState({
          directions: null,
          requested: true,
          status,
          summary: null,
        });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [enabled, serialized]);

  return state;
}

function buildSummaryStats(
  routeSummary: DirectionsSummary | null,
  scenarioStats: MapScenarioStat[],
) {
  const summaryStats: MapScenarioStat[] = routeSummary
    ? [
        { label: "Distance", value: routeSummary.distanceText, tone: "neutral" },
        { label: "ETA", value: routeSummary.durationText, tone: "accent" },
      ]
    : [];

  return [...summaryStats, ...scenarioStats].slice(0, 4);
}

function directionsStatusMessage(statuses: Array<string | null>) {
  if (statuses.includes("REQUEST_DENIED")) {
    return "Google road routing is unavailable on this key. Showing straight-line route preview on the map.";
  }
  if (statuses.includes("ZERO_RESULTS")) {
    return "Google Maps could not find a drivable road route. Showing straight-line route preview on the map.";
  }
  if (statuses.includes("OVER_QUERY_LIMIT")) {
    return "Google Maps quota was exceeded for the current browser key. Showing straight-line route preview on the map.";
  }
  if (statuses.includes("UNKNOWN_ERROR")) {
    return "Google Maps hit a temporary routing error. Showing straight-line route preview on the map.";
  }
  return "Google Maps is still preparing a road-following route.";
}

function fallbackStatusMessage(warningMessage?: string) {
  if (warningMessage) {
    return `${warningMessage} Clean preview map is active.`;
  }

  return "Clean preview map is active. Straight-line route preview is active.";
}

function PreviewCanvas({
  scenario,
  routeSummary,
  warningMessage,
}: {
  scenario: MapScenario;
  routeSummary: DirectionsSummary | null;
  warningMessage?: string;
}) {
  const pointPool = allScenarioPoints(scenario);
  const animatedRoute = useMemo(() => pickAnimatedRoute(scenario), [scenario]);
  const traversalProgress = useRouteTraversal(animatedRoute);
  const traversingPoint = useMemo(
    () => interpolateRoutePoint(animatedRoute, traversalProgress),
    [animatedRoute, traversalProgress],
  );
  const fallbackViewport = useMemo(() => buildPreviewViewport(pointPool), [pointPool]);
  const displayedStats = buildSummaryStats(
    routeSummary ?? buildFallbackDirectionsSummary(animatedRoute),
    scenario.dockStats,
  );
  const hasAnyRoute =
    scenario.passengerRoute.length > 1 ||
    scenario.parcelRoute.length > 1 ||
    scenario.optimizedRoute.length > 1;

  const labeledPoints = [
    scenario.currentLocation
      ? { point: scenario.currentLocation, label: "H", title: "VIT service hub", fill: "#111111" }
      : null,
    scenario.passengerRoute[0]
      ? { point: scenario.passengerRoute[0], label: "P", title: "Passenger pickup", fill: "#22C55E" }
      : null,
    scenario.passengerRoute[1]
      ? { point: scenario.passengerRoute[1], label: "D", title: "Passenger drop", fill: "#22C55E" }
      : null,
    scenario.parcelRoute[0]
      ? { point: scenario.parcelRoute[0], label: "X", title: "Parcel pickup", fill: "#3B82F6" }
      : null,
    scenario.parcelRoute[1]
      ? { point: scenario.parcelRoute[1], label: "Y", title: "Parcel drop", fill: "#3B82F6" }
      : null,
  ].filter(Boolean) as Array<{
    point: RoutePoint;
    label: string;
    title: string;
    fill: string;
  }>;

  return (
    <div className="relative h-full min-h-[440px] overflow-hidden rounded-[32px] border border-[#e7eaee] bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] shadow-[0_25px_60px_rgba(15,23,42,0.12)]">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(180deg,#ffffff_0%,#f6f8fb_100%)]" />
        <div className="absolute inset-0 opacity-70 [background-image:linear-gradient(rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.12)_1px,transparent_1px)] [background-size:44px_44px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(91,91,239,0.06),transparent_28%),radial-gradient(circle_at_bottom_left,rgba(34,197,94,0.05),transparent_30%)]" />
        <div className="absolute inset-y-0 left-[18%] w-px bg-[linear-gradient(180deg,transparent,rgba(203,213,225,0.7),transparent)]" />
        <div className="absolute inset-y-0 right-[22%] w-px bg-[linear-gradient(180deg,transparent,rgba(203,213,225,0.7),transparent)]" />
        <div className="absolute left-0 right-0 top-[26%] h-px bg-[linear-gradient(90deg,transparent,rgba(203,213,225,0.7),transparent)]" />
        <div className="absolute left-0 right-0 bottom-[24%] h-px bg-[linear-gradient(90deg,transparent,rgba(203,213,225,0.7),transparent)]" />
      </div>
      <div className="absolute left-5 right-5 top-5 z-10 flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="rounded-[24px] bg-white/94 px-5 py-4 shadow-sm backdrop-blur">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">
            {scenario.badge ?? "Service mode"}
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">
            {scenario.title}
          </h2>
          <p className="mt-1 text-sm text-[#6b7280]">{scenario.subtitle}</p>
        </div>
        {hasAnyRoute ? <MapLegend /> : null}
      </div>

      <svg viewBox="0 0 1200 860" className="relative h-full w-full">
        {scenario.passengerRoute.length > 1 ? (
          <polyline
            points={pointsToPolyline(scenario.passengerRoute, fallbackViewport)}
            fill="none"
            stroke="#22C55E"
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}

        {scenario.parcelRoute.length > 1 ? (
          <polyline
            points={pointsToPolyline(scenario.parcelRoute, fallbackViewport)}
            fill="none"
            stroke="#3B82F6"
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}

        {scenario.optimizedRoute.length > 1 ? (
          <polyline
            points={pointsToPolyline(scenario.optimizedRoute, fallbackViewport)}
            fill="none"
            stroke="#5B5BEF"
            strokeWidth="13"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.95"
          />
        ) : null}

        {animatedRoute.length > 1 ? (
          <polyline
            points={pointsToPolyline(animatedRoute, fallbackViewport)}
            fill="none"
            stroke="rgba(17,24,39,0.45)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="18 12"
          >
            <animate
              attributeName="stroke-dashoffset"
              values="0;-60"
              dur="1.4s"
              repeatCount="indefinite"
            />
          </polyline>
        ) : null}

        {labeledPoints.map(({ point, label, title, fill }) => {
          const projected = projectPoint(point, fallbackViewport);
          return (
            <g key={`${title}-${point.name}`}>
              <circle cx={projected.x} cy={projected.y} r="14" fill={fill} opacity="0.18">
                <animate attributeName="r" values="14;24;14" dur="1.8s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.25;0;0.25" dur="1.8s" repeatCount="indefinite" />
              </circle>
              <circle cx={projected.x} cy={projected.y} r="18" fill="white" />
              <circle cx={projected.x} cy={projected.y} r="14" fill={fill} opacity="0.96" />
              <text
                x={projected.x}
                y={projected.y + 4}
                textAnchor="middle"
                fontSize="13"
                fontFamily="Inter, sans-serif"
                fill="#ffffff"
                fontWeight="700"
              >
                {label}
              </text>
            </g>
          );
        })}

        {traversingPoint ? (
          <g>
            <circle
              cx={projectPoint(traversingPoint, fallbackViewport).x}
              cy={projectPoint(traversingPoint, fallbackViewport).y}
              r="12"
              fill="rgba(91,91,239,0.20)"
            >
              <animate attributeName="r" values="12;22;12" dur="1.2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.3;0;0.3" dur="1.2s" repeatCount="indefinite" />
            </circle>
            <circle
              cx={projectPoint(traversingPoint, fallbackViewport).x}
              cy={projectPoint(traversingPoint, fallbackViewport).y}
              r="7"
              fill="#111111"
              stroke="#ffffff"
              strokeWidth="3"
            />
          </g>
        ) : null}
      </svg>

      <div className="absolute bottom-5 left-5 right-5 z-10 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-wrap gap-3">
          {displayedStats.map((stat) => (
            <DockStat key={`${stat.label}-${stat.value}`} stat={stat} />
          ))}
        </div>
        <div className="rounded-[22px] bg-white/94 px-4 py-3 text-sm text-[#4b5563] shadow-sm backdrop-blur">
          <div className="flex items-center gap-2">
            {hasAnyRoute ? (
              <MapPinned className="h-4 w-4 text-[#5B5BEF]" />
            ) : (
              <LocateFixed className="h-4 w-4 text-[#5B5BEF]" />
            )}
            {fallbackStatusMessage(warningMessage)}
          </div>
        </div>
      </div>
    </div>
  );
}

export function LiveMapCanvas({ scenario }: LiveMapCanvasProps) {
  const { googleMapsApiKey, isLoaded, isReady, statusMessage } = useGoogleMapsLoader();
  const mapRef = useRef<google.maps.Map | null>(null);
  const animatedRoute = useMemo(() => pickAnimatedRoute(scenario), [scenario]);
  const traversalProgress = useRouteTraversal(animatedRoute);
  const traversingPoint = useMemo(
    () => interpolateRoutePoint(animatedRoute, traversalProgress),
    [animatedRoute, traversalProgress],
  );

  const passengerOverlay = useDirectionsOverlay(
    scenario.passengerRoute,
    Boolean(googleMapsApiKey && isReady),
  );
  const parcelOverlay = useDirectionsOverlay(
    scenario.parcelRoute,
    Boolean(googleMapsApiKey && isReady),
  );
  const optimizedOverlay = useDirectionsOverlay(
    scenario.optimizedRoute,
    Boolean(googleMapsApiKey && isReady),
  );

  const pointPool = useMemo(() => allScenarioPoints(scenario), [scenario]);
  const hasAnyRoute =
    scenario.passengerRoute.length > 1 ||
    scenario.parcelRoute.length > 1 ||
    scenario.optimizedRoute.length > 1;

  const primaryOverlay =
    scenario.optimizedRoute.length > 1
      ? optimizedOverlay
      : scenario.passengerRoute.length > 1
        ? passengerOverlay
        : scenario.parcelRoute.length > 1
          ? parcelOverlay
          : null;

  const fallbackSummary = useMemo(
    () => buildFallbackDirectionsSummary(animatedRoute),
    [animatedRoute],
  );
  const displayedStats = buildSummaryStats(primaryOverlay?.summary ?? fallbackSummary, scenario.dockStats);
  const awaitingDirections =
    hasAnyRoute &&
    [
      { overlay: passengerOverlay, points: scenario.passengerRoute },
      { overlay: parcelOverlay, points: scenario.parcelRoute },
      { overlay: optimizedOverlay, points: scenario.optimizedRoute },
    ].some(({ overlay, points }) => points.length > 1 && overlay.requested === false);

  const routeStatus = [passengerOverlay, parcelOverlay, optimizedOverlay]
    .filter((overlay) => overlay.requested && !overlay.directions)
    .map((overlay) => overlay.status);

  useEffect(() => {
    if (!mapRef.current || typeof google === "undefined") {
      return;
    }

    if (!pointPool.length) {
      mapRef.current.setCenter(defaultVelloreLocation);
      mapRef.current.setZoom(13);
      return;
    }

    if (pointPool.length === 1) {
      mapRef.current.setCenter({ lat: pointPool[0].lat, lng: pointPool[0].lng });
      mapRef.current.setZoom(13);
      return;
    }

    const bounds = new google.maps.LatLngBounds();
    pointPool.forEach((point) => bounds.extend({ lat: point.lat, lng: point.lng }));
    mapRef.current.fitBounds(bounds, 80);
  }, [pointPool]);

  const center = useMemo(() => {
    const defaultCenter = scenario.currentLocation ?? defaultVelloreLocation;

    if (!pointPool.length) {
      return defaultCenter;
    }

    return {
      lat: pointPool.reduce((sum, point) => sum + point.lat, 0) / pointPool.length,
      lng: pointPool.reduce((sum, point) => sum + point.lng, 0) / pointPool.length,
    };
  }, [pointPool, scenario.currentLocation]);

  if (!googleMapsApiKey) {
    return (
      <PreviewCanvas
        scenario={scenario}
        routeSummary={primaryOverlay?.summary ?? fallbackSummary}
      />
    );
  }

  if (statusMessage && !isReady) {
    return (
      <PreviewCanvas
        scenario={scenario}
        routeSummary={primaryOverlay?.summary ?? fallbackSummary}
        warningMessage="Google Maps base layer is unavailable right now. Showing straight-line route preview instead."
      />
    );
  }

  if (!isLoaded) {
    return (
      <div className="grid h-full min-h-[440px] place-items-center rounded-[32px] border border-[#e7eaee] bg-white shadow-[0_25px_60px_rgba(15,23,42,0.12)]">
        <div className="text-center">
          <LoaderCircle className="mx-auto h-10 w-10 animate-spin text-[#5B5BEF]" />
          <p className="mt-4 text-sm font-medium text-[#111827]">Loading Google Maps</p>
          <p className="mt-2 text-sm text-[#6b7280]">Preparing live road-following directions.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-[440px] overflow-hidden rounded-[32px] border border-[#e7eaee] shadow-[0_25px_60px_rgba(15,23,42,0.12)]">
      <div className="absolute left-5 right-5 top-5 z-10 flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="rounded-[24px] bg-white/94 px-5 py-4 shadow-sm backdrop-blur">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">
            {scenario.badge ?? "Live map"}
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">
            {scenario.title}
          </h2>
          <p className="mt-1 text-sm text-[#6b7280]">{scenario.subtitle}</p>
        </div>
        {hasAnyRoute ? <MapLegend /> : null}
      </div>

      <GoogleMap
        center={center}
        zoom={13}
        mapContainerStyle={{ width: "100%", height: "100%" }}
        onLoad={(map) => {
          mapRef.current = map;
        }}
        options={{
          gestureHandling: "greedy",
          styles: GOOGLE_MAPS_WHITE_THEME,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
        }}
      >
        {passengerOverlay.directions ? (
          <DirectionsRenderer
            directions={passengerOverlay.directions}
            options={{
              suppressMarkers: true,
              preserveViewport: true,
              polylineOptions: {
                strokeColor: "#22C55E",
                strokeOpacity: 0.92,
                strokeWeight: 5,
              },
            }}
          />
        ) : passengerOverlay.requested && scenario.passengerRoute.length > 1 ? (
          <PolylineF
            path={pointsToMapPath(scenario.passengerRoute)}
            options={{
              strokeColor: "#22C55E",
              strokeOpacity: 0.92,
              strokeWeight: 5,
            }}
          />
        ) : null}

        {parcelOverlay.directions ? (
          <DirectionsRenderer
            directions={parcelOverlay.directions}
            options={{
              suppressMarkers: true,
              preserveViewport: true,
              polylineOptions: {
                strokeColor: "#3B82F6",
                strokeOpacity: 0.92,
                strokeWeight: 5,
              },
            }}
          />
        ) : parcelOverlay.requested && scenario.parcelRoute.length > 1 ? (
          <PolylineF
            path={pointsToMapPath(scenario.parcelRoute)}
            options={{
              strokeColor: "#3B82F6",
              strokeOpacity: 0.92,
              strokeWeight: 5,
            }}
          />
        ) : null}

        {optimizedOverlay.directions ? (
          <DirectionsRenderer
            directions={optimizedOverlay.directions}
            options={{
              suppressMarkers: true,
              preserveViewport: true,
              polylineOptions: {
                strokeColor: "#5B5BEF",
                strokeOpacity: 0.95,
                strokeWeight: 6,
              },
            }}
          />
        ) : optimizedOverlay.requested && scenario.optimizedRoute.length > 1 ? (
          <PolylineF
            path={pointsToMapPath(scenario.optimizedRoute)}
            options={{
              strokeColor: "#5B5BEF",
              strokeOpacity: 0.95,
              strokeWeight: 6,
            }}
          />
        ) : null}

        {scenario.passengerRoute[0] ? (
          <MarkerF position={scenario.passengerRoute[0]} label="P" title="Passenger pickup" />
        ) : null}
        {scenario.passengerRoute[1] ? (
          <MarkerF position={scenario.passengerRoute[1]} label="D" title="Passenger drop" />
        ) : null}
        {scenario.parcelRoute[0] ? (
          <MarkerF position={scenario.parcelRoute[0]} label="X" title="Parcel pickup" />
        ) : null}
        {scenario.parcelRoute[1] ? (
          <MarkerF position={scenario.parcelRoute[1]} label="Y" title="Parcel drop" />
        ) : null}
        {scenario.currentLocation ? (
          <MarkerF
            position={scenario.currentLocation}
            label="H"
            title="VIT service hub"
            icon={{
              path: google.maps.SymbolPath.CIRCLE,
              fillColor: "#111111",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 2,
              scale: 8,
            }}
          />
        ) : null}
        {traversingPoint ? (
          <MarkerF
            position={traversingPoint}
            title="Active route traversal"
            icon={{
              path: google.maps.SymbolPath.CIRCLE,
              fillColor: "#111111",
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeWeight: 3,
              scale: 7,
            }}
          />
        ) : null}
      </GoogleMap>

      <div className="absolute bottom-5 left-5 right-5 z-10 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-wrap gap-3">
          {displayedStats.map((stat) => (
            <DockStat key={`${stat.label}-${stat.value}`} stat={stat} />
          ))}
        </div>
        <div className="rounded-[22px] bg-white/94 px-4 py-3 text-sm text-[#4b5563] shadow-sm backdrop-blur">
          <div className="flex items-center gap-2">
            {hasAnyRoute ? (
              <MapPinned className="h-4 w-4 text-[#5B5BEF]" />
            ) : (
              <LocateFixed className="h-4 w-4 text-[#5B5BEF]" />
            )}
            {routeStatus.length
              ? directionsStatusMessage(routeStatus)
                : awaitingDirections
                  ? "Preparing road-following route..."
                  : hasAnyRoute
                    ? "Road-snapped Google Maps directions active"
                    : "VIT area map ready"}
          </div>
        </div>
      </div>
    </div>
  );
}
