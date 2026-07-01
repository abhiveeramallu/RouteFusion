import {
  ArrowRight,
  CarFront,
  CheckCircle2,
  Clock3,
  HandCoins,
  MapPin,
  Package,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useNavigate } from "react-router-dom";

import { PanelCard } from "../components/PanelCard";
import { PanelHeader } from "../components/PanelHeader";
import { PlaceAutocompleteInput } from "../components/PlaceAutocompleteInput";
import { useRouteFusion } from "../context/RouteFusionContext";
import {
  bookingModes,
  parcelPriorityOptions,
  parcelTypeOptions,
  rideTypeOptions,
  routePointToSelection,
  supportedLocalPlaces,
} from "../lib/constants";
import { formatCurrency, humanizeRecommendation } from "../lib/format";
import { freeServiceModeMessage, geocodeSelection, hasGoogleMapsApiKey, selectionToPayloadPoint } from "../lib/googleMaps";
import { createCaptainScenario, createParcelScenario, createRideScenario } from "../lib/mapScenario";
import { buildAcceptedRoutePoints, buildRouteSummary, buildRouteTimeline } from "../lib/routeInsights";
import type {
  BookingMode,
  CaptainDecision,
  LocationSelection,
  Parcel,
  ParcelDraftValues,
  ParcelFormValues,
  Recommendation,
  Ride,
  RideDraftValues,
  RideFormValues,
} from "../types";

const rideRouteMap: Record<BookingMode, string> = {
  ride: "/ride",
  parcel: "/parcel",
  captain: "/captain",
};

function emptyLocationSelection(): LocationSelection {
  return {
    name: "",
    lat: null,
    lng: null,
  };
}

function defaultPlaceSelection(name: string, fallbackIndex: number) {
  const place = supportedLocalPlaces.find((candidate) => candidate.name === name) ?? supportedLocalPlaces[fallbackIndex];
  return routePointToSelection(place);
}

function createDefaultRideForm(): RideDraftValues {
  return {
    pickup_location: defaultPlaceSelection("VIT Main Gate", 0),
    drop_location: defaultPlaceSelection("CMC Hospital", 1),
    passenger_count: 2,
    ride_type: "Comfort",
  };
}

function createDefaultParcelForm(): ParcelDraftValues {
  return {
    pickup_location: defaultPlaceSelection("Silver Jubilee Tower", 2),
    drop_location: defaultPlaceSelection("Gandhi Nagar", 3),
    parcel_weight: 4.5,
    parcel_type: "Medical Package",
    priority: "High",
  };
}

type BookingHubPageProps = {
  mode: BookingMode;
};

function FieldShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-[#4b5563]">{label}</span>
      {children}
    </label>
  );
}

function inputClassName() {
  return "w-full rounded-2xl border border-[#dbe1e7] bg-[#f9fafb] px-4 py-3 text-sm text-[#111827] outline-none transition placeholder:text-[#9ca3af] focus:border-[#111111] focus:bg-white";
}

function locationName(selection: LocationSelection) {
  return selection.name.trim() || "Choose a location";
}

function statusClassName(status: string) {
  if (status === "confirmed" || status === "assigned" || status === "confirmed_solo" || status === "assigned_solo") {
    return "bg-[#ecfdf3] text-[#15803d]";
  }
  if (status === "completed") {
    return "bg-[#ecfdf3] text-[#166534]";
  }
  if (status === "rejected" || status === "cancelled") {
    return "bg-[#fff1f2] text-[#b42318]";
  }
  if (status === "open") {
    return "bg-[#f3f4f6] text-[#4b5563]";
  }
  return "bg-[#eff6ff] text-[#2563eb]";
}

function statusLabel(status: string) {
  return status.replace(/_/g, " ");
}

function isActiveRideStatus(status: string) {
  return status === "open" || status === "confirmed" || status === "confirmed_solo";
}

function isActiveParcelStatus(status: string) {
  return status === "open" || status === "assigned" || status === "assigned_solo";
}

function rideNeedsCancelConfirmation(status: string) {
  return status === "confirmed" || status === "confirmed_solo";
}

function parcelNeedsCancelConfirmation(status: string) {
  return status === "assigned" || status === "assigned_solo";
}

function confirmationLabel(decisionMode: "pending" | "combined" | "ride_only" | "parcel_only") {
  return {
    pending: "Awaiting captain choice",
    combined: "Combined route confirmed",
    ride_only: "Ride accepted only",
    parcel_only: "Parcel accepted only",
  }[decisionMode];
}

function buildCaptainGuideRoute(
  recommendation: Recommendation,
  currentLocation: Recommendation["optimized_route"][number] | null,
) {
  return buildAcceptedRoutePoints(recommendation, currentLocation);
}

function captainGuideReason(recommendation: Recommendation) {
  if (recommendation.decision_mode === "combined") {
    return "AI recommends this combined order because it keeps the passenger and parcel on one confirmed trip with the strongest efficiency score and customer savings.";
  }

  if (recommendation.decision_mode === "ride_only") {
    return "AI recommends following only the ride route now because that is the cleanest confirmed trip. The parcel stays open for a later match.";
  }

  if (recommendation.decision_mode === "parcel_only") {
    return "AI recommends following only the parcel route now because that is the cleanest confirmed trip. The ride stays open for a later match.";
  }

  return "AI is evaluating the best order for the current demand.";
}

function hasRideRequest(recommendation: Recommendation) {
  return recommendation.ride !== null;
}

function hasParcelRequest(recommendation: Recommendation) {
  return recommendation.parcel !== null;
}

function confirmedSecondaryMetricLabel(recommendation: Recommendation) {
  if (recommendation.decision_mode === "combined") {
    return "Parcel fee";
  }

  if (recommendation.decision_mode === "ride_only") {
    return hasParcelRequest(recommendation) ? "Queue status" : "Route mode";
  }

  if (recommendation.decision_mode === "parcel_only") {
    return hasRideRequest(recommendation) ? "Queue status" : "Route mode";
  }

  return "Queue status";
}

function confirmedSecondaryMetricValue(recommendation: Recommendation) {
  if (recommendation.decision_mode === "combined") {
    return formatCurrency(recommendation.parcel_customer_price);
  }

  if (recommendation.decision_mode === "ride_only") {
    return hasParcelRequest(recommendation) ? "Parcel open" : "Direct ride";
  }

  if (recommendation.decision_mode === "parcel_only") {
    return hasRideRequest(recommendation) ? "Ride open" : "Direct parcel";
  }

  return "Open";
}

function paymentCollectionSummary(recommendation: Recommendation) {
  if (recommendation.decision_mode === "combined") {
    return `Collect ${formatCurrency(recommendation.ride_customer_price)} from the passenger and ${formatCurrency(recommendation.parcel_customer_price)} from the parcel sender.`;
  }

  if (recommendation.decision_mode === "ride_only") {
    return `Collect ${formatCurrency(recommendation.ride_customer_price)} from the passenger.`;
  }

  return `Collect ${formatCurrency(recommendation.parcel_customer_price)} from the parcel sender.`;
}

function buildRidePayload(
  form: RideDraftValues,
  pickupLocation: LocationSelection,
  dropLocation: LocationSelection,
): RideFormValues {
  return {
    pickup_location: pickupLocation.name,
    drop_location: dropLocation.name,
    pickup_point: selectionToPayloadPoint(pickupLocation),
    drop_point: selectionToPayloadPoint(dropLocation),
    passenger_count: form.passenger_count,
    ride_type: form.ride_type,
  };
}

function buildParcelPayload(
  form: ParcelDraftValues,
  pickupLocation: LocationSelection,
  dropLocation: LocationSelection,
): ParcelFormValues {
  return {
    pickup_location: pickupLocation.name,
    drop_location: dropLocation.name,
    pickup_point: selectionToPayloadPoint(pickupLocation),
    drop_point: selectionToPayloadPoint(dropLocation),
    parcel_weight: form.parcel_weight,
    parcel_type: form.parcel_type,
    priority: form.priority,
  };
}

export function BookingHubPage({ mode }: BookingHubPageProps) {
  const navigate = useNavigate();
  const {
    currentLocation,
    dashboard,
    recommendation,
    rides,
    parcels,
    submitRide,
    submitParcel,
    cancelRideRequest,
    cancelParcelRequest,
    respondToCaptainDecision,
    completeCaptainRoute,
    setMapScenario,
  } = useRouteFusion();
  const [activeMode, setActiveMode] = useState<BookingMode>(mode);
  const [rideForm, setRideForm] = useState<RideDraftValues>(createDefaultRideForm);
  const [parcelForm, setParcelForm] = useState<ParcelDraftValues>(createDefaultParcelForm);
  const [createdRide, setCreatedRide] = useState<Ride | null>(null);
  const [createdParcel, setCreatedParcel] = useState<Parcel | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setActiveMode(mode);
  }, [mode]);

  const activeRideRequests = rides.filter((ride) => isActiveRideStatus(ride.status));
  const activeParcelRequests = parcels.filter((parcel) => isActiveParcelStatus(parcel.status));
  const trackedRide = createdRide
    ? activeRideRequests.find((ride) => ride.id === createdRide.id)
      ?? activeRideRequests[0]
      ?? rides.find((ride) => ride.id === createdRide.id)
      ?? createdRide
    : activeRideRequests[0] ?? null;
  const trackedParcel = createdParcel
    ? activeParcelRequests.find((parcel) => parcel.id === createdParcel.id)
      ?? activeParcelRequests[0]
      ?? parcels.find((parcel) => parcel.id === createdParcel.id)
      ?? createdParcel
    : activeParcelRequests[0] ?? null;
  const routeConfirmed = Boolean(recommendation?.route_confirmed);
  const hasRideRecommendation = Boolean(recommendation?.ride);
  const hasParcelRecommendation = Boolean(recommendation?.parcel);
  const captainGuideSteps = recommendation
    ? buildCaptainGuideRoute(recommendation, currentLocation)
    : [];
  const captainRouteSummary = recommendation ? buildRouteSummary(captainGuideSteps) : null;
  const captainTimeline = recommendation ? buildRouteTimeline(captainGuideSteps) : [];
  const canAcceptBoth = Boolean(recommendation && !routeConfirmed && hasRideRecommendation && hasParcelRecommendation);
  const canAcceptRide = Boolean(recommendation && !routeConfirmed && hasRideRecommendation);
  const canAcceptParcel = Boolean(recommendation && !routeConfirmed && hasParcelRecommendation);
  const queuedRides = rides.filter((ride) => ride.status === "open");
  const queuedParcels = parcels.filter((parcel) => parcel.status === "open");
  const captainMetrics = dashboard?.metrics;

  const panelScenario = useMemo(() => {
    if (activeMode === "ride") {
      return createRideScenario({ form: rideForm, currentLocation });
    }
    if (activeMode === "parcel") {
      return createParcelScenario({ form: parcelForm, currentLocation });
    }
    return createCaptainScenario(recommendation, currentLocation);
  }, [activeMode, currentLocation, parcelForm, recommendation, rideForm]);

  useEffect(() => {
    setMapScenario(panelScenario);
    return () => setMapScenario(null);
  }, [panelScenario, setMapScenario]);

  function switchMode(nextMode: BookingMode) {
    setActiveMode(nextMode);
    navigate(rideRouteMap[nextMode]);
  }

  function handleRideSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => {
      void (async () => {
        const pickupLocation = await geocodeSelection(rideForm.pickup_location);
        const dropLocation = await geocodeSelection(rideForm.drop_location);
        setRideForm((current) => ({
          ...current,
          pickup_location: pickupLocation,
          drop_location: dropLocation,
        }));
        const ride = await submitRide(buildRidePayload(rideForm, pickupLocation, dropLocation));
        setCreatedRide(ride);
      })().catch(() => undefined);
    });
  }

  function handleParcelSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => {
      void (async () => {
        const pickupLocation = await geocodeSelection(parcelForm.pickup_location);
        const dropLocation = await geocodeSelection(parcelForm.drop_location);
        setParcelForm((current) => ({
          ...current,
          pickup_location: pickupLocation,
          drop_location: dropLocation,
        }));
        const parcel = await submitParcel(buildParcelPayload(parcelForm, pickupLocation, dropLocation));
        setCreatedParcel(parcel);
      })().catch(() => undefined);
    });
  }

  function handleCaptainDecision(decision: CaptainDecision) {
    if (isPending) {
      return;
    }
    startTransition(() => {
      void respondToCaptainDecision(decision).catch(() => undefined);
    });
  }

  function handleCaptainCompletion() {
    if (isPending) {
      return;
    }
    startTransition(() => {
      void completeCaptainRoute().catch(() => undefined);
    });
  }

  function handleRideCancel(ride: Ride) {
    if (
      rideNeedsCancelConfirmation(ride.status)
      && !window.confirm("Captain already accepted this ride. Are you sure you want to cancel it?")
    ) {
      return;
    }

    startTransition(() => {
      void cancelRideRequest(ride.id)
        .then(() => {
          setCreatedRide((current) => (current?.id === ride.id ? null : current));
        })
        .catch(() => undefined);
    });
  }

  function handleParcelCancel(parcel: Parcel) {
    if (
      parcelNeedsCancelConfirmation(parcel.status)
      && !window.confirm("Captain already accepted this parcel. Are you sure you want to cancel it?")
    ) {
      return;
    }

    startTransition(() => {
      void cancelParcelRequest(parcel.id)
        .then(() => {
          setCreatedParcel((current) => (current?.id === parcel.id ? null : current));
        })
        .catch(() => undefined);
    });
  }

  return (
    <div className="space-y-6 p-6">
      <PanelHeader
        eyebrow="Booking Hub"
        title="Trips, parcels, and captain decisions in one panel"
        description="Switch between ride intake, parcel intake, and the captain recommendation without losing context. The map stays alive while this panel swaps modes, similar to how Uber keeps service switching inside one booking surface."
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
          {bookingModes.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => switchMode(tab.key)}
              className={`rounded-full px-4 py-2.5 text-sm font-semibold transition ${
                activeMode === tab.key
                  ? "bg-[#111111] text-white"
                  : "bg-[#f3f4f6] text-[#4b5563] hover:bg-[#e5e7eb] hover:text-[#111827]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-[24px] border border-[#e7eaee] bg-[#f9fafb] px-4 py-3 text-xs text-[#6b7280]">
        {hasGoogleMapsApiKey()
          ? "Google place search is wired in. If live road routing is unavailable, RouteFusion keeps the map visible and falls back to straight-line route preview."
          : freeServiceModeMessage()}
      </div>

      {activeMode === "ride" ? (
        <div className="space-y-4">
          <PanelCard className="bg-[#f9fafb]">
            <div className="flex items-center gap-2 text-[#111827]">
              <CarFront className="h-4 w-4 text-[#22C55E]" />
              <p className="text-sm font-semibold uppercase tracking-[0.18em]">Current ride requests</p>
            </div>
            <div className="mt-4 space-y-3">
              {activeRideRequests.length > 0 ? (
                activeRideRequests.map((ride) => (
                  <div key={ride.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words text-base font-semibold text-[#111827]">
                          {ride.pickup_name} to {ride.drop_name}
                        </p>
                        <p className="mt-2 text-sm text-[#6b7280]">
                          {ride.passenger_count} passengers • {ride.ride_type}
                        </p>
                      </div>
                      <span className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold capitalize ${statusClassName(ride.status)}`}>
                        {statusLabel(ride.status)}
                      </span>
                    </div>
                    {rideNeedsCancelConfirmation(ride.status) ? (
                      <p className="mt-3 text-sm text-[#b45309]">
                        Captain already accepted this ride. Cancelling it will ask for confirmation.
                      </p>
                    ) : null}
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={() => handleRideCancel(ride)}
                        className="inline-flex items-center justify-center rounded-full border border-[#ef4444]/20 bg-[#fff1f2] px-4 py-2.5 text-sm font-semibold text-[#b42318] transition hover:border-[#ef4444]"
                      >
                        {isPending ? "Cancelling..." : "Cancel Request"}
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-[#dbe1e7] bg-white p-4 text-sm text-[#6b7280]">
                  No current ride requests yet.
                </div>
              )}
            </div>
          </PanelCard>

          <PanelCard>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Ride Mode</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Book a ride</h2>
                <p className="mt-2 text-sm leading-7 text-[#6b7280]">
                  Passenger intake stays quick while the map previews the exact route using the selected Google place coordinates.
                </p>
              </div>
              <div className="rounded-2xl bg-[#f3f4f6] p-3 text-[#111827]">
                <CarFront className="h-5 w-5" />
              </div>
            </div>

            <form className="mt-6 grid gap-4" onSubmit={handleRideSubmit}>
              <PlaceAutocompleteInput
                label="Pickup location"
                placeholder="Search ride pickup"
                value={rideForm.pickup_location}
                onChange={(pickup_location) => setRideForm((current) => ({ ...current, pickup_location }))}
              />

              <PlaceAutocompleteInput
                label="Drop location"
                placeholder="Search ride drop"
                value={rideForm.drop_location}
                onChange={(drop_location) => setRideForm((current) => ({ ...current, drop_location }))}
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <FieldShell label="Passenger count">
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={rideForm.passenger_count}
                    onChange={(event) =>
                      setRideForm((current) => ({
                        ...current,
                        passenger_count: Number(event.target.value),
                      }))
                    }
                    className={inputClassName()}
                  />
                </FieldShell>

                <FieldShell label="Ride type">
                  <select
                    value={rideForm.ride_type}
                    onChange={(event) =>
                      setRideForm((current) => ({ ...current, ride_type: event.target.value }))
                    }
                    className={inputClassName()}
                  >
                    {rideTypeOptions.map((rideType) => (
                      <option key={rideType} value={rideType}>
                        {rideType}
                      </option>
                    ))}
                  </select>
                </FieldShell>
              </div>

              <button
                type="submit"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[#111111] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#000000]"
              >
                {isPending ? "Booking..." : "Book Ride"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>
          </PanelCard>

          <div className="grid gap-4 sm:grid-cols-2">
            <PanelCard className="bg-[#f9fafb]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#22C55E]">Live preview</p>
              <p className="mt-2 text-lg font-semibold text-[#111827]">
                {locationName(rideForm.pickup_location)} to {locationName(rideForm.drop_location)}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Passenger route updates the map instantly while the captain position stays visible on the right.
              </p>
            </PanelCard>

            <PanelCard className={trackedRide ? "bg-[#f0fdf4]" : "bg-[#f9fafb]"}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Status</p>
              <div className="mt-2 flex items-center justify-between gap-3">
                <p className="text-lg font-semibold text-[#111827]">
                  {routeConfirmed
                    ? recommendation?.decision_mode === "parcel_only"
                      ? "Ride still open for matching"
                      : "Ride confirmed by captain"
                    : trackedRide
                      ? "Ride request stored"
                      : "Ready for submission"}
                </p>
                {trackedRide ? (
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusClassName(trackedRide.status)}`}>
                    {statusLabel(trackedRide.status)}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-[#6b7280]">
                {trackedRide
                  ? `${trackedRide.passenger_count} passengers • ${trackedRide.ride_type}`
                  : "Create the passenger side first, then add a parcel request for captain matching."}
              </p>
            </PanelCard>
          </div>
        </div>
      ) : null}

      {activeMode === "parcel" ? (
        <div className="space-y-4">
          <PanelCard className="bg-[#f9fafb]">
            <div className="flex items-center gap-2 text-[#111827]">
              <Package className="h-4 w-4 text-[#2563eb]" />
              <p className="text-sm font-semibold uppercase tracking-[0.18em]">Current parcel requests</p>
            </div>
            <div className="mt-4 space-y-3">
              {activeParcelRequests.length > 0 ? (
                activeParcelRequests.map((parcel) => (
                  <div key={parcel.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words text-base font-semibold text-[#111827]">
                          {parcel.pickup_name} to {parcel.drop_name}
                        </p>
                        <p className="mt-2 text-sm text-[#6b7280]">
                          {parcel.parcel_weight} kg • {parcel.priority} • {parcel.parcel_type}
                        </p>
                      </div>
                      <span className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold capitalize ${statusClassName(parcel.status)}`}>
                        {statusLabel(parcel.status)}
                      </span>
                    </div>
                    {parcelNeedsCancelConfirmation(parcel.status) ? (
                      <p className="mt-3 text-sm text-[#b45309]">
                        Captain already accepted this parcel. Cancelling it will ask for confirmation.
                      </p>
                    ) : null}
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={() => handleParcelCancel(parcel)}
                        className="inline-flex items-center justify-center rounded-full border border-[#ef4444]/20 bg-[#fff1f2] px-4 py-2.5 text-sm font-semibold text-[#b42318] transition hover:border-[#ef4444]"
                      >
                        {isPending ? "Cancelling..." : "Cancel Request"}
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-[#dbe1e7] bg-white p-4 text-sm text-[#6b7280]">
                  No current parcel requests yet.
                </div>
              )}
            </div>
          </PanelCard>

          <PanelCard>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Parcel Mode</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Send a parcel</h2>
                <p className="mt-2 text-sm leading-7 text-[#6b7280]">
                  Capture a delivery request without leaving the booking panel. The parcel route keeps updating on the same live map.
                </p>
              </div>
              <div className="rounded-2xl bg-[#f3f4f6] p-3 text-[#111827]">
                <Package className="h-5 w-5" />
              </div>
            </div>

            <form className="mt-6 grid gap-4" onSubmit={handleParcelSubmit}>
              <PlaceAutocompleteInput
                label="Pickup location"
                placeholder="Search parcel pickup"
                value={parcelForm.pickup_location}
                onChange={(pickup_location) => setParcelForm((current) => ({ ...current, pickup_location }))}
              />

              <PlaceAutocompleteInput
                label="Drop location"
                placeholder="Search parcel drop"
                value={parcelForm.drop_location}
                onChange={(drop_location) => setParcelForm((current) => ({ ...current, drop_location }))}
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <FieldShell label="Weight (kg)">
                  <input
                    type="number"
                    min="0.5"
                    max="50"
                    step="0.1"
                    value={parcelForm.parcel_weight}
                    onChange={(event) =>
                      setParcelForm((current) => ({
                        ...current,
                        parcel_weight: Number(event.target.value),
                      }))
                    }
                    className={inputClassName()}
                  />
                </FieldShell>

                <FieldShell label="Priority">
                  <select
                    value={parcelForm.priority}
                    onChange={(event) =>
                      setParcelForm((current) => ({
                        ...current,
                        priority: event.target.value as ParcelDraftValues["priority"],
                      }))
                    }
                    className={inputClassName()}
                  >
                    {parcelPriorityOptions.map((priority) => (
                      <option key={priority} value={priority}>
                        {priority}
                      </option>
                    ))}
                  </select>
                </FieldShell>
              </div>

              <FieldShell label="Parcel type">
                <select
                  value={parcelForm.parcel_type}
                  onChange={(event) =>
                    setParcelForm((current) => ({ ...current, parcel_type: event.target.value }))
                  }
                  className={inputClassName()}
                >
                  {parcelTypeOptions.map((parcelType) => (
                    <option key={parcelType} value={parcelType}>
                      {parcelType}
                    </option>
                  ))}
                </select>
              </FieldShell>

              <button
                type="submit"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[#111111] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#000000]"
              >
                {isPending ? "Submitting..." : "Request Delivery"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>
          </PanelCard>

          <div className="grid gap-4 sm:grid-cols-2">
            <PanelCard className="bg-[#eff6ff]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2563eb]">Route insight</p>
              <p className="mt-2 text-lg font-semibold text-[#111827]">
                {locationName(parcelForm.pickup_location)} to {locationName(parcelForm.drop_location)}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Short, urgent parcel runs are easier for the captain to bundle without degrading passenger ETA.
              </p>
            </PanelCard>

            <PanelCard className={trackedParcel ? "bg-[#f0fdf4]" : "bg-[#f9fafb]"}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Status</p>
              <div className="mt-2 flex items-center justify-between gap-3">
                <p className="text-lg font-semibold text-[#111827]">
                  {routeConfirmed
                    ? recommendation?.decision_mode === "ride_only"
                      ? "Parcel returned to the queue"
                      : "Parcel assigned by captain"
                    : trackedParcel
                      ? "Parcel request stored"
                      : "Ready for submission"}
                </p>
                {trackedParcel ? (
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusClassName(trackedParcel.status)}`}>
                    {statusLabel(trackedParcel.status)}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-[#6b7280]">
                {trackedParcel
                  ? `${trackedParcel.parcel_weight} kg • ${trackedParcel.priority} priority`
                  : "Submit a parcel request, then switch to Captain to evaluate the combined route."}
              </p>
            </PanelCard>
          </div>
        </div>
      ) : null}

      {activeMode === "captain" ? (
        <div className="space-y-4">
          <PanelCard className="bg-[linear-gradient(180deg,#ffffff_0%,#f9fafb_100%)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Captain Mode</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Captain decisions</h2>
                <p className="mt-2 text-sm leading-7 text-[#6b7280]">
                  Choose whether the captain should take the ride only, the parcel only, or the combined route, while the map keeps the live path visible.
                </p>
              </div>
              <div className="inline-flex max-w-full items-center gap-2 rounded-full bg-[#f3f4f6] px-4 py-2 text-sm text-[#4b5563]">
                <Clock3 className="h-4 w-4 text-[#5B5BEF]" />
                Last action: {recommendation?.recent_decision ? "Recorded" : "Pending"}
              </div>
            </div>

            {recommendation ? (
              <div className="mt-6 space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-[24px] bg-white p-4 shadow-[0_12px_28px_rgba(15,23,42,0.06)]">
                    <div className="flex items-center gap-3">
                      <div className="grid h-12 w-12 place-items-center rounded-full bg-[#111111] text-sm font-semibold text-white">
                        CA
                      </div>
                      <div className="min-w-0">
                        <p className="break-words text-lg font-semibold text-[#111827]">
                          {recommendation.driver.display_name}
                        </p>
                        <p className="break-words text-sm text-[#6b7280]">{recommendation.driver.vehicle_type}</p>
                      </div>
                    </div>
                    <div className="mt-4 flex items-start gap-2 text-sm text-[#4b5563]">
                      <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#5B5BEF]" />
                      <span className="break-words leading-6">{recommendation.confirmation_status}</span>
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-[24px] bg-[#111111] p-4 text-white shadow-[0_18px_36px_rgba(17,24,39,0.18)]">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-white/60">
                      {routeConfirmed ? "Captain choice" : "Recommendation"}
                    </p>
                    <p className="mt-3 break-words text-2xl font-semibold tracking-[-0.03em]">
                      {routeConfirmed ? confirmationLabel(recommendation.decision_mode) : humanizeRecommendation(recommendation.recommendation)}
                    </p>
                    <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                      <div>
                        <p className="text-white/60">
                          {routeConfirmed
                            ? recommendation.decision_mode === "parcel_only"
                              ? "Parcel fee"
                              : "Ride fare"
                            : "Score"}
                        </p>
                        <p className="mt-1 font-semibold">
                          {routeConfirmed
                            ? formatCurrency(
                                recommendation.decision_mode === "parcel_only"
                                  ? recommendation.parcel_customer_price
                                  : recommendation.ride_customer_price,
                              )
                            : `${recommendation.efficiency_score}%`}
                        </p>
                      </div>
                      <div>
                        <p className="text-white/60">{routeConfirmed ? confirmedSecondaryMetricLabel(recommendation) : "Distance"}</p>
                        <p className="mt-1 font-semibold">
                          {routeConfirmed
                            ? confirmedSecondaryMetricValue(recommendation)
                            : `${recommendation.extra_distance} km`}
                        </p>
                      </div>
                      <div>
                        <p className="text-white/60">{routeConfirmed ? "Total" : "Time"}</p>
                        <p className="mt-1 font-semibold">
                          {routeConfirmed
                            ? formatCurrency(recommendation.combined_customer_total)
                            : `${Math.round(recommendation.extra_time)} min`}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className={`grid gap-4 ${hasRideRecommendation && hasParcelRecommendation ? "sm:grid-cols-2" : "sm:grid-cols-1"}`}>
                  {recommendation.ride ? (
                    <div className="rounded-[24px] bg-white p-4 shadow-[0_12px_28px_rgba(15,23,42,0.06)]">
                      <div className="flex items-center gap-2 text-[#22C55E]">
                        <CarFront className="h-4 w-4" />
                        <p className="text-sm font-semibold uppercase tracking-[0.18em]">Ride</p>
                      </div>
                      <p className="mt-3 break-words text-lg font-semibold leading-8 text-[#111827]">
                        {recommendation.ride.pickup_name} to {recommendation.ride.drop_name}
                      </p>
                      <p className="mt-2 text-sm text-[#6b7280]">
                        {recommendation.ride.passenger_count} passengers • {recommendation.ride.ride_type}
                      </p>
                      <span className={`mt-3 inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusClassName(recommendation.ride.status)}`}>
                        {statusLabel(recommendation.ride.status)}
                      </span>
                    </div>
                  ) : null}

                  {recommendation.parcel ? (
                    <div className="rounded-[24px] bg-white p-4 shadow-[0_12px_28px_rgba(15,23,42,0.06)]">
                      <div className="flex items-center gap-2 text-[#2563eb]">
                        <Package className="h-4 w-4" />
                        <p className="text-sm font-semibold uppercase tracking-[0.18em]">Parcel</p>
                      </div>
                      <p className="mt-3 break-words text-lg font-semibold leading-8 text-[#111827]">
                        {recommendation.parcel.pickup_name} to {recommendation.parcel.drop_name}
                      </p>
                      <p className="mt-2 text-sm text-[#6b7280]">
                        {recommendation.parcel.parcel_weight} kg • {recommendation.parcel.priority}
                      </p>
                      <span className={`mt-3 inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusClassName(recommendation.parcel.status)}`}>
                        {statusLabel(recommendation.parcel.status)}
                      </span>
                    </div>
                  ) : null}
                </div>

                {routeConfirmed ? (
                  <div
                    className={`grid gap-4 ${
                      recommendation.decision_mode === "combined" ? "sm:grid-cols-3" : "sm:grid-cols-2"
                    }`}
                  >
                    {recommendation.decision_mode !== "parcel_only" ? (
                      <div className="rounded-[24px] bg-[#f0fdf4] p-4 shadow-[0_10px_24px_rgba(34,197,94,0.08)]">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#15803d]">Ride fare</p>
                        <p className="mt-2 text-2xl font-semibold text-[#111827]">
                          {formatCurrency(recommendation.ride_customer_price)}
                        </p>
                      </div>
                    ) : null}
                    {recommendation.decision_mode !== "ride_only" ? (
                      <div className="rounded-[24px] bg-[#eff6ff] p-4 shadow-[0_10px_24px_rgba(37,99,235,0.08)]">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2563eb]">Parcel fee</p>
                        <p className="mt-2 text-2xl font-semibold text-[#111827]">
                          {formatCurrency(recommendation.parcel_customer_price)}
                        </p>
                      </div>
                    ) : null}
                    <div className="rounded-[24px] bg-[#f5f3ff] p-4 shadow-[0_10px_24px_rgba(91,91,239,0.08)]">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#6d28d9]">
                        {recommendation.decision_mode === "combined" ? "Customer savings" : "Route total"}
                      </p>
                      <p className="mt-2 text-2xl font-semibold text-[#111827]">
                        {recommendation.decision_mode === "combined"
                          ? formatCurrency(recommendation.estimated_customer_savings)
                          : formatCurrency(recommendation.combined_customer_total)}
                      </p>
                    </div>
                  </div>
                ) : null}

                {routeConfirmed ? (
                  <div className="rounded-[24px] border border-[#e7eaee] bg-white px-4 py-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#6b7280]">
                      Payment collection
                    </p>
                    <p className="mt-2 text-sm leading-7 text-[#111827]">
                      {paymentCollectionSummary(recommendation)}
                    </p>
                  </div>
                ) : null}

                {recommendation ? (
                  <div className="rounded-[24px] border border-[#e7e9f6] bg-[#fafaff] p-4 shadow-[0_12px_28px_rgba(91,91,239,0.06)]">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">
                      AI Route Guidance
                    </p>
                    <p className="mt-2 text-xl font-semibold tracking-[-0.03em] text-[#111827]">
                      {routeConfirmed ? "Best route to follow" : "Best route proposal"}
                    </p>
                    <p className="mt-2 text-sm leading-7 text-[#6b7280]">
                      {captainGuideReason(recommendation)}
                    </p>
                    {captainRouteSummary ? (
                      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        <div className="rounded-2xl border border-[#eceef5] bg-white px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">
                            Shortest route
                          </p>
                          <p className="mt-2 text-lg font-semibold text-[#111827]">
                            {captainRouteSummary.distanceText}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-[#eceef5] bg-white px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">
                            Estimated time
                          </p>
                          <p className="mt-2 text-lg font-semibold text-[#111827]">
                            {captainRouteSummary.durationText}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-[#eceef5] bg-white px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">
                            Active mode
                          </p>
                          <p className="mt-2 text-lg font-semibold capitalize text-[#111827]">
                            {recommendation.decision_mode.replace(/_/g, " ")}
                          </p>
                        </div>
                      </div>
                    ) : null}
                    {captainGuideSteps.length ? (
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        {captainGuideSteps.map((step, index) => (
                          <div
                            key={`${step.name}-${index}`}
                            className="flex items-center gap-3 rounded-2xl border border-[#eceef5] bg-white px-4 py-3"
                          >
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#111111] text-xs font-semibold text-white">
                              {index + 1}
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6b7280]">
                                {index === 0 ? "Start" : "Stop"}
                              </p>
                              <p className="break-words text-sm font-semibold text-[#111827]">{step.name}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {captainTimeline.length ? (
                      <div className="mt-4 rounded-[22px] border border-[#eceef5] bg-white p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">
                          Estimated stop timeline
                        </p>
                        <div className="mt-3 grid gap-3">
                          {captainTimeline.map((stop, index) => (
                            <div
                              key={`${stop.point.name}-${index}-eta`}
                              className="flex items-start justify-between gap-4 rounded-2xl bg-[#f9fafb] px-4 py-3"
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6b7280]">
                                  Stop {index + 1}
                                </p>
                                <p className="mt-1 break-words text-sm font-semibold text-[#111827]">
                                  {stop.point.name}
                                </p>
                              </div>
                              <div className="shrink-0 text-right">
                                <p className="text-xs text-[#6b7280]">ETA</p>
                                <p className="text-sm font-semibold text-[#111827]">
                                  {Math.round(stop.estimatedMinutes)} min
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-3">
                  {routeConfirmed ? (
                    <div className="grid w-full gap-3 sm:grid-cols-2">
                      <div className="inline-flex items-center gap-2 rounded-full bg-[#111111] px-5 py-3 text-sm font-semibold text-white">
                        <CheckCircle2 className="h-4 w-4" />
                        {confirmationLabel(recommendation.decision_mode)}
                      </div>
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={handleCaptainCompletion}
                        className="inline-flex items-center justify-center gap-2 rounded-full border border-[#111111] bg-white px-5 py-3 text-sm font-semibold text-[#111827] transition hover:bg-[#111111] hover:text-white disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-white disabled:hover:text-[#111827]"
                      >
                        <HandCoins className="h-4 w-4" />
                        {isPending ? "Closing Route..." : "Mark Done & Collect Payment"}
                      </button>
                    </div>
                  ) : (
                    <div className="grid w-full gap-3 sm:grid-cols-2">
                      {canAcceptBoth ? (
                        <button
                          type="button"
                          disabled={isPending}
                          onClick={() => handleCaptainDecision("accept_both")}
                          className="inline-flex items-center justify-center gap-2 rounded-full bg-[#111111] px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-[#000000] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-[#111111]"
                        >
                          <CheckCircle2 className="h-4 w-4 shrink-0" />
                          {isPending ? "Saving..." : "Accept Both"}
                        </button>
                      ) : null}
                      {canAcceptRide ? (
                        <button
                          type="button"
                          disabled={isPending}
                          onClick={() => handleCaptainDecision("accept_ride")}
                          className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-center text-sm font-semibold transition ${
                            canAcceptBoth
                              ? "border border-[#22C55E]/30 bg-[#f0fdf4] text-[#166534] hover:border-[#22C55E]"
                              : "bg-[#111111] text-white hover:bg-[#000000]"
                          } disabled:cursor-not-allowed disabled:opacity-60`}
                        >
                          <CarFront className="h-4 w-4 shrink-0" />
                          {canAcceptBoth ? "Accept Ride Only" : isPending ? "Saving..." : "Accept Ride"}
                        </button>
                      ) : null}
                      {canAcceptParcel ? (
                        <button
                          type="button"
                          disabled={isPending}
                          onClick={() => handleCaptainDecision("accept_parcel")}
                          className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-center text-sm font-semibold transition ${
                            canAcceptBoth
                              ? "border border-[#2563eb]/30 bg-[#eff6ff] text-[#1d4ed8] hover:border-[#2563eb]"
                              : "bg-[#111111] text-white hover:bg-[#000000]"
                          } disabled:cursor-not-allowed disabled:opacity-60`}
                        >
                          <Package className="h-4 w-4 shrink-0" />
                          {canAcceptBoth ? "Accept Parcel Only" : isPending ? "Saving..." : "Accept Parcel"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() => handleCaptainDecision("reject")}
                        className="inline-flex items-center justify-center gap-2 rounded-full border border-[#dbe1e7] bg-white px-5 py-3 text-center text-sm font-semibold text-[#111827] transition hover:border-[#111111] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-[#dbe1e7]"
                      >
                        <XCircle className="h-4 w-4 shrink-0" />
                        Reject All
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="mt-6 rounded-[24px] border border-dashed border-[#dbe1e7] bg-[#f9fafb] p-5">
                <div className="flex items-start gap-3">
                  <Sparkles className="mt-0.5 h-5 w-5 text-[#5B5BEF]" />
                  <div>
                    <p className="text-lg font-semibold text-[#111827]">No active recommendation yet</p>
                    <p className="mt-2 text-sm leading-7 text-[#6b7280]">
                      Create a ride or parcel request and the captain recommendation will appear here. If both overlap well, RouteFusion will also show the combined AI route.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </PanelCard>

          <div className="grid gap-4 sm:grid-cols-2">
            <PanelCard className="bg-[#f9fafb]">
              <div className="flex items-center gap-2 text-[#111827]">
                <ShieldCheck className="h-4 w-4 text-[#5B5BEF]" />
                <p className="text-sm font-semibold uppercase tracking-[0.18em]">Ride requests</p>
              </div>
              <div className="mt-4 space-y-3">
                {queuedRides.length > 0 ? (
                  queuedRides.slice(0, 3).map((ride) => (
                    <div key={ride.id} className="rounded-2xl border border-[#e7eaee] bg-white p-3 text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p className="min-w-0 break-words font-semibold text-[#111827]">
                          {ride.pickup_name} to {ride.drop_name}
                        </p>
                        <span className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold capitalize ${statusClassName(ride.status)}`}>
                          {statusLabel(ride.status)}
                        </span>
                      </div>
                      <p className="mt-1 text-[#6b7280]">
                        {ride.passenger_count} passengers • {ride.ride_type}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-[#dbe1e7] bg-white p-4 text-sm text-[#6b7280]">
                    No ride requests in the queue.
                  </div>
                )}
              </div>
            </PanelCard>

            <PanelCard className="bg-[#f9fafb]">
              <div className="flex items-center gap-2 text-[#111827]">
                <Package className="h-4 w-4 text-[#2563eb]" />
                <p className="text-sm font-semibold uppercase tracking-[0.18em]">Parcel requests</p>
              </div>
              <div className="mt-4 space-y-3">
                {queuedParcels.length > 0 ? (
                  queuedParcels.slice(0, 3).map((parcel) => (
                    <div key={parcel.id} className="rounded-2xl border border-[#e7eaee] bg-white p-3 text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p className="min-w-0 break-words font-semibold text-[#111827]">
                          {parcel.pickup_name} to {parcel.drop_name}
                        </p>
                        <span className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold capitalize ${statusClassName(parcel.status)}`}>
                          {statusLabel(parcel.status)}
                        </span>
                      </div>
                      <p className="mt-1 text-[#6b7280]">
                        {parcel.parcel_weight} kg • {parcel.priority}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-[#dbe1e7] bg-white p-4 text-sm text-[#6b7280]">
                    No parcel requests in the queue.
                  </div>
                )}
              </div>
            </PanelCard>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <PanelCard className="bg-[#f9fafb]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#15803d]">Captain earnings</p>
              <p className="mt-3 text-2xl font-semibold text-[#111827]">
                {formatCurrency(captainMetrics?.captain_total_earnings ?? 0)}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Added only after payment is collected on completed routes.
              </p>
            </PanelCard>

            <PanelCard className="bg-[#f9fafb]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Rides by captain</p>
              <p className="mt-3 text-2xl font-semibold text-[#111827]">
                {captainMetrics?.captain_rides_handled ?? 0}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Ride requests already handled by the captain.
              </p>
            </PanelCard>

            <PanelCard className="bg-[#f9fafb]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2563eb]">Parcels by captain</p>
              <p className="mt-3 text-2xl font-semibold text-[#111827]">
                {captainMetrics?.captain_parcels_handled ?? 0}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Parcel requests already handled by the captain.
              </p>
            </PanelCard>

            <PanelCard className="bg-[#f9fafb]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#6d28d9]">Combined trips</p>
              <p className="mt-3 text-2xl font-semibold text-[#111827]">
                {captainMetrics?.captain_combined_trips ?? 0}
              </p>
              <p className="mt-2 text-sm text-[#6b7280]">
                Shared ride-plus-parcel trips confirmed through RouteFusion optimization.
              </p>
            </PanelCard>
          </div>
        </div>
      ) : null}
    </div>
  );
}
