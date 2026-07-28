import { filterPeriod, mergeClimateData, summarizePeriod } from "./climate-calcs.js";
import { HAZARD_LABELS, PERIODS } from "./constants.js";

export const GRAPHIC_TYPES = [
  { value: "overview", label: "Period overview" },
  { value: "heat", label: "Heat summary" },
  { value: "rain", label: "Rainfall summary" },
  { value: "daily", label: "Daily snapshot" },
];

function temperature(value, digits = 0) {
  return Number.isFinite(value) ? `${Number(value).toFixed(digits)}°F` : "—";
}

function precipitation(value) {
  return Number.isFinite(value) ? `${Number(value).toFixed(2)}″` : "—";
}

function departure(value, digits = 1, suffix = "°F") {
  if (!Number.isFinite(value)) return "—";
  const rounded = Number(value).toFixed(digits);
  return `${value > 0 ? "+" : ""}${rounded}${suffix}`;
}

function dateLabel(value) {
  if (!value) return "—";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function dateList(values = []) {
  return values.length ? values.map(dateLabel).join(", ") : "—";
}

function compactDateList(values = []) {
  if (!values.length) return "none";
  const grouped = new Map();
  values.forEach((value) => {
    const parsed = new Date(`${value}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return;
    const month = parsed.toLocaleDateString("en-US", { month: "short" });
    const day = parsed.getDate();
    if (!grouped.has(month)) grouped.set(month, []);
    grouped.get(month).push(day);
  });
  if (!grouped.size) return values.join(", ");
  return [...grouped.entries()]
    .map(([month, days]) => `${month} ${[...new Set(days)].join(", ")}`)
    .join("; ");
}

function recordDetail(brokenDates = [], tiedDates = []) {
  return `B: ${compactDateList(brokenDates)} · T: ${compactDateList(tiedDates)}`;
}

function groupedTemperatureEvents(events = []) {
  if (!events.length) return "none";
  const grouped = new Map();
  events.forEach((event) => {
    if (!event?.type || !event?.date) return;
    if (!grouped.has(event.type)) grouped.set(event.type, []);
    grouped.get(event.type).push(event.date);
  });
  return [...grouped.entries()]
    .map(([type, dates]) => `${type}: ${compactDateList(dates)}`)
    .join("; ");
}

function temperatureRecordDetail(brokenEvents = [], tiedEvents = []) {
  return `B: ${groupedTemperatureEvents(brokenEvents)} · T: ${groupedTemperatureEvents(tiedEvents)}`;
}

function ordinal(value) {
  const number = Math.max(1, Number(value) || 1);
  const remainder100 = number % 100;
  if (remainder100 >= 11 && remainder100 <= 13) return `${number}th`;
  const suffix = number % 10 === 1 ? "st" : number % 10 === 2 ? "nd" : number % 10 === 3 ? "rd" : "th";
  return `${number}${suffix}`;
}

function historicalRainfallRank(total, history, period, endDate, displayYear) {
  if (!Number.isFinite(total) || !endDate) {
    return { value: "—", detail: "Historical comparison unavailable" };
  }
  const endKey = endDate.slice(5);
  const entries = history?.precipPeriodTotals?.[period]?.[endKey] ?? [];
  const historical = entries
    .map((entry) => ({ year: Number(entry?.[0]), amount: Number(entry?.[1]) }))
    .filter(
      (entry) =>
        Number.isFinite(entry.year) &&
        Number.isFinite(entry.amount) &&
        entry.year !== Number(displayYear),
    );
  if (!historical.length) {
    return { value: "—", detail: "Historical comparison unavailable" };
  }

  const current = { year: Number(displayYear), amount: Number(total) };
  const population = [...historical, current];
  const tolerance = 0.005;
  const wettestRank = 1 + population.filter((entry) => entry.amount > current.amount + tolerance).length;
  const driestRank = 1 + population.filter((entry) => entry.amount < current.amount - tolerance).length;
  const tied = population.filter((entry) => Math.abs(entry.amount - current.amount) <= tolerance).length > 1;
  const wettestAmount = Math.max(...population.map((entry) => entry.amount));
  const driestAmount = Math.min(...population.map((entry) => entry.amount));

  let side;
  if (wettestRank < driestRank) side = "wettest";
  else if (driestRank < wettestRank) side = "driest";
  else {
    side = wettestAmount - current.amount <= current.amount - driestAmount ? "wettest" : "driest";
  }

  const rank = side === "wettest" ? wettestRank : driestRank;
  const extremeAmount = side === "wettest" ? wettestAmount : driestAmount;
  const extremeYears = population
    .filter((entry) => Math.abs(entry.amount - extremeAmount) <= tolerance)
    .map((entry) => entry.year)
    .sort((a, b) => a - b);
  const value = `${tied ? "T-" : ""}${ordinal(rank)} ${side}`;
  const detail = `${side === "wettest" ? "Wettest" : "Driest"}: ${precipitation(extremeAmount)} (${extremeYears.join(", ")})`;
  return { value, detail };
}

function metric(id, label, value, detail = "") {
  return { id, label, value, detail };
}

function wettestDay(rows) {
  const valid = rows.filter((row) => Number.isFinite(row.precip));
  if (!valid.length) return { value: null, dates: [] };
  const value = Math.max(...valid.map((row) => row.precip));
  return {
    value,
    dates: valid.filter((row) => row.precip === value).map((row) => row.date),
  };
}

function normalizedHazards(hazards = []) {
  return hazards.map((hazard) => {
    if (hazard === "EH.A") return "XH.A";
    if (hazard === "EH.W") return "XH.W";
    return hazard;
  });
}

function overviewMetrics(rows, summary) {
  return [
    metric(
      "average-high",
      "Average high",
      temperature(summary.observedHighAverage, 1),
      `Normal ${temperature(summary.normalHighAverage, 1)} · ${departure(summary.highDeparture)}`,
    ),
    metric(
      "average-low",
      "Average low",
      temperature(summary.observedLowAverage, 1),
      `Normal ${temperature(summary.normalLowAverage, 1)} · ${departure(summary.lowDeparture)}`,
    ),
    metric(
      "period-rainfall",
      "Period rainfall",
      precipitation(summary.totalPrecip),
      `${summary.dayCount} completed days`,
    ),
    metric("hottest-high", "Hottest high", temperature(summary.hottest.value), dateList(summary.hottest.dates)),
    metric(
      "temperature-records",
      "Temp records (B/T)",
      `${summary.temperatureRecordsBroken} / ${summary.temperatureRecordsTied}`,
      temperatureRecordDetail(summary.temperatureRecordBrokenEvents, summary.temperatureRecordTiedEvents),
    ),
    metric(
      "rainfall-records",
      "Rain records (B/T)",
      `${summary.precipRecordsBroken} / ${summary.precipRecordsTied}`,
      recordDetail(summary.precipRecordBrokenDates, summary.precipRecordTiedDates),
    ),
  ];
}

function heatMetrics(summary) {
  return [
    metric("hottest-high", "Hottest high", temperature(summary.hottest.value), dateList(summary.hottest.dates)),
    metric(
      "maximum-heat-index",
      "Maximum heat index",
      temperature(summary.maxHeatIndex.value),
      dateList(summary.maxHeatIndex.dates),
    ),
    metric("days-90", "90° days", String(summary.daysAtOrAbove90), "High at or above 90°F"),
    metric("days-100", "100° days", String(summary.daysAtOrAbove100), "High at or above 100°F"),
    metric("heat-advisory-days", "Heat Advisory days", String(summary.hazardCounts["HT.Y"] ?? 0), "Product-days"),
    metric(
      "watch-warning-days",
      "Watch / Warning days",
      `${summary.hazardCounts["XH.A"] ?? 0} / ${summary.hazardCounts["XH.W"] ?? 0}`,
      "Extreme Heat Watch / Warning",
    ),
  ];
}

function rainfallMetrics(rows, summary, history, options) {
  const wettest = wettestDay(rows);
  const rainDays = rows.filter(
    (row) => row.precipTrace || (Number.isFinite(row.precip) && row.precip > 0),
  ).length;
  const ranking = historicalRainfallRank(
    summary.totalPrecip,
    history,
    options.period,
    rows.at(-1)?.date,
    options.year,
  );
  return [
    metric(
      "period-rainfall",
      "Period rainfall",
      precipitation(summary.totalPrecip),
      `${rainDays} day${rainDays === 1 ? "" : "s"} with rain`,
    ),
    metric("ytd-rainfall", "YTD rainfall", precipitation(summary.endingAccumulatedPrecip), "At the end of the selected period"),
    metric(
      "ytd-rainfall-departure",
      "YTD departure",
      departure(summary.endingPrecipDeparture, 2, "″"),
      "Compared with 1991–2020 normal",
    ),
    metric("wettest-day", "Wettest day", precipitation(wettest.value), dateList(wettest.dates)),
    metric(
      "rain-records-broken",
      "Daily records broken",
      String(summary.precipRecordsBroken),
      compactDateList(summary.precipRecordBrokenDates),
    ),
    metric("rainfall-rank", "Period rainfall rank", ranking.value, ranking.detail),
  ];
}

function dailyMetrics(row) {
  if (!row) {
    return [
      metric("daily-high", "High", "—", "No completed observation"),
      metric("daily-low", "Low", "—", "No completed observation"),
      metric("daily-heat-index", "Maximum heat index", "—"),
      metric("daily-rainfall", "Rainfall", "—"),
      metric("daily-ytd-rainfall", "YTD rainfall", "—"),
      metric("heat-products", "Heat products", "None"),
    ];
  }
  const hazards = normalizedHazards(row.hazards)
    .map((hazard) => HAZARD_LABELS[hazard] ?? hazard)
    .join(" · ");
  return [
    metric("daily-high", "High", temperature(row.high), `Departure ${departure(row.highDeparture)}`),
    metric("daily-low", "Low", temperature(row.low), `Departure ${departure(row.lowDeparture)}`),
    metric("daily-heat-index", "Maximum heat index", temperature(row.maxHeatIndex), ""),
    metric("daily-rainfall", "Rainfall", row.precipTrace ? "Trace" : precipitation(row.precip), ""),
    metric(
      "daily-ytd-rainfall",
      "YTD rainfall",
      precipitation(row.accumulatedPrecip),
      `Departure ${departure(row.precipDeparture, 2, "″")}`,
    ),
    metric("heat-products", "Heat products", hazards || "None", ""),
  ];
}

export function graphicPeriodLabel(period) {
  return PERIODS.find((item) => item.value === period)?.label ?? "Season";
}

export function defaultGraphicTitle(type, year, period, date) {
  if (type === "daily") return `Climate Snapshot · ${dateLabel(date)}, ${year}`;
  const label = graphicPeriodLabel(period);
  const titles = {
    overview: "Summer Climate Overview",
    heat: "Summer Heat Summary",
    rain: "Summer Rainfall Summary",
  };
  return `${titles[type] ?? "Summer Climate Summary"} · ${label} ${year}`;
}

export function defaultGraphicDate(year, now = new Date()) {
  const start = `${year}-06-01`;
  const end = `${year}-09-30`;
  if (year < now.getFullYear()) return end;
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const iso = yesterday.toISOString().slice(0, 10);
  if (iso < start) return start;
  if (iso > end) return end;
  return iso;
}

export function stationGraphicModel(meta, season, climatology, options) {
  const merged = mergeClimateData(season.observations ?? [], climatology.daily ?? {});
  const rows =
    options.type === "daily"
      ? merged.filter((row) => row.date === options.date)
      : filterPeriod(merged, options.period);
  const summary = summarizePeriod(rows, merged);
  const history = climatology.history ?? {};
  let metrics;
  if (options.type === "heat") metrics = heatMetrics(summary);
  else if (options.type === "rain") metrics = rainfallMetrics(rows, summary, history, options);
  else if (options.type === "daily") metrics = dailyMetrics(rows[0]);
  else metrics = overviewMetrics(rows, summary);
  return {
    code: meta.code,
    name: meta.name,
    city: meta.city,
    dataThrough: season.dataThrough,
    provisional: Boolean(season.provisional),
    metrics,
  };
}

export function graphicGrid(count) {
  const safeCount = Math.max(1, Math.min(4, Number(count) || 1));
  if (safeCount === 1) {
    return [{ x: 120, y: 220, width: 1680, height: 610 }];
  }
  if (safeCount === 2) {
    return [
      { x: 85, y: 225, width: 855, height: 610 },
      { x: 980, y: 225, width: 855, height: 610 },
    ];
  }
  const slots = [
    { x: 85, y: 180, width: 855, height: 330 },
    { x: 980, y: 180, width: 855, height: 330 },
    { x: 85, y: 545, width: 855, height: 330 },
    { x: 980, y: 545, width: 855, height: 330 },
  ];
  if (safeCount === 3) {
    slots[2] = { x: 532, y: 545, width: 855, height: 330 };
  }
  return slots.slice(0, safeCount);
}
