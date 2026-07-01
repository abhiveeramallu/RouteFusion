import type { MapScenarioStat } from "../types";

type DockStatProps = {
  stat: MapScenarioStat;
};

const toneClasses = {
  neutral: "bg-white text-[#111827]",
  success: "bg-[#ecfdf3] text-[#0f8a4b]",
  accent: "bg-[#edf4ff] text-[#2563eb]",
  purple: "bg-[#efefff] text-[#4f46e5]",
};

export function DockStat({ stat }: DockStatProps) {
  const tone = stat.tone ?? "neutral";

  return (
    <div className={`min-w-[116px] rounded-2xl px-4 py-3 shadow-sm ${toneClasses[tone]}`}>
      <p className="text-[11px] font-medium uppercase tracking-[0.2em] opacity-70">{stat.label}</p>
      <p className="mt-2 text-sm font-semibold">{stat.value}</p>
    </div>
  );
}
