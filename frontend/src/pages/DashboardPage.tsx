import { Fuel, ShieldCheck, Sparkles, TrendingUp, Truck } from "lucide-react";

import { PanelCard } from "../components/PanelCard";
import { PanelHeader } from "../components/PanelHeader";
import { useRouteFusion } from "../context/RouteFusionContext";
import { formatDateTime, formatNumber } from "../lib/format";
import type { DashboardMetrics } from "../types";

function metricCards(metrics: DashboardMetrics) {
  return [
    { label: "Total rides", value: formatNumber(metrics.total_rides), icon: Truck, tone: "text-[#111111]" },
    { label: "Total parcels", value: formatNumber(metrics.total_parcels), icon: Sparkles, tone: "text-[#5B5BEF]" },
    { label: "Combined trips", value: formatNumber(metrics.total_combined_trips), icon: TrendingUp, tone: "text-[#22C55E]" },
    { label: "Fuel saved", value: formatNumber(metrics.estimated_fuel_saved, " L"), icon: Fuel, tone: "text-[#22C55E]" },
    { label: "Efficiency score", value: `${metrics.average_efficiency_score}%`, icon: TrendingUp, tone: "text-[#2563eb]" },
    { label: "Active captains", value: formatNumber(metrics.active_captains), icon: ShieldCheck, tone: "text-[#5B5BEF]" },
  ];
}

export function DashboardPage() {
  const { dashboard, rides, parcels } = useRouteFusion();
  const metrics = dashboard?.metrics ?? {
    total_rides: 0,
    total_parcels: 0,
    total_combined_trips: 0,
    active_captains: 0,
    average_efficiency_score: 0,
    estimated_fuel_saved: 0,
    captain_total_earnings: 0,
    captain_rides_handled: 0,
    captain_parcels_handled: 0,
    captain_combined_trips: 0,
  };
  const cards = metricCards(metrics);

  const chartData = [
    { label: "Rides", value: metrics.total_rides, color: "bg-[#111111]" },
    { label: "Parcels", value: metrics.total_parcels, color: "bg-[#2563eb]" },
    { label: "Combined", value: metrics.total_combined_trips, color: "bg-[#22C55E]" },
    { label: "Captains", value: metrics.active_captains, color: "bg-[#5B5BEF]" },
  ];
  const maxChartValue = Math.max(...chartData.map((item) => item.value), 1);

  return (
    <div className="space-y-6 p-6">
      <PanelHeader
        eyebrow="Dashboard"
        title="Demand, supply, and savings"
        description="Operations analytics stay fully data-focused here with statistics cards, charts, and tables only."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map(({ label, value, icon: Icon, tone }) => (
          <PanelCard key={label}>
            <div className="flex items-center gap-2 text-[#4b5563]">
              <Icon className={`h-4 w-4 ${tone}`} />
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">{label}</p>
            </div>
            <p className="mt-3 text-2xl font-semibold text-[#111827]">{value}</p>
          </PanelCard>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PanelCard>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Request mix</p>
          <div className="mt-5 space-y-4">
            {chartData.map((item) => (
              <div key={item.label}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium text-[#111827]">{item.label}</span>
                  <span className="text-[#6b7280]">{formatNumber(item.value)}</span>
                </div>
                <div className="mt-2 h-3 rounded-full bg-[#f3f4f6]">
                  <div
                    className={`h-3 rounded-full ${item.color}`}
                    style={{ width: `${Math.max((item.value / maxChartValue) * 100, item.value ? 12 : 0)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </PanelCard>

        <PanelCard className="bg-[#f9fafb]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5B5BEF]">Efficiency chart</p>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <div className="rounded-[24px] bg-white p-4 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">Efficiency</p>
              <p className="mt-2 text-2xl font-semibold text-[#111827]">{metrics.average_efficiency_score}%</p>
            </div>
            <div className="rounded-[24px] bg-white p-4 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">Fuel saved</p>
              <p className="mt-2 text-2xl font-semibold text-[#111827]">{formatNumber(metrics.estimated_fuel_saved, " L")}</p>
            </div>
            <div className="rounded-[24px] bg-white p-4 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">Captains</p>
              <p className="mt-2 text-2xl font-semibold text-[#111827]">{formatNumber(metrics.active_captains)}</p>
            </div>
          </div>
        </PanelCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PanelCard className="overflow-hidden p-0">
          <div className="border-b border-[#eef1f4] px-6 py-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#5B5BEF]">Recent activity</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Latest operational events</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[#f9fafb] text-[#6b7280]">
                <tr>
                  <th className="px-6 py-4 font-medium">Time</th>
                  <th className="px-6 py-4 font-medium">Type</th>
                  <th className="px-6 py-4 font-medium">Route</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium">Efficiency</th>
                </tr>
              </thead>
              <tbody>
                {dashboard?.recent_activity.map((item) => (
                  <tr key={`${item.activity_type}-${item.timestamp}-${item.route_label}`} className="border-t border-[#eef1f4]">
                    <td className="px-6 py-4 text-[#6b7280]">{formatDateTime(item.timestamp)}</td>
                    <td className="px-6 py-4 text-[#111827]">{item.activity_type}</td>
                    <td className="px-6 py-4 text-[#6b7280]">{item.route_label}</td>
                    <td className="px-6 py-4 text-[#111827]">{item.status}</td>
                    <td className="px-6 py-4 text-[#6b7280]">
                      {item.efficiency_score !== null ? `${item.efficiency_score}%` : "-"}
                    </td>
                  </tr>
                )) ?? null}
              </tbody>
            </table>
          </div>
        </PanelCard>

        <PanelCard className="overflow-hidden p-0">
          <div className="border-b border-[#eef1f4] px-6 py-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#5B5BEF]">Queue tables</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#111827]">Latest ride and parcel requests</h3>
          </div>
          <div className="grid divide-y divide-[#eef1f4]">
            <div className="px-6 py-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22C55E]">Rides</p>
              <div className="mt-4 space-y-3">
                {rides.slice(0, 3).map((ride) => (
                  <div key={ride.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4 text-sm">
                    <p className="font-semibold text-[#111827]">
                      {ride.pickup_name} to {ride.drop_name}
                    </p>
                    <p className="mt-1 text-[#6b7280]">
                      {ride.passenger_count} passengers • {ride.ride_type}
                    </p>
                  </div>
                ))}
                {!rides.length ? <p className="text-sm text-[#6b7280]">No ride requests available.</p> : null}
              </div>
            </div>
            <div className="px-6 py-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#2563eb]">Parcels</p>
              <div className="mt-4 space-y-3">
                {parcels.slice(0, 3).map((parcel) => (
                  <div key={parcel.id} className="rounded-2xl border border-[#e7eaee] bg-white p-4 text-sm">
                    <p className="font-semibold text-[#111827]">
                      {parcel.pickup_name} to {parcel.drop_name}
                    </p>
                    <p className="mt-1 text-[#6b7280]">
                      {parcel.parcel_weight} kg • {parcel.priority}
                    </p>
                  </div>
                ))}
                {!parcels.length ? <p className="text-sm text-[#6b7280]">No parcel requests available.</p> : null}
              </div>
            </div>
          </div>
        </PanelCard>
      </div>
    </div>
  );
}
