type PanelHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
};

export function PanelHeader({ eyebrow, title, description }: PanelHeaderProps) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#5B5BEF]">{eyebrow}</p>
      <h1 className="mt-3 text-[32px] font-semibold tracking-[-0.03em] text-[#111827]">{title}</h1>
      <p className="mt-3 max-w-xl text-[15px] leading-7 text-[#6b7280]">{description}</p>
    </div>
  );
}
