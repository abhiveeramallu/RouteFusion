import { Flag, LocateFixed, Route as RouteIcon, Truck } from "lucide-react";
import { useEffect } from "react";

import { PanelCard } from "../components/PanelCard";
import { PanelHeader } from "../components/PanelHeader";
import { useRouteFusion } from "../context/RouteFusionContext";
import { createLiveMapScenario } from "../lib/mapScenario";
import { humanizeRecommendation } from "../lib/format";
import { buildAcceptedRoutePoints, buildRouteSummary, buildRouteTimeline } from "../lib/routeInsights";

export function LiveMapPage() {
  const { recommendation, currentLocation, setMapScenario } = useRouteFusion();
  const acceptedRoute = recommendation?.route_confirmed ? buildAcceptedRoutePoints(recommendation, currentLocation) : [];
  const routeSummary = recommendation?.route_confirmed ? buildRouteSummary(acceptedRoute) : null;
  const routeTimeline = recommendation?.route_confirmed ? buildRouteTimeline(acceptedRoute) : [];

  useEffect(() => {
    setMapScenario(createLiveMapScenario(recommendation, currentLocation));
    return () => setMapScenario(null);
  }, [currentLocation, recommendation, setMapScenario]);

  if (!recommendation?.route_confirmed) {
    return (
      <div className="p-6">
        <PanelCard>
          <p className="text-sm text-[#6b7280]">
            No live route is active yet. Accept a ride, parcel, or combined route in Captain Corner first.
          </p>
        </PanelCard>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <PanelHeader
        eyebrow="Live Map"
        title="Hero route visualization"
        description="This panel supports the map-first story: passenger route in green, parcel route in blue, optimized route in purple, plus a moving captain marker."
      />

      <div className="grid gap-4">
        <PanelCard className="bg-[#f9fafb]">
          <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(160px,1fr))]">
            <div className="flex min-w-0 items-start gap-3">
              <Truck className="mt-1 h-5 w-5 text-[#22C55E]" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#22C55E]">
                  {recommendation.decision_mode === "parcel_only" ? "Ride queue" : "Passenger route"}
                </p>
                <p className="mt-2 break-words text-sm font-semibold text-[#111827]">
                  {recommendation.decision_mode === "parcel_only"
                    ? "Ride stays open for another match"
                    : recommendation.ride
                      ? `${recommendation.ride.pickup_name} to ${recommendation.ride.drop_name}`
                      : "No active ride route"}
                </p>
              </div>
            </div>
            <div className="flex min-w-0 items-start gap-3">
              <Flag className="mt-1 h-5 w-5 text-[#2563eb]" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2563eb]">
                  {recommendation.decision_mode === "ride_only" ? "Parcel queue" : "Parcel route"}
                </p>
                <p className="mt-2 break-words text-sm font-semibold text-[#111827]">
                  {recommendation.decision_mode === "ride_only"
                    ? "Parcel stays open for another match"
                    : recommendation.parcel
                      ? `${recommendation.parcel.pickup_name} to ${recommendation.parcel.drop_name}`
                      : "No active parcel route"}
                </p>
              </div>
            </div>
            <div className="flex min-w-0 items-start gap-3">
              <RouteIcon className="mt-1 h-5 w-5 text-[#5B5BEF]" />
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Optimized route</p>
                <p className="mt-2 break-words text-sm font-semibold text-[#111827]">
                  {recommendation.route_confirmed
                    ? recommendation.confirmation_status
                    : humanizeRecommendation(recommendation.recommendation)}
                </p>
              </div>
            </div>
            {routeSummary ? (
              <>
                <div className="flex min-w-0 items-start gap-3">
                  <LocateFixed className="mt-1 h-5 w-5 text-[#5B5BEF]" />
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">
                      Shortest route
                    </p>
                    <p className="mt-2 break-words text-sm font-semibold text-[#111827]">
                      {routeSummary.distanceText}
                    </p>
                  </div>
                </div>
                <div className="flex min-w-0 items-start gap-3">
                  <LocateFixed className="mt-1 h-5 w-5 text-[#111827]" />
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#6b7280]">
                      Estimated time
                    </p>
                    <p className="mt-2 break-words text-sm font-semibold text-[#111827]">
                      {routeSummary.durationText}
                    </p>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </PanelCard>

        <PanelCard>
          <div className="flex items-center gap-2 text-[#4b5563]">
            <LocateFixed className="h-4 w-4 text-[#5B5BEF]" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">Sequence timeline</p>
          </div>
          <div className="mt-5 grid gap-3">
            {routeTimeline.map((stop, index) => (
              <div key={`${stop.point.name}-${index}`} className="rounded-2xl border border-[#e7eaee] bg-[#f9fafb] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">Stop {index + 1}</p>
                <div className="mt-2 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-base font-semibold text-[#111827]">{stop.point.name}</p>
                    <p className="mt-2 text-sm text-[#6b7280]">
                      {stop.point.lat.toFixed(4)}, {stop.point.lng.toFixed(4)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">ETA</p>
                    <p className="mt-2 text-sm font-semibold text-[#111827]">
                      {Math.round(stop.estimatedMinutes)} min
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </PanelCard>
      </div>
    </div>
  );
}
