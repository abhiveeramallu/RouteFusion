import type { ReactNode } from "react";

type GlassCardProps = {
  children: ReactNode;
  className?: string;
};

export function GlassCard({ children, className = "" }: GlassCardProps) {
  return (
    <div
      className={`rounded-[28px] border border-white/10 bg-slateCard/70 p-6 shadow-glow backdrop-blur-xl ${className}`}
    >
      {children}
    </div>
  );
}
