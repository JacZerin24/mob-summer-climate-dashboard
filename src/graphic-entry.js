import { openGraphicBuilder } from "./components/graphic-builder.js";
import "./graphic-builder-scroll.css";
import {
  AVAILABLE_YEARS,
  DEFAULT_STATION,
  DEFAULT_YEAR,
  PERIODS,
  getDefaultPeriod,
} from "./lib/constants.js";
import { loadStations } from "./lib/data-loader.js";

const stationsPromise = loadStations();

function currentDashboardState() {
  const params = new URLSearchParams(window.location.search);
  const requestedYear = Number(params.get("year"));
  const year = AVAILABLE_YEARS.includes(requestedYear) ? requestedYear : DEFAULT_YEAR;
  const requestedPeriod = params.get("period");
  const period = PERIODS.some((item) => item.value === requestedPeriod)
    ? requestedPeriod
    : getDefaultPeriod(year);
  return {
    station: params.get("station") ?? DEFAULT_STATION,
    year,
    period,
  };
}

function attachGraphicBuilderButton() {
  const actions = document.querySelector(".header-actions");
  if (!actions || actions.querySelector("#graphic-builder-button")) return;
  const button = document.createElement("button");
  button.id = "graphic-builder-button";
  button.className = "graphic-builder-trigger";
  button.type = "button";
  button.innerHTML = '<span aria-hidden="true">▣</span><span>Build graphic</span>';
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const stations = await stationsPromise;
      openGraphicBuilder({ stations, currentState: currentDashboardState() });
    } finally {
      button.disabled = false;
    }
  });
  const themeButton = actions.querySelector("#theme-toggle");
  actions.insertBefore(button, themeButton ?? null);
}

const observer = new MutationObserver(attachGraphicBuilderButton);
observer.observe(document.querySelector("#app"), { childList: true, subtree: true });
attachGraphicBuilderButton();
