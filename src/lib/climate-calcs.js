const average = (values) => {
  const valid = values.filter((value) => Number.isFinite(value));
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
};

const maxWithDates = (rows, key) => {
  const valid = rows.filter((row) => Number.isFinite(row[key]));
  if (!valid.length) return { value: null, dates: [] };
  const value = Math.max(...valid.map((row) => row[key]));
  return { value, dates: valid.filter((row) => row[key] === value).map((row) => row.date) };
};

const firstDateAtOrAbove = (rows, threshold) =>
  rows
    .filter((row) => Number.isFinite(row.high) && row.high >= threshold && row.date)
    .sort((a, b) => a.date.localeCompare(b.date))[0]?.date ?? null;

const recordDates = (rows, key, status) =>
  rows.filter((row) => row[key] === status && row.date).map((row) => row.date);

const uniqueDates = (...dateGroups) =>
  [...new Set(dateGroups.flat().filter(Boolean))].sort((a, b) => a.localeCompare(b));

const TEMPERATURE_RECORD_TYPES = [
  { key: "highRecordStatus", type: "Record high" },
  { key: "warmLowRecordStatus", type: "Warm low" },
  { key: "lowRecordStatus", type: "Record low" },
  { key: "coolHighRecordStatus", type: "Cool high" },
];

const temperatureRecordEvents = (rows, status) =>
  rows.flatMap((row) =>
    TEMPERATURE_RECORD_TYPES.filter((record) => row[record.key] === status).map((record) => ({
      date: row.date,
      type: record.type,
    })),
  );

export function getRecordStatus(observed, record) {
  if (!Number.isFinite(observed) || !Number.isFinite(record)) return "none";
  if (observed > record) return "broken";
  if (observed === record) return "tied";
  return "none";
}

export function getLowRecordStatus(observed, record) {
  if (!Number.isFinite(observed) || !Number.isFinite(record)) return "none";
  if (observed < record) return "broken";
  if (observed === record) return "tied";
  return "none";
}

export function mergeClimateData(observations, climatology) {
  return observations.map((observation) => {
    const climate = climatology[observation.date.slice(5)] ?? {};
    return {
      ...observation,
      ...climate,
      highDeparture:
        Number.isFinite(observation.high) && Number.isFinite(climate.normalHigh)
          ? observation.high - climate.normalHigh
          : null,
      lowDeparture:
        Number.isFinite(observation.low) && Number.isFinite(climate.normalLow)
          ? observation.low - climate.normalLow
          : null,
      precipDeparture:
        Number.isFinite(observation.accumulatedPrecip) && Number.isFinite(climate.normalYtdPrecip)
          ? observation.accumulatedPrecip - climate.normalYtdPrecip
          : null,
      highRecordStatus: getRecordStatus(observation.high, climate.recordHigh),
      warmLowRecordStatus: getRecordStatus(observation.low, climate.recordWarmLow),
      lowRecordStatus: getLowRecordStatus(observation.low, climate.recordLow),
      coolHighRecordStatus: getLowRecordStatus(observation.high, climate.recordCoolHigh),
      precipRecordStatus: getRecordStatus(observation.precip, climate.recordPrecip),
    };
  });
}

export function filterPeriod(rows, period) {
  if (period === "season") return rows;
  return rows.filter((row) => row.date.slice(5, 7) === period);
}

export function summarizePeriod(rows, seasonRows = rows) {
  const hazardCounts = { "HT.Y": 0, "XH.A": 0, "XH.W": 0 };
  rows.forEach((row) => {
    (row.hazards ?? []).forEach((rawHazard) => {
      const hazard = rawHazard === "EH.A" ? "XH.A" : rawHazard === "EH.W" ? "XH.W" : rawHazard;
      hazardCounts[hazard] = (hazardCounts[hazard] ?? 0) + 1;
    });
  });

  const hottest = maxWithDates(rows, "high");
  const warmestLow = maxWithDates(rows, "low");
  const maxHeatIndex = maxWithDates(rows, "maxHeatIndex");
  const observedHighAverage = average(rows.map((row) => row.high));
  const normalHighAverage = average(rows.map((row) => row.normalHigh));
  const observedLowAverage = average(rows.map((row) => row.low));
  const normalLowAverage = average(rows.map((row) => row.normalLow));
  const totalPrecip = rows.reduce(
    (sum, row) => sum + (Number.isFinite(row.precip) ? row.precip : 0),
    0,
  );

  const highRecordBrokenDates = recordDates(rows, "highRecordStatus", "broken");
  const highRecordTiedDates = recordDates(rows, "highRecordStatus", "tied");
  const warmLowRecordBrokenDates = recordDates(rows, "warmLowRecordStatus", "broken");
  const warmLowRecordTiedDates = recordDates(rows, "warmLowRecordStatus", "tied");
  const lowRecordBrokenDates = recordDates(rows, "lowRecordStatus", "broken");
  const lowRecordTiedDates = recordDates(rows, "lowRecordStatus", "tied");
  const coolHighRecordBrokenDates = recordDates(rows, "coolHighRecordStatus", "broken");
  const coolHighRecordTiedDates = recordDates(rows, "coolHighRecordStatus", "tied");
  const precipRecordBrokenDates = recordDates(rows, "precipRecordStatus", "broken");
  const precipRecordTiedDates = recordDates(rows, "precipRecordStatus", "tied");
  const temperatureRecordBrokenEvents = temperatureRecordEvents(rows, "broken");
  const temperatureRecordTiedEvents = temperatureRecordEvents(rows, "tied");
  const temperatureRecordBrokenDates = uniqueDates(
    highRecordBrokenDates,
    warmLowRecordBrokenDates,
    lowRecordBrokenDates,
    coolHighRecordBrokenDates,
  );
  const temperatureRecordTiedDates = uniqueDates(
    highRecordTiedDates,
    warmLowRecordTiedDates,
    lowRecordTiedDates,
    coolHighRecordTiedDates,
  );

  return {
    dayCount: rows.length,
    hazardCounts,
    daysAtOrAbove90: rows.filter((row) => row.high >= 90).length,
    daysAtOrAbove99: rows.filter((row) => row.high >= 99).length,
    daysAtOrAbove100: rows.filter((row) => row.high >= 100).length,
    first90DegreeDay: firstDateAtOrAbove(seasonRows, 90),
    first100DegreeDay: firstDateAtOrAbove(seasonRows, 100),
    daysAboveNormal: rows.filter((row) => row.highDeparture > 0).length,
    nightsAtOrAbove80: rows.filter((row) => row.low >= 80).length,
    nightsAboveNormal: rows.filter((row) => row.lowDeparture > 0).length,
    hottest,
    warmestLow,
    maxHeatIndex,
    averageHeatIndex: average(rows.map((row) => row.maxHeatIndex)),
    observedHighAverage,
    normalHighAverage,
    highDeparture:
      Number.isFinite(observedHighAverage) && Number.isFinite(normalHighAverage)
        ? observedHighAverage - normalHighAverage
        : null,
    observedLowAverage,
    normalLowAverage,
    lowDeparture:
      Number.isFinite(observedLowAverage) && Number.isFinite(normalLowAverage)
        ? observedLowAverage - normalLowAverage
        : null,
    totalPrecip,
    highRecordsBroken: highRecordBrokenDates.length,
    highRecordsTied: highRecordTiedDates.length,
    highRecordBrokenDates,
    highRecordTiedDates,
    warmLowRecordsBroken: warmLowRecordBrokenDates.length,
    warmLowRecordsTied: warmLowRecordTiedDates.length,
    warmLowRecordBrokenDates,
    warmLowRecordTiedDates,
    lowRecordsBroken: lowRecordBrokenDates.length,
    lowRecordsTied: lowRecordTiedDates.length,
    lowRecordBrokenDates,
    lowRecordTiedDates,
    coolHighRecordsBroken: coolHighRecordBrokenDates.length,
    coolHighRecordsTied: coolHighRecordTiedDates.length,
    coolHighRecordBrokenDates,
    coolHighRecordTiedDates,
    temperatureRecordsBroken: temperatureRecordBrokenEvents.length,
    temperatureRecordsTied: temperatureRecordTiedEvents.length,
    temperatureRecordBrokenDates,
    temperatureRecordTiedDates,
    temperatureRecordBrokenEvents,
    temperatureRecordTiedEvents,
    precipRecordsBroken: precipRecordBrokenDates.length,
    precipRecordsTied: precipRecordTiedDates.length,
    precipRecordBrokenDates,
    precipRecordTiedDates,
    endingAccumulatedPrecip: rows.at(-1)?.accumulatedPrecip ?? null,
    endingPrecipDeparture: rows.at(-1)?.precipDeparture ?? null,
  };
}
