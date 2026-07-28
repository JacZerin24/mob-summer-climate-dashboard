import test from "node:test";
import assert from "node:assert/strict";
import {
  buildChartReadouts,
  nearestChartIndex,
  renderTrendChart,
} from "../src/components/trend-chart.js";

const rows = [
  {
    date: "2026-06-01",
    high: 94,
    normalHigh: 90.2,
    highDeparture: 3.8,
    low: 76,
    normalLow: 71.4,
    lowDeparture: 4.6,
    maxHeatIndex: 103,
    precip: 0.5,
    precipTrace: false,
    recordPrecip: 2.25,
    recordPrecipYears: "1989",
    accumulatedPrecip: 20.5,
    normalYtdPrecip: 21.1,
    precipDeparture: -0.6,
    precipRecordStatus: "none",
  },
  {
    date: "2026-06-02",
    high: 100,
    normalHigh: 90.3,
    highDeparture: 9.7,
    low: 79,
    normalLow: 71.5,
    lowDeparture: 7.5,
    maxHeatIndex: 112,
    precip: 3.1,
    precipTrace: false,
    recordPrecip: 2.8,
    recordPrecipYears: "1964",
    accumulatedPrecip: 23.6,
    normalYtdPrecip: 21.3,
    precipDeparture: 2.3,
    precipRecordStatus: "broken",
  },
];

test("temperature readouts contain daily observed, normal, and heat-index values", () => {
  const readouts = buildChartReadouts(rows, "temperature");
  assert.equal(readouts.length, 2);
  assert.equal(readouts[0].items.find((item) => item.label === "Observed high").value, "94°F");
  assert.equal(readouts[0].items.find((item) => item.label === "Normal low").value, "71.4°F");
  assert.equal(readouts[1].items.find((item) => item.label === "Maximum heat index").value, "112°F");
});

test("precipitation readouts contain records and YTD comparisons", () => {
  const readouts = buildChartReadouts(rows, "precipitation");
  assert.equal(readouts[1].items.find((item) => item.label === "Observed rain").value, "3.10″");
  assert.equal(readouts[1].items.find((item) => item.label === "Daily record").value, "2.80″");
  assert.equal(readouts[1].items.find((item) => item.label === "Record year(s)").value, "1964");
  assert.equal(readouts[1].items.find((item) => item.label === "YTD departure").value, "+2.30″");
});

test("nearest chart index clamps pointer positions to available rows", () => {
  assert.equal(nearestChartIndex(-100, 2), 0);
  assert.equal(nearestChartIndex(960, 2), 1);
  assert.equal(nearestChartIndex(500, 0), -1);
});

test("rendered chart can switch between temperature and precipitation views", () => {
  const temperature = renderTrendChart(rows, "temperature");
  const precipitation = renderTrendChart(rows, "precipitation");

  assert.match(temperature, /Observed temperatures versus normals/);
  assert.match(temperature, /data-chart-mode="precipitation"/);
  assert.match(temperature, /data-readouts=/);
  assert.match(precipitation, /Daily rainfall versus records/);
  assert.match(precipitation, /class="precip-bar record-broken-bar"/);
  assert.match(precipitation, /Daily rainfall record/);
});
