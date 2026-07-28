import { escapeHtml } from "../lib/formatters.js";

export function renderStationSelector(stations, activeStation) {
  return `
    <div class="control-group">
      <label for="station-select">Climate station</label>
      <select id="station-select">
        ${stations
          .map(
            (station) => `
              <option value="${escapeHtml(station.code)}" ${
                station.code === activeStation ? "selected" : ""
              }>
                ${escapeHtml(station.code)} — ${escapeHtml(station.name)}
              </option>`,
          )
          .join("")}
      </select>
    </div>
  `;
}
