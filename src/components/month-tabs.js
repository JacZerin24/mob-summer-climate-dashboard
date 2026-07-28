import { PERIODS } from "../lib/constants.js";

export function renderMonthTabs(activePeriod) {
  return `
    <div class="period-tabs" role="tablist" aria-label="Climate period">
      ${PERIODS.map(
        (period) => `
          <button
            type="button"
            class="period-tab ${period.value === activePeriod ? "is-active" : ""}"
            data-period="${period.value}"
            role="tab"
            aria-selected="${period.value === activePeriod}"
          >
            ${period.label}
          </button>`,
      ).join("")}
    </div>
  `;
}
