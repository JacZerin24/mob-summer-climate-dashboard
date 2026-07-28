import test from "node:test";
import assert from "node:assert/strict";
import { getRecordStatus, mergeClimateData, summarizePeriod } from "../src/lib/climate-calcs.js";

test("record comparisons distinguish ties and new records", () => {
  assert.equal(getRecordStatus(100, 99), "broken");
  assert.equal(getRecordStatus(99, 99), "tied");
  assert.equal(getRecordStatus(98, 99), "none");
  assert.equal(getRecordStatus(null, 99), "none");
});

test("summary calculations use merged official climatology fields", () => {
  const observations = [
    { date: "2026-06-01", high: 100, low: 80, precip: 0.5, accumulatedPrecip: 10.5, maxHeatIndex: 110, hazards: ["HT.Y"] },
    { date: "2026-06-02", high: 98, low: 78, precip: 0, accumulatedPrecip: 10.5, maxHeatIndex: 105, hazards: ["XH.W"] },
  ];
  const climatology = {
    "06-01": {
      normalHigh: 90,
      normalLow: 70,
      recordHigh: 100,
      recordWarmLow: 79,
      recordPrecip: 0.5,
      recordPrecipYears: "1998",
      normalYtdPrecip: 10,
    },
    "06-02": {
      normalHigh: 91,
      normalLow: 71,
      recordHigh: 99,
      recordWarmLow: 78,
      recordPrecip: 1.25,
      recordPrecipYears: "2017",
      normalYtdPrecip: 10.2,
    },
  };
  const rows = mergeClimateData(observations, climatology);
  const summary = summarizePeriod(rows);

  assert.equal(summary.dayCount, 2);
  assert.equal(summary.observedHighAverage, 99);
  assert.equal(summary.highDeparture, 8.5);
  assert.equal(summary.totalPrecip, 0.5);
  assert.equal(summary.daysAtOrAbove90, 2);
  assert.equal(summary.daysAtOrAbove100, 1);
  assert.equal(summary.first90DegreeDay, "2026-06-01");
  assert.equal(summary.first100DegreeDay, "2026-06-01");
  assert.equal(summary.highRecordsTied, 1);
  assert.equal(summary.warmLowRecordsBroken, 1);
  assert.equal(summary.warmLowRecordsTied, 1);
  assert.equal(summary.precipRecordsTied, 1);
  assert.equal(summary.precipRecordsBroken, 0);
  assert.equal(rows[0].precipRecordStatus, "tied");
  assert.equal(rows[1].precipRecordStatus, "none");
  assert.equal(summary.hazardCounts["HT.Y"], 1);
  assert.equal(summary.hazardCounts["XH.W"], 1);
});

test("selected-period counts use the period while first dates use the full season", () => {
  const seasonRows = [
    { date: "2026-06-01", high: 88 },
    { date: "2026-06-03", high: 90 },
    { date: "2026-07-01", high: 100 },
    { date: "2026-07-02", high: 95 },
  ];
  const julyRows = seasonRows.filter((row) => row.date.startsWith("2026-07"));
  const summary = summarizePeriod(julyRows, seasonRows);

  assert.equal(summary.daysAtOrAbove90, 2);
  assert.equal(summary.daysAtOrAbove100, 1);
  assert.equal(summary.first90DegreeDay, "2026-06-03");
  assert.equal(summary.first100DegreeDay, "2026-07-01");
});

test("a season without a threshold leaves its first date empty", () => {
  const summary = summarizePeriod([{ date: "2026-06-01", high: 89 }]);
  assert.equal(summary.daysAtOrAbove90, 0);
  assert.equal(summary.daysAtOrAbove100, 0);
  assert.equal(summary.first90DegreeDay, null);
  assert.equal(summary.first100DegreeDay, null);
});

test("observed rainfall above the prior record is flagged as broken", () => {
  const [row] = mergeClimateData(
    [{ date: "2026-07-04", precip: 3.25 }],
    { "07-04": { recordPrecip: 3.1, recordPrecipYears: "2001" } },
  );
  assert.equal(row.precipRecordStatus, "broken");
});

test("legacy EH codes are normalized into current XH summary buckets", () => {
  const summary = summarizePeriod([{ date: "2025-07-01", hazards: ["EH.A", "EH.W"] }]);
  assert.equal(summary.hazardCounts["XH.A"], 1);
  assert.equal(summary.hazardCounts["XH.W"], 1);
});
