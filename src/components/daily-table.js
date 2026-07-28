import "../rain-records.css";
import "../hazard-layout.css";
import {
  escapeHtml,
  formatDate,
  formatDeparture,
  formatPrecip,
  formatTemperature,
} from "../lib/formatters.js";
import { renderHazardPills } from "../lib/hazard-renderer.js";

function recordClass(status) {
  return status === "broken" ? "record-broken" : status === "tied" ? "record-tied" : "";
}

function dailyRainRecord(row) {
  const years = row.recordPrecipYears ? escapeHtml(row.recordPrecipYears) : "—";
  return `
    <span class="record-rain-value">${formatPrecip(row.recordPrecip)}</span>
    <span class="record-rain-years">${years}</span>`;
}

export function renderDailyTable(rows, station, periodLabel, year) {
  if (!rows.length) {
    return `
      <section aria-labelledby="daily-heading">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Official observations and climatology</p>
            <h2 id="daily-heading">Daily climate table</h2>
          </div>
        </div>
        <div class="empty-panel">
          <h3>No observations are available for ${escapeHtml(periodLabel)} ${year} yet.</h3>
          <p>The live updater publishes completed daily summaries as they become available.</p>
        </div>
      </section>`;
  }

  return `
    <section aria-labelledby="daily-heading">
      <div class="section-heading">
        <div>
          <p class="eyebrow">NOAA/NCEI observations · 1991–2020 normals</p>
          <h2 id="daily-heading">Daily climate table</h2>
        </div>
        <p>Orange = tied daily record · dark orange = broken daily record</p>
      </div>
      <div class="table-wrap">
        <table class="climate-table">
          <caption>${escapeHtml(station)} daily climate statistics for ${escapeHtml(periodLabel)} ${year}</caption>
          <thead>
            <tr>
              <th scope="col">Date</th><th scope="col">Heat product</th><th scope="col">High</th><th scope="col">Normal high</th><th scope="col">High dep.</th><th scope="col">Record high</th><th scope="col">Record year(s)</th><th scope="col">Low</th><th scope="col">Normal low</th><th scope="col">Low dep.</th><th scope="col">Warm-low record</th><th scope="col">Record year(s)</th><th scope="col">Max HI*</th><th scope="col">Rain</th><th scope="col">Daily rain record</th><th scope="col">YTD rain</th><th scope="col">Normal YTD</th><th scope="col">YTD dep.</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <th scope="row">${formatDate(row.date, { month: "short", day: "numeric", weekday: "short" })}</th>
                <td class="hazard-cell">${renderHazardPills(row.hazards)}</td>
                <td class="${recordClass(row.highRecordStatus)}">${formatTemperature(row.high)}</td>
                <td>${formatTemperature(row.normalHigh, Number.isInteger(row.normalHigh) ? 0 : 1)}</td>
                <td class="${row.highDeparture > 0 ? "positive" : row.highDeparture < 0 ? "negative" : ""}">${formatDeparture(row.highDeparture)}</td>
                <td>${formatTemperature(row.recordHigh)}</td>
                <td>${escapeHtml(row.recordHighYears ?? "—")}</td>
                <td class="${recordClass(row.warmLowRecordStatus)}">${formatTemperature(row.low)}</td>
                <td>${formatTemperature(row.normalLow, Number.isInteger(row.normalLow) ? 0 : 1)}</td>
                <td class="${row.lowDeparture > 0 ? "positive" : row.lowDeparture < 0 ? "negative" : ""}">${formatDeparture(row.lowDeparture)}</td>
                <td>${formatTemperature(row.recordWarmLow)}</td>
                <td>${escapeHtml(row.recordWarmLowYears ?? "—")}</td>
                <td>${formatTemperature(row.maxHeatIndex)}</td>
                <td class="${recordClass(row.precipRecordStatus)}">${formatPrecip(row.precip, row.precipTrace)}</td>
                <td class="rain-record-cell">${dailyRainRecord(row)}</td>
                <td>${formatPrecip(row.accumulatedPrecip)}</td>
                <td>${formatPrecip(row.normalYtdPrecip)}</td>
                <td class="${row.precipDeparture > 0 ? "positive-rain" : row.precipDeparture < 0 ? "negative-rain" : ""}">${formatDeparture(row.precipDeparture, 2, "″")}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
      <p class="source-note">*Maximum heat index is a derived IEM value. High, low, and rainfall preferentially use NOAA/NCEI Daily Summaries. Daily records use the RCC ACIS operational climate series.</p>
    </section>`;
}
