import type { ReactNode } from "react";

type PanelCardProps = {
  children: ReactNode;
  className?: string;
};

export function PanelCard({ children, className = "" }: PanelCardProps) {
  return (
    <section
      className={`rounded-[28px] border border-[#e7eaee] bg-white p-5 shadow-[0_18px_40px_rgba(15,23,42,0.06)] ${className}`}
    >
      {children}
    </section>
  );
}
