import type { LucideIcon } from "lucide-react";

import { GlassCard } from "./GlassCard";

type MetricCardProps = {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "primary" | "secondary" | "accent" | "rose";
  note?: string;
};

const toneClasses = {
  primary: "from-primary/30 to-primary/5 text-primary",
  secondary: "from-secondary/30 to-secondary/5 text-secondary",
  accent: "from-accent/30 to-accent/5 text-accent",
  rose: "from-peach/30 to-peach/5 text-peach",
};

export function MetricCard({
  icon: Icon,
  label,
  value,
  tone = "primary",
  note,
}: MetricCardProps) {
  return (
    <GlassCard className="relative overflow-hidden">
      <div className={`absolute inset-0 bg-gradient-to-br ${toneClasses[tone]} opacity-70`} />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-300">{label}</p>
          <p className="mt-4 font-display text-3xl font-semibold text-white">{value}</p>
          {note ? <p className="mt-2 text-sm text-slate-300">{note}</p> : null}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-white">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </GlassCard>
  );
}
