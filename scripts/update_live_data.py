#!/usr/bin/env python3
"""Refresh a MOB summer season from official and documented public sources.

Daily high, low, and precipitation preferentially come from NOAA/NCEI Daily
Summaries. IEM daily summaries supply the derived maximum heat index and are
used only as an explicitly identified provisional fallback when NCEI has not
yet posted a completed day.

Heat products are assembled from the official NWS API for the most recent
seven days and the IEM archive of NWS-issued VTEC products for the full season.
Current VTEC terminology/codes are Heat Advisory (HT.Y), Extreme Heat Watch
(XH.A), and Extreme Heat Warning (XH.W).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from build_official_reference_data import (
    NCEI_ACCESS,
    STATIONS as REFERENCE_STATIONS,
    SUMMER_MONTHS,
    parse_number,
    request_text,
)

CENTRAL = ZoneInfo("America/Chicago")
USER_AGENT = "mob-summer-climate-dashboard/2.0 (WFO MOB climate dashboard)"
IEM_DAILY_ENDPOINT = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
IEM_VTEC_ENDPOINT = "https://mesonet.agron.iastate.edu/json/vtec_events_bypoint.py"
NWS_ALERTS_ENDPOINT = "https://api.weather.gov/alerts"

STATIONS = {
    "KMOB": {**REFERENCE_STATIONS["KMOB"], "iem": "MOB", "network": "AL_ASOS"},
    "KPNS": {**REFERENCE_STATIONS["KPNS"], "iem": "PNS", "network": "FL_ASOS"},
}

EVENT_CODES = {
    "Heat Advisory": "HT.Y",
    "Extreme Heat Watch": "XH.A",
    "Extreme Heat Warning": "XH.W",
    # Preserve compatibility with products issued before the national rename.
    "Excessive Heat Watch": "XH.A",
    "Excessive Heat Warning": "XH.W",
}


def request_json(url: str, accept: str = "application/json") -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_hazard(code: str) -> str | None:
    text = str(code or "").strip().upper()
    aliases = {
        "HT.Y": "HT.Y",
        "XH.A": "XH.A",
        "XH.W": "XH.W",
        "EH.A": "XH.A",
        "EH.W": "XH.W",
    }
    return aliases.get(text)


def fetch_iem_daily(network: str, station_ids: list[str], year: int, end_date: date) -> list[dict[str, str]]:
    params = {
        "sts": f"{year}-01-01",
        "ets": end_date.isoformat(),
        "network": network,
        "stations": ",".join(station_ids),
        "var": "max_temp_f,min_temp_f,precip_in,max_feel",
        "format": "csv",
        "na": "",
    }
    url = f"{IEM_DAILY_ENDPOINT}?{urllib.parse.urlencode(params)}"
    return list(csv.DictReader(io.StringIO(request_text(url))))


def fetch_ncei_current(ghcn: str, year: int, end_date: date) -> dict[str, dict[str, Any]]:
    params = {
        "dataset": "daily-summaries",
        "stations": ghcn,
        "startDate": f"{year}-01-01",
        "endDate": end_date.isoformat(),
        "format": "json",
        "units": "standard",
        "includeAttributes": "true",
        "includeStationName": "true",
        "dataTypes": "TMAX,TMIN,PRCP",
    }
    payload = json.loads(request_text(f"{NCEI_ACCESS}?{urllib.parse.urlencode(params)}"))
    if isinstance(payload, dict):
        payload = payload.get("results") or payload.get("data") or []
    output: dict[str, dict[str, Any]] = {}
    for row in payload:
        day_text = str(row.get("DATE") or row.get("date") or "")[:10]
        try:
            date.fromisoformat(day_text)
        except ValueError:
            continue
        precip_text = str(row.get("PRCP") or "").strip().upper()
        output[day_text] = {
            "high": parse_number(row.get("TMAX")),
            "low": parse_number(row.get("TMIN")),
            "precip": 0 if precip_text == "T" else parse_number(row.get("PRCP")),
            "precipTrace": precip_text == "T",
        }
    return output


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def add_hazard_days(hazards: dict[str, set[str]], begins: datetime, ends: datetime, code: str) -> None:
    if ends < begins:
        ends = begins
    # A product expiring exactly at midnight should not count the new calendar day.
    adjusted_end = ends - timedelta(microseconds=1) if ends > begins else ends
    current = begins.astimezone(CENTRAL).date()
    final = adjusted_end.astimezone(CENTRAL).date()
    while current <= final:
        hazards.setdefault(current.isoformat(), set()).add(code)
        current += timedelta(days=1)


def fetch_nws_recent_hazards(meta: dict[str, Any], today: date) -> dict[str, set[str]]:
    start = today - timedelta(days=7)
    params = {
        "point": f"{meta['lat']},{meta['lon']}",
        "start": datetime.combine(start, time.min, CENTRAL).astimezone(timezone.utc).isoformat(),
        "end": datetime.combine(today + timedelta(days=1), time.min, CENTRAL).astimezone(timezone.utc).isoformat(),
        "status": "actual",
    }
    payload = request_json(f"{NWS_ALERTS_ENDPOINT}?{urllib.parse.urlencode(params)}", "application/geo+json")
    hazards: dict[str, set[str]] = {}
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        code = EVENT_CODES.get(properties.get("event"))
        if not code:
            continue
        begins = parse_iso(properties.get("onset") or properties.get("effective") or properties.get("sent"))
        ends = parse_iso(properties.get("ends") or properties.get("expires"))
        if begins:
            add_hazard_days(hazards, begins, ends or begins, code)
    return hazards


def fetch_iem_archived_hazards(meta: dict[str, Any], start: date, end: date) -> dict[str, set[str]]:
    params = {
        "lat": meta["lat"],
        "lon": meta["lon"],
        "sdate": start.isoformat(),
        "edate": (end + timedelta(days=1)).isoformat(),
    }
    payload = request_json(f"{IEM_VTEC_ENDPOINT}?{urllib.parse.urlencode(params)}")
    hazards: dict[str, set[str]] = {}
    for event in payload.get("events", []):
        phenomena = str(event.get("phenomena") or "").upper()
        significance = str(event.get("significance") or "").upper()
        if phenomena == "HT" and significance == "Y":
            code = "HT.Y"
        elif phenomena in {"XH", "EH"} and significance in {"A", "W"}:
            code = f"XH.{significance}"
        else:
            continue
        begins = parse_iso(event.get("issue"))
        ends = parse_iso(event.get("expire"))
        if begins:
            add_hazard_days(hazards, begins, ends or begins, code)
    return hazards


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def apply_override(observation: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "high",
        "low",
        "maxHeatIndex",
        "precip",
        "precipTrace",
        "accumulatedPrecip",
        "hazards",
        "dailySource",
    }
    for key, value in override.items():
        if key in allowed:
            observation[key] = value
    if "hazards" in observation:
        observation["hazards"] = sorted(
            {normalized for item in observation["hazards"] if (normalized := normalize_hazard(item))}
        )
    return observation


def choose_value(official: dict[str, Any] | None, provisional: dict[str, Any] | None, key: str) -> tuple[Any, str]:
    if official and official.get(key) is not None:
        return official[key], "NOAA/NCEI Daily Summaries"
    if provisional and provisional.get(key) is not None:
        return provisional[key], "IEM provisional fallback"
    return None, "missing"


def update(year: int, output: Path, through: date | None = None) -> list[Path]:
    today = datetime.now(CENTRAL).date()
    season_end = date(year, 9, 30)
    default_through = min(today - timedelta(days=1), season_end)
    end_date = through or default_through
    if end_date < date(year, 1, 1):
        raise ValueError(f"No completed {year} days are available yet")

    by_iem = {meta["iem"]: code for code, meta in STATIONS.items()}
    iem_rows: dict[str, dict[str, dict[str, Any]]] = {code: {} for code in STATIONS}
    for network in sorted({meta["network"] for meta in STATIONS.values()}):
        ids = [meta["iem"] for meta in STATIONS.values() if meta["network"] == network]
        for row in fetch_iem_daily(network, ids, year, end_date):
            code = by_iem.get((row.get("station") or "").strip())
            day_text = (row.get("day") or "").strip()
            if not code or not day_text:
                continue
            precip_raw = parse_number(row.get("precip_in"))
            trace = precip_raw == 0.0001
            iem_rows[code][day_text] = {
                "high": parse_number(row.get("max_temp_f")),
                "low": parse_number(row.get("min_temp_f")),
                "precip": 0 if trace else precip_raw,
                "precipTrace": trace,
                "maxHeatIndex": parse_number(row.get("max_feel")),
            }

    overrides_path = output / "overrides" / f"{year}.json"
    overrides = load_json(overrides_path, {"stations": {}}).get("stations", {})
    changed: list[Path] = []

    for code, meta in STATIONS.items():
        target = output / "seasons" / str(year) / f"{code}.json"
        existing = load_json(target, {"observations": []})
        existing_hazards = {
            item["date"]: {normalized for hazard in item.get("hazards", []) if (normalized := normalize_hazard(hazard))}
            for item in existing.get("observations", [])
            if item.get("date")
        }
        official = fetch_ncei_current(meta["ghcn"], year, end_date)
        try:
            archive_hazards = fetch_iem_archived_hazards(meta, date(year, 6, 1), min(end_date, season_end))
        except Exception as exc:
            print(f"Warning: IEM VTEC archive unavailable for {code}: {exc}")
            archive_hazards = {}
        try:
            recent_hazards = fetch_nws_recent_hazards(meta, today)
        except Exception as exc:
            print(f"Warning: NWS recent alerts unavailable for {code}: {exc}")
            recent_hazards = {}

        ytd_precip = 0.0
        observations: list[dict[str, Any]] = []
        source_counts = {"NOAA/NCEI Daily Summaries": 0, "IEM provisional fallback": 0, "mixed": 0, "missing": 0}
        cursor = date(year, 1, 1)
        while cursor <= end_date:
            day_text = cursor.isoformat()
            ncei = official.get(day_text)
            iem = iem_rows[code].get(day_text)
            high, high_source = choose_value(ncei, iem, "high")
            low, low_source = choose_value(ncei, iem, "low")
            precip, precip_source = choose_value(ncei, iem, "precip")
            trace = bool((ncei or {}).get("precipTrace"))
            if precip == 0 and iem and iem.get("precipTrace"):
                trace = True
            if isinstance(precip, (int, float)):
                ytd_precip += float(precip)

            if cursor.month in SUMMER_MONTHS:
                sources = {high_source, low_source, precip_source} - {"missing"}
                daily_source = sources.pop() if len(sources) == 1 else "mixed" if sources else "missing"
                source_counts[daily_source] = source_counts.get(daily_source, 0) + 1
                hazards = (
                    existing_hazards.get(day_text, set())
                    | archive_hazards.get(day_text, set())
                    | recent_hazards.get(day_text, set())
                )
                observation = {
                    "date": day_text,
                    "hazards": sorted(hazards),
                    "high": high,
                    "low": low,
                    "maxHeatIndex": (iem or {}).get("maxHeatIndex"),
                    "precip": precip,
                    "precipTrace": trace,
                    "accumulatedPrecip": round(ytd_precip, 2),
                    "dailySource": daily_source,
                }
                station_override = overrides.get(code, {}).get(day_text, {})
                observations.append(apply_override(observation, station_override))
            cursor += timedelta(days=1)

        sources = {
            "dailyObservations": "NOAA/NCEI Daily Summaries; IEM provisional fallback only where NCEI is not yet available",
            "maximumHeatIndex": "IEM derived maximum feels-like temperature",
            "heatHazards": "Official NWS recent alerts plus IEM archive of NWS-issued VTEC products",
            "stationId": meta["ghcn"],
        }
        data_through = observations[-1]["date"] if observations else None
        payload = {
            "station": code,
            "year": year,
            "provisional": year >= today.year,
            "dataThrough": data_through,
            "lastUpdated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "sources": sources,
            "sourceCounts": source_counts,
            "observations": observations,
        }
        comparable_existing = {key: value for key, value in existing.items() if key != "lastUpdated"}
        comparable_payload = {key: value for key, value in payload.items() if key != "lastUpdated"}
        if comparable_existing == comparable_payload:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        changed.append(target)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=int(os.getenv("CLIMATE_YEAR", "2026")))
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--through", type=date.fromisoformat, help="Override final date (YYYY-MM-DD)")
    args = parser.parse_args()
    changed = update(args.year, args.output, args.through)
    if changed:
        print("Updated:")
        for path in changed:
            print(f"  {path}")
    else:
        print("No live-data changes detected")


if __name__ == "__main__":
    main()
