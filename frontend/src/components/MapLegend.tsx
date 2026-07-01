const legendItems = [
  { label: "Passenger route", color: "#22C55E" },
  { label: "Parcel route", color: "#3B82F6" },
  { label: "Optimized route", color: "#5B5BEF" },
];

export function MapLegend() {
  return (
    <div className="flex flex-wrap gap-2">
      {legendItems.map((item) => (
        <div
          key={item.label}
          className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/95 px-3 py-2 text-xs font-medium text-[#111827] shadow-sm backdrop-blur"
        >
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </div>
      ))}
    </div>
  );
}
