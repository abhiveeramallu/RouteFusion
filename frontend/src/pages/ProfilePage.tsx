import { Clock3, Package, Settings2, ShieldCheck, UserCircle2 } from "lucide-react";

import { PanelCard } from "../components/PanelCard";
import { PanelHeader } from "../components/PanelHeader";
import { useRouteFusion } from "../context/RouteFusionContext";
import { formatDateTime } from "../lib/format";

function infoRow(label: string, value: string) {
  return (
    <div className="rounded-2xl bg-[#f9fafb] px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b7280]">{label}</p>
      <p className="mt-2 text-sm font-semibold text-[#111827]">{value}</p>
    </div>
  );
}

function locationStatusLabel(status: string) {
  if (status === "demo") {
    return "VIT demo zone";
  }
  return status;
}

export function ProfilePage() {
  const { user, rides, parcels, dashboard, recommendation, locationStatus } = useRouteFusion();
  const profileTitle =
    user?.role
      ? `${user.role.charAt(0).toUpperCase()}${user.role.slice(1)} profile`
      : "RouteFusion profile";

  return (
    <div className="space-y-6 p-6">
      <PanelHeader
        eyebrow="Profile"
        title={profileTitle}
        description="Profile details, trip history, parcel history, captain statistics, and settings live here without any map component."
      />

      <PanelCard>
        <div className="flex items-start gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#111111] text-xl font-semibold text-white">
            {user?.full_name?.slice(0, 1) ?? "D"}
          </div>
          <div className="flex-1">
            <p className="text-2xl font-semibold tracking-[-0.03em] text-[#111827]">
              {user?.full_name ?? "Public Access"}
            </p>
            <p className="mt-1 text-sm text-[#6b7280]">
              {user?.email ?? "public@routefusion.app"}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {infoRow("Name", user?.full_name ?? "Public Access")}
              {infoRow("Email", user?.email ?? "public@routefusion.app")}
              {infoRow("Phone", "Not configured")}
              {infoRow("Role", user?.role ?? "operator")}
            </div>
          </div>
        </div>
      </PanelCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <PanelCard>
          <div className="flex items-center gap-2 text-[#4b5563]">
            <ShieldCheck className="h-4 w-4 text-[#5B5BEF]" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">Captain statistics</p>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {infoRow("Active captains", String(dashboard?.metrics.active_captains ?? 0))}
            {infoRow("Efficiency score", `${dashboard?.metrics.average_efficiency_score ?? 0}%`)}
            {infoRow("Combined trips", String(dashboard?.metrics.total_combined_trips ?? 0))}
            {infoRow("Location status", locationStatusLabel(locationStatus))}
          </div>
          <p className="mt-4 text-sm text-[#6b7280]">
            {recommendation
              ? `Latest recommendation: ${recommendation.route_confirmed ? recommendation.confirmation_status : recommendation.recommendation}`
              : "No active recommendation is available right now."}
          </p>
        </PanelCard>

        <PanelCard className="bg-[#f9fafb]">
          <div className="flex items-center gap-2 text-[#4b5563]">
            <Settings2 className="h-4 w-4 text-[#111111]" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">Settings</p>
          </div>
          <div className="mt-5 space-y-3">
            <div className="rounded-2xl bg-white px-4 py-3 shadow-sm">
              <p className="text-sm font-semibold text-[#111827]">Notifications</p>
              <p className="mt-1 text-sm text-[#6b7280]">Route alerts and captain recommendations remain enabled.</p>
            </div>
            <div className="rounded-2xl bg-white px-4 py-3 shadow-sm">
              <p className="text-sm font-semibold text-[#111827]">Map region</p>
              <p className="mt-1 text-sm text-[#6b7280]">
                Route previews are anchored to the {locationStatusLabel(locationStatus).toLowerCase()} for a consistent VIT-area demo.
              </p>
            </div>
            <div className="rounded-2xl bg-white px-4 py-3 shadow-sm">
              <p className="text-sm font-semibold text-[#111827]">Access mode</p>
              <p className="mt-1 text-sm text-[#6b7280]">
                {user?.id === 0
                  ? "Public access mode is active for the local RouteFusion workspace."
                  : "Authenticated account access is active."}
              </p>
            </div>
          </div>
        </PanelCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PanelCard className="overflow-hidden p-0">
          <div className="border-b border-[#eef1f4] px-6 py-5">
            <div className="flex items-center gap-2 text-[#4b5563]">
              <Clock3 className="h-4 w-4 text-[#22C55E]" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#22C55E]">Trip history</p>
            </div>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Recent rides</h3>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              {rides.slice(0, 5).map((ride) => (
                <div key={ride.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4">
                  <p className="font-semibold text-[#111827]">
                    {ride.pickup_name} to {ride.drop_name}
                  </p>
                  <p className="mt-1 text-sm text-[#6b7280]">
                    {ride.passenger_count} passengers • {ride.ride_type}
                  </p>
                  <p className="mt-2 text-xs text-[#9ca3af]">{formatDateTime(ride.created_at)}</p>
                </div>
              ))}
              {!rides.length ? <p className="text-sm text-[#6b7280]">No trip history available yet.</p> : null}
            </div>
          </div>
        </PanelCard>

        <PanelCard className="overflow-hidden p-0">
          <div className="border-b border-[#eef1f4] px-6 py-5">
            <div className="flex items-center gap-2 text-[#4b5563]">
              <Package className="h-4 w-4 text-[#2563eb]" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2563eb]">Parcel history</p>
            </div>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Recent parcels</h3>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              {parcels.slice(0, 5).map((parcel) => (
                <div key={parcel.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4">
                  <p className="font-semibold text-[#111827]">
                    {parcel.pickup_name} to {parcel.drop_name}
                  </p>
                  <p className="mt-1 text-sm text-[#6b7280]">
                    {parcel.parcel_weight} kg • {parcel.priority}
                  </p>
                  <p className="mt-2 text-xs text-[#9ca3af]">{formatDateTime(parcel.created_at)}</p>
                </div>
              ))}
              {!parcels.length ? <p className="text-sm text-[#6b7280]">No parcel history available yet.</p> : null}
            </div>
          </div>
        </PanelCard>
      </div>

      <PanelCard className="bg-[#f9fafb]">
        <div className="flex items-center gap-2 text-[#4b5563]">
          <UserCircle2 className="h-4 w-4 text-[#111111]" />
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">Session summary</p>
        </div>
        <p className="mt-3 text-base leading-7 text-[#6b7280]">
          This profile keeps identity, activity history, captain performance, and settings in one place without relying on the map view.
        </p>
      </PanelCard>
    </div>
  );
}
