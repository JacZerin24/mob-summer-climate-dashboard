import {
  escapeHtml,
  formatDate,
  formatDeparture,
  formatNumber,
  formatPrecip,
  formatTemperature,
} from "../lib/formatters.js";

export const CHART_MODES = ["temperature", "precipitation"];

const WIDTH = 960;
const HEIGHT = 320;
const PADDING = { top: 28, right: 24, bottom: 46, left: 52 };

function xForIndex(index, length) {
  const usableWidth = WIDTH - PADDING.left - PADDING.right;
  return PADDING.left + (index / Math.max(length - 1, 1)) * usableWidth;
}

function yForValue(value, min, max) {
  const usableHeight = HEIGHT - PADDING.top - PADDING.bottom;
  return PADDING.top + ((max - value) / Math.max(max - min, 1)) * usableHeight;
}

function points(rows, key, min, max) {
  return rows
    .map((row, index) => {
      const value = row[key];
      if (!Number.isFinite(value)) return null;
      return `${xForIndex(index, rows.length).toFixed(1)},${yForValue(value, min, max).toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function tooltipItem(label, value) {
  return { label, value };
}

export function buildChartReadouts(rows, mode = "temperature") {
  const chartMode = CHART_MODES.includes(mode) ? mode : "temperature";
  return rows.map((row, index) => {
    const items = chartMode === "precipitation"
      ? [
          tooltipItem("Observed rain", formatPrecip(row.precip, row.precipTrace)),
          tooltipItem("Daily record", formatPrecip(row.recordPrecip)),
          tooltipItem("Record year(s)", row.recordPrecipYears || "—"),
          tooltipItem("YTD rainfall", formatPrecip(row.accumulatedPrecip)),
          tooltipItem("Normal YTD", formatPrecip(row.normalYtdPrecip)),
          tooltipItem("YTD departure", formatDeparture(row.precipDeparture, 2, "″")),
        ]
      : [
          tooltipItem("Observed high", formatTemperature(row.high)),
          tooltipItem("Normal high", formatTemperature(row.normalHigh, Number.isInteger(row.normalHigh) ? 0 : 1)),
          tooltipItem("High departure", formatDeparture(row.highDeparture)),
          tooltipItem("Observed low", formatTemperature(row.low)),
          tooltipItem("Normal low", formatTemperature(row.normalLow, Number.isInteger(row.normalLow) ? 0 : 1)),
          tooltipItem("Low departure", formatDeparture(row.lowDeparture)),
          tooltipItem("Maximum heat index", formatTemperature(row.maxHeatIndex)),
        ];

    return {
      date: formatDate(row.date, { weekday: "short", month: "short", day: "numeric", year: "numeric" }),
      x: Number(xForIndex(index, rows.length).toFixed(2)),
      items,
    };
  });
}

export function nearestChartIndex(xValue, rowCount) {
  if (!rowCount) return -1;
  const usableWidth = WIDTH - PADDING.left - PADDING.right;
  const ratio = (xValue - PADDING.left) / usableWidth;
  return Math.min(rowCount - 1, Math.max(0, Math.round(ratio * Math.max(rowCount - 1, 1))));
}

function chartToggle(mode) {
  return `
    <div class="chart-mode-toggle" role="group" aria-label="Chart variable">
      <button type="button" data-chart-mode="temperature" aria-pressed="${mode === "temperature"}">Temperature</button>
      <button type="button" data-chart-mode="precipitation" aria-pressed="${mode === "precipitation"}">Precipitation</button>
    </div>`;
}

function xAxisLabels(rows) {
  const start = rows[0]?.date;
  const middle = rows[Math.floor(rows.length / 2)]?.date;
  const end = rows.at(-1)?.date;
  return `
    <text class="axis-label" x="${PADDING.left}" y="${HEIGHT - 12}">${formatDate(start)}</text>
    <text class="axis-label" x="${WIDTH / 2}" y="${HEIGHT - 12}" text-anchor="middle">${formatDate(middle)}</text>
    <text class="axis-label" x="${WIDTH - PADDING.right}" y="${HEIGHT - 12}" text-anchor="end">${formatDate(end)}</text>`;
}

function interactiveShell(rows, mode, chartMarkup, title, ariaLabel, legend) {
  const readouts = buildChartReadouts(rows, mode);
  return `
    <section class="chart-panel" aria-labelledby="trend-heading" data-active-chart="${mode}">
      <div class="section-heading chart-heading">
        <div>
          <p class="eyebrow">Daily comparison</p>
          <h2 id="trend-heading">${escapeHtml(title)}</h2>
        </div>
        ${chartToggle(mode)}
      </div>
      <div class="chart-scroll">
        <div class="chart-stage">
          <svg
            class="interactive-chart"
            viewBox="0 0 ${WIDTH} ${HEIGHT}"
            role="img"
            tabindex="0"
            aria-label="${escapeHtml(ariaLabel)}. Hover for daily values, or focus the chart and use the left and right arrow keys."
            aria-describedby="chart-instructions chart-tooltip"
            data-view-width="${WIDTH}"
            data-plot-left="${PADDING.left}"
            data-plot-right="${WIDTH - PADDING.right}"
            data-readouts="${escapeHtml(JSON.stringify(readouts))}"
          >
            ${chartMarkup}
            <line class="chart-hover-guide" x1="${PADDING.left}" y1="${PADDING.top}" x2="${PADDING.left}" y2="${HEIGHT - PADDING.bottom}" />
          </svg>
          <div id="chart-tooltip" class="chart-tooltip" role="status" aria-live="polite" hidden>
            <p class="chart-tooltip-date" data-chart-tooltip-date></p>
            <dl data-chart-tooltip-values></dl>
          </div>
        </div>
      </div>
      <p id="chart-instructions" class="chart-instructions">Hover or tap the graph for a daily readout. Keyboard users can focus the graph and use ← and →.</p>
      <div class="chart-legend" aria-hidden="true">${legend}</div>
    </section>`;
}

function renderTemperatureChart(rows, mode) {
  const values = rows
    .flatMap((row) => [row.high, row.normalHigh, row.low, row.normalLow])
    .filter(Number.isFinite);
  if (!values.length) return "";

  const min = Math.floor(Math.min(...values) / 5) * 5 - 5;
  const max = Math.ceil(Math.max(...values) / 5) * 5 + 5;
  const ticks = Array.from({ length: 5 }, (_, index) => min + ((max - min) * index) / 4).reverse();
  const markup = `
    ${ticks.map((tick) => {
      const y = yForValue(tick, min, max);
      return `
        <line class="grid-line" x1="${PADDING.left}" y1="${y}" x2="${WIDTH - PADDING.right}" y2="${y}" />
        <text class="axis-label" x="${PADDING.left - 10}" y="${y + 4}" text-anchor="end">${formatNumber(tick, 0)}°</text>`;
    }).join("")}
    <polyline class="chart-line high" points="${points(rows, "high", min, max)}" />
    <polyline class="chart-line normal-high" points="${points(rows, "normalHigh", min, max)}" />
    <polyline class="chart-line low" points="${points(rows, "low", min, max)}" />
    <polyline class="chart-line normal-low" points="${points(rows, "normalLow", min, max)}" />
    ${rows.map((row, index) => Number.isFinite(row.high)
      ? `<circle class="chart-point high" cx="${xForIndex(index, rows.length)}" cy="${yForValue(row.high, min, max)}" r="3.2" />`
      : "").join("")}
    ${rows.map((row, index) => Number.isFinite(row.low)
      ? `<circle class="chart-point low" cx="${xForIndex(index, rows.length)}" cy="${yForValue(row.low, min, max)}" r="3.2" />`
      : "").join("")}
    ${xAxisLabels(rows)}`;
  const legend = `
    <span><i class="legend-swatch high"></i>Observed high</span>
    <span><i class="legend-swatch normal-high"></i>Normal high</span>
    <span><i class="legend-swatch low"></i>Observed low</span>
    <span><i class="legend-swatch normal-low"></i>Normal low</span>`;
  return interactiveShell(
    rows,
    mode,
    markup,
    "Observed temperatures versus normals",
    "Line chart of observed and normal high and low temperatures",
    legend,
  );
}

function renderPrecipitationChart(rows, mode) {
  const values = rows.flatMap((row) => [row.precip, row.recordPrecip]).filter(Number.isFinite);
  if (!values.length) return "";

  const max = Math.max(1, Math.ceil(Math.max(...values)));
  const min = 0;
  const ticks = Array.from({ length: 5 }, (_, index) => max - (max * index) / 4);
  const usableWidth = WIDTH - PADDING.left - PADDING.right;
  const barWidth = Math.max(2.5, Math.min(18, (usableWidth / Math.max(rows.length, 1)) * 0.66));
  const baseline = yForValue(0, min, max);
  const markup = `
    ${ticks.map((tick) => {
      const y = yForValue(tick, min, max);
      return `
        <line class="grid-line" x1="${PADDING.left}" y1="${y}" x2="${WIDTH - PADDING.right}" y2="${y}" />
        <text class="axis-label" x="${PADDING.left - 10}" y="${y + 4}" text-anchor="end">${formatNumber(tick, tick % 1 ? 2 : 0)}″</text>`;
    }).join("")}
    ${rows.map((row, index) => {
      if (!Number.isFinite(row.precip)) return "";
      const x = xForIndex(index, rows.length) - barWidth / 2;
      const y = yForValue(row.precip, min, max);
      const height = Math.max(row.precipTrace ? 2 : 0, baseline - y);
      const status = row.precipRecordStatus === "broken"
        ? " record-broken-bar"
        : row.precipRecordStatus === "tied"
          ? " record-tied-bar"
          : "";
      return `<rect class="precip-bar${status}" x="${x}" y="${baseline - height}" width="${barWidth}" height="${height}" rx="2" />`;
    }).join("")}
    <polyline class="chart-line precip-record" points="${points(rows, "recordPrecip", min, max)}" />
    ${xAxisLabels(rows)}`;
  const legend = `
    <span><i class="legend-swatch precip-observed"></i>Observed daily rainfall</span>
    <span><i class="legend-swatch precip-record"></i>Daily rainfall record</span>`;
  return interactiveShell(
    rows,
    mode,
    markup,
    "Daily rainfall versus records",
    "Bar chart of observed daily rainfall with the daily rainfall record",
    legend,
  );
}

export function renderTrendChart(rows, requestedMode = "temperature") {
  const mode = CHART_MODES.includes(requestedMode) ? requestedMode : "temperature";
  return mode === "precipitation"
    ? renderPrecipitationChart(rows, mode)
    : renderTemperatureChart(rows, mode);
}
