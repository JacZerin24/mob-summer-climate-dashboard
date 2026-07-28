import {
  formatDate,
  formatDateList,
  formatDeparture,
  formatPrecip,
  formatTemperature,
} from "../lib/formatters.js";
import { HAZARD_LABELS } from "../lib/constants.js";

function card(label, value, detail = "") {
  return `
    <article class="summary-card">
      <p class="summary-label">${label}</p>
      <p class="summary-value">${value}</p>
      ${detail ? `<p class="summary-detail">${detail}</p>` : ""}
    </article>
  `;
}

function firstOfSeason(value) {
  return value ? `First of season: ${formatDate(value, { month: "short", day: "numeric" })}` : "None yet this season";
}

export function renderSummaryCards(summary) {
  const hazardDetail = Object.entries(summary.hazardCounts)
    .map(([code, count]) => `${HAZARD_LABELS[code] ?? code}: ${count}`)
    .join(" · ");

  return `
    <section aria-labelledby="summary-heading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Calculated from audited daily rows</p>
          <h2 id="summary-heading">Period summary</h2>
        </div>
        <p>${summary.dayCount} days</p>
      </div>
      <div class="summary-grid">
        ${card("Average high", formatTemperature(summary.observedHighAverage, 1), `${formatDeparture(summary.highDeparture)} from normal · ${summary.daysAboveNormal} days above normal`)}
        ${card("Average low", formatTemperature(summary.observedLowAverage, 1), `${formatDeparture(summary.lowDeparture)} from normal`)}
        ${card("Hottest day", formatTemperature(summary.hottest.value), formatDateList(summary.hottest.dates))}
        ${card("Warmest night", formatTemperature(summary.warmestLow.value), formatDateList(summary.warmestLow.dates))}
        ${card("Rainfall", formatPrecip(summary.totalPrecip), `${formatDeparture(summary.endingPrecipDeparture, 2, "″")} YTD departure`)}
        ${card("Maximum heat index*", formatTemperature(summary.maxHeatIndex.value), `Average ${formatTemperature(summary.averageHeatIndex, 1)}`)}
        ${card("Heat product-days", String(Object.values(summary.hazardCounts).reduce((a, b) => a + b, 0)), hazardDetail)}
        ${card("90°F days", String(summary.daysAtOrAbove90), firstOfSeason(summary.first90DegreeDay))}
        ${card("100°F days", String(summary.daysAtOrAbove100), firstOfSeason(summary.first100DegreeDay))}
        ${card("Warm nights", `${summary.nightsAtOrAbove80} ≥80°F`, `${summary.nightsAboveNormal} above normal`)}
        ${card("Daily record highs", `${summary.highRecordsBroken} broken`, `${summary.highRecordsTied} tied`)}
        ${card("Warm-low records", `${summary.warmLowRecordsBroken} broken`, `${summary.warmLowRecordsTied} tied`)}
        ${card("Daily rainfall records", `${summary.precipRecordsBroken} broken`, `${summary.precipRecordsTied} tied`)}
        ${card("Accumulated rainfall", formatPrecip(summary.endingAccumulatedPrecip), "Calendar-year total at period end")}
      </div>
    </section>
  `;
}
