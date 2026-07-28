import test from "node:test";
import assert from "node:assert/strict";
import { renderHazardPills } from "../src/lib/hazard-renderer.js";

test("multiple heat products render as separate pills inside a shared layout", () => {
  const html = renderHazardPills(["XH.A", "XH.W"]);

  assert.match(html, /class="hazard-list"/);
  assert.equal((html.match(/class="hazard-pill"/g) ?? []).length, 2);
  assert.match(html, />Extreme Heat Watch</);
  assert.match(html, />Extreme Heat Warning</);
  assert.match(html, /aria-label="Heat products: Extreme Heat Watch, Extreme Heat Warning"/);
});

test("a day without a heat product keeps the table placeholder", () => {
  assert.equal(renderHazardPills([]), '<span class="muted">—</span>');
});
