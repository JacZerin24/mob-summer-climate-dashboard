import { HAZARD_LABELS } from "./constants.js";
import { escapeHtml } from "./formatters.js";

export function renderHazardPills(hazards = []) {
  if (!hazards.length) return '<span class="muted">—</span>';

  const labels = hazards.map((hazard) => HAZARD_LABELS[hazard] ?? hazard);
  const pills = hazards.map((hazard, index) => {
    const label = labels[index];
    return `<span class="hazard-pill" title="${escapeHtml(`${label} (${hazard})`)}">${escapeHtml(label)}</span>`;
  }).join("");

  return `<div class="hazard-list" aria-label="Heat products: ${escapeHtml(labels.join(", "))}">${pills}</div>`;
}
