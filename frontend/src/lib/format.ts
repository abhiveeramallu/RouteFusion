export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatNumber(value: number, suffix = "") {
  return `${value.toLocaleString("en-IN")}${suffix}`;
}

export function formatCurrency(value: number) {
  return `Rs ${value.toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
}

export function formatDistance(value: number) {
  return `${value.toFixed(1)} km`;
}

export function formatMinutes(value: number) {
  return `${Math.round(value)} min`;
}

export function humanizeRecommendation(value: string) {
  return value.replace(/_/g, " ");
}
