import "./styles.css";
import "./source-notes.css";
import "./theme.css";
import "./chart-interactions.css";
import { renderDailyTable } from "./components/daily-table.js";
import { renderHistoryPanel } from "./components/history-panel.js";
import { renderMonthTabs } from "./components/month-tabs.js";
import { renderStationSelector } from "./components/station-selector.js";
import { renderSummaryCards } from "./components/summary-cards.js";
import {
  CHART_MODES,
  nearestChartIndex,
  renderTrendChart,
} from "./components/trend-chart.js";
import { renderYearSelector } from "./components/year-selector.js";
import { filterPeriod, mergeClimateData, summarizePeriod } from "./lib/climate-calcs.js";
import {
  AVAILABLE_YEARS,
  DEFAULT_STATION,
  DEFAULT_YEAR,
  PERIODS,
  getDefaultPeriod,
} from "./lib/constants.js";
import { loadStationData, loadStations } from "./lib/data-loader.js";
import { escapeHtml, formatDate } from "./lib/formatters.js";

const app = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);
const requestedYear = Number(params.get("year"));
const startingYear = AVAILABLE_YEARS.includes(requestedYear) ? requestedYear : DEFAULT_YEAR;
const THEME_KEY = "mob-climate-theme";
const CHART_MODE_KEY = "mob-climate-chart-mode";

function storedChartMode() {
  try {
    const saved = window.localStorage.getItem(CHART_MODE_KEY);
    return CHART_MODES.includes(saved) ? saved : null;
  } catch {
    return null;
  }
}

const requestedChartMode = params.get("chart");
const startingChartMode = CHART_MODES.includes(requestedChartMode)
  ? requestedChartMode
  : storedChartMode() ?? "temperature";

const state = {
  station: params.get("station") ?? DEFAULT_STATION,
  year: startingYear,
  period: params.get("period") ?? getDefaultPeriod(startingYear),
  chartMode: startingChartMode,
};

let activeChartRows = [];

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function updateThemeToggle() {
  const button = document.querySelector("#theme-toggle");
  if (!button) return;
  const dark = currentTheme() === "dark";
  button.setAttribute("aria-pressed", String(dark));
  button.setAttribute("aria-label", `Switch to ${dark ? "light" : "dark"} mode`);
  const icon = button.querySelector("[data-theme-icon]");
  const label = button.querySelector("[data-theme-label]");
  if (icon) icon.textContent = dark ? "☀" : "☾";
  if (label) label.textContent = dark ? "Light mode" : "Dark mode";
}

function setTheme(theme, persist = true) {
  const resolved = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  if (persist) {
    try {
      window.localStorage.setItem(THEME_KEY, resolved);
    } catch {
      // The selected theme still applies for this page when storage is unavailable.
    }
  }
  updateThemeToggle();
}

function updateUrl() {
  const next = new URL(window.location.href);
  next.searchParams.set("station", state.station);
  next.searchParams.set("year", String(state.year));
  next.searchParams.set("period", state.period);
  next.searchParams.set("chart", state.chartMode);
  window.history.replaceState({}, "", next);
}

function setChartMode(mode) {
  if (!CHART_MODES.includes(mode) || mode === state.chartMode) return;
  state.chartMode = mode;
  try {
    window.localStorage.setItem(CHART_MODE_KEY, mode);
  } catch {
    // The selected graph still applies for this page when storage is unavailable.
  }
  updateUrl();
  const panel = document.querySelector(".chart-panel");
  if (panel) {
    panel.outerHTML = renderTrendChart(activeChartRows, state.chartMode);
    attachChartEvents();
  }
}

function attachChartEvents() {
  document.querySelectorAll("[data-chart-mode]").forEach((button) => {
    button.addEventListener("click", () => setChartMode(button.dataset.chartMode));
  });

  const svg = document.querySelector(".interactive-chart");
  if (!svg) return;

  let readouts = [];
  try {
    readouts = JSON.parse(svg.dataset.readouts ?? "[]");
  } catch {
    return;
  }
  if (!readouts.length) return;

  const stage = svg.closest(".chart-stage");
  const tooltip = stage?.querySelector(".chart-tooltip");
  const tooltipDate = tooltip?.querySelector("[data-chart-tooltip-date]");
  const tooltipValues = tooltip?.querySelector("[data-chart-tooltip-values]");
  const guide = svg.querySelector(".chart-hover-guide");
  const viewWidth = Number(svg.dataset.viewWidth) || 960;
  const plotLeft = Number(svg.dataset.plotLeft) || 52;
  const plotRight = Number(svg.dataset.plotRight) || 936;
  let currentIndex = 0;

  function hideReadout() {
    if (tooltip) tooltip.hidden = true;
    guide?.classList.remove("is-visible");
  }

  function showReadout(index) {
    currentIndex = Math.min(readouts.length - 1, Math.max(0, index));
    const readout = readouts[currentIndex];
    if (!readout || !tooltip || !tooltipDate || !tooltipValues) return;

    tooltipDate.textContent = readout.date;
    tooltipValues.replaceChildren();
    readout.items.forEach((item) => {
      const term = document.createElement("dt");
      term.textContent = item.label;
      const description = document.createElement("dd");
      description.textContent = item.value;
      tooltipValues.append(term, description);
    });

    tooltip.hidden = false;
    tooltip.style.left = `${(readout.x / viewWidth) * 100}%`;
    tooltip.classList.toggle("align-left", readout.x < viewWidth * 0.28);
    tooltip.classList.toggle("align-right", readout.x > viewWidth * 0.72);
    guide?.setAttribute("x1", String(readout.x));
    guide?.setAttribute("x2", String(readout.x));
    guide?.classList.add("is-visible");
    svg.dataset.currentIndex = String(currentIndex);
  }

  function indexFromPointer(event) {
    const rectangle = svg.getBoundingClientRect();
    if (!rectangle.width) return 0;
    const xValue = ((event.clientX - rectangle.left) / rectangle.width) * viewWidth;
    const clampedX = Math.min(plotRight, Math.max(plotLeft, xValue));
    return nearestChartIndex(clampedX, readouts.length);
  }

  svg.addEventListener("pointermove", (event) => showReadout(indexFromPointer(event)));
  svg.addEventListener("pointerleave", () => {
    if (document.activeElement !== svg) hideReadout();
  });
  svg.addEventListener("click", (event) => {
    svg.focus({ preventScroll: true });
    showReadout(indexFromPointer(event));
  });
  svg.addEventListener("focus", () => showReadout(Number(svg.dataset.currentIndex) || 0));
  svg.addEventListener("blur", hideReadout);
  svg.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") currentIndex = 0;
    if (event.key === "End") currentIndex = readouts.length - 1;
    if (event.key === "ArrowLeft") currentIndex = Math.max(0, currentIndex - 1);
    if (event.key === "ArrowRight") currentIndex = Math.min(readouts.length - 1, currentIndex + 1);
    showReadout(currentIndex);
  });
}

function attachEvents(stations) {
  document.querySelector("#station-select")?.addEventListener("change", async (event) => {
    state.station = event.target.value;
    updateUrl();
    await render(stations);
  });
  document.querySelector("#year-select")?.addEventListener("change", async (event) => {
    state.year = Number(event.target.value);
    state.period = getDefaultPeriod(state.year);
    updateUrl();
    await render(stations);
  });
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.period = button.dataset.period;
      updateUrl();
      await render(stations);
    });
  });
  document.querySelector("#theme-toggle")?.addEventListener("click", () => {
    setTheme(currentTheme() === "dark" ? "light" : "dark");
  });
  updateThemeToggle();
  attachChartEvents();
}

function renderDataStatus(season) {
  const dataThrough = season.dataThrough
    ? formatDate(season.dataThrough, { month: "long", day: "numeric", year: "numeric" })
    : "No completed days yet";
  const updated = season.lastUpdated
    ? new Date(season.lastUpdated).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })
    : "Not yet updated";
  const label = season.provisional ? "Provisional live data" : "Completed historical season";
  const counts = season.sourceCounts ?? {};
  const official = counts["NOAA/NCEI Daily Summaries"] ?? 0;
  const fallback = counts["IEM provisional fallback"] ?? 0;
  const mixed = counts.mixed ?? 0;
  const sourceSummary = `${official} official · ${fallback} fallback${mixed ? ` · ${mixed} mixed` : ""}`;
  return `
    <aside class="data-status" aria-label="Data status">
      <div><span>${escapeHtml(label)}</span><strong>Through ${escapeHtml(dataThrough)}</strong></div>
      <div><span>Daily source coverage</span><strong>${escapeHtml(sourceSummary)}</strong></div>
      <div><span>Last refreshed</span><strong>${escapeHtml(updated)}</strong></div>
    </aside>`;
}

function renderSourceFooter(season, climatology) {
  const normalSource = climatology.source?.normals ?? {};
  const recordSource = climatology.source?.records ?? {};
  const observationStation = season.sources?.stationId ?? normalSource.stationId ?? "NCEI station";
  const recordStation = recordSource.stationId ?? "ACIS climate thread";
  const recordThrough = recordSource.throughYear ?? state.year - 1;
  const auditUrl = `${import.meta.env.BASE_URL}data/audit/latest.json`;
  return `
    <footer>
      <p>
        High, low, and precipitation use NOAA/NCEI Daily Summaries for ${escapeHtml(observationStation)},
        with IEM used only as a labeled provisional fallback when a completed day is not yet available from NCEI.
        Daily normals are NOAA/NCEI 1991–2020 normals. Record comparisons and historical tables use the
        RCC ACIS operational climate series ${escapeHtml(recordStation)} through ${escapeHtml(recordThrough)},
        preserving the climate thread across station moves where applicable. Maximum heat index is derived by IEM.
        Recent heat alerts come from the official NWS API; older product history is reconstructed from IEM's archive
        of NWS-issued VTEC products. Current terminology is Heat Advisory, Extreme Heat Watch, and Extreme Heat Warning.
      </p>
      <p><a href="${auditUrl}">Open the latest machine-readable data audit</a>.</p>
    </footer>`;
}

async function render(stations) {
  app.innerHTML = '<main class="loading">Loading climate data…</main>';
  try {
    if (!stations.some((station) => station.code === state.station)) state.station = DEFAULT_STATION;
    if (!AVAILABLE_YEARS.includes(state.year)) state.year = DEFAULT_YEAR;
    if (!PERIODS.some((period) => period.value === state.period)) state.period = getDefaultPeriod(state.year);
    if (!CHART_MODES.includes(state.chartMode)) state.chartMode = "temperature";

    const stationMeta = stations.find((station) => station.code === state.station);
    const { season, climatology, history } = await loadStationData(state.station, state.year);
    const merged = mergeClimateData(season.observations ?? [], climatology.daily);
    const rows = filterPeriod(merged, state.period);
    activeChartRows = rows;
    const summary = summarizePeriod(rows, merged);
    const periodLabel = PERIODS.find((period) => period.value === state.period)?.label ?? "Season";

    app.innerHTML = `
      <header class="site-header">
        <div class="header-inner">
          <div>
            <p class="eyebrow">WFO MOB climate statistics</p>
            <h1>Summer Climate Dashboard</h1>
            <p class="header-copy">
              Audited daily observations, 1991–2020 normals, operational climate records, heat products, rainfall, and historical context for Mobile, Pensacola, Evergreen, Crestview, and Destin.
            </p>
          </div>
          <div class="header-actions">
            <div class="header-badge">Summer ${state.year}</div>
            <button id="theme-toggle" class="theme-toggle" type="button" aria-pressed="false">
              <span data-theme-icon aria-hidden="true">☾</span>
              <span data-theme-label>Dark mode</span>
            </button>
          </div>
        </div>
      </header>
      <main id="dashboard" class="dashboard">
        <section class="controls-panel" aria-label="Dashboard controls">
          ${renderStationSelector(stations, state.station)}
          ${renderYearSelector(AVAILABLE_YEARS, state.year)}
          <div class="station-title">
            <p class="eyebrow">Selected station</p>
            <h2>${escapeHtml(stationMeta.code)} · ${escapeHtml(stationMeta.name)}</h2>
          </div>
          ${renderMonthTabs(state.period)}
        </section>
        ${renderDataStatus(season)}
        ${renderSummaryCards(summary)}
        ${renderTrendChart(rows, state.chartMode)}
        ${renderDailyTable(rows, state.station, periodLabel, state.year)}
        ${renderHistoryPanel(history, state.period)}
        ${renderSourceFooter(season, climatology)}
      </main>
    `;
    attachEvents(stations);
  } catch (error) {
    console.error(error);
    app.innerHTML = `
      <main class="error-panel">
        <h1>Climate data could not be loaded</h1>
        <p>${escapeHtml(error.message)}</p>
      </main>`;
  }
}

loadStations().then(render).catch((error) => {
  app.innerHTML = `<main class="error-panel"><h1>Unable to start dashboard</h1><p>${escapeHtml(error.message)}</p></main>`;
});
