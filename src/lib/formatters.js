export function formatNumber(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatTemperature(value, digits = 0) {
  return value == null ? "—" : `${formatNumber(value, digits)}°F`;
}

export function formatPrecip(value, trace = false) {
  if (trace) return "T";
  return value == null ? "—" : `${formatNumber(value, 2)}″`;
}

export function formatDeparture(value, digits = 1, unit = "°F") {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, digits)}${unit}`;
}

export function formatDate(value, options = { month: "short", day: "numeric" }) {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("en-US", options).format(date);
}

export function formatDateList(values) {
  if (!values?.length) return "—";
  return values.map((value) => formatDate(value)).join(", ");
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
