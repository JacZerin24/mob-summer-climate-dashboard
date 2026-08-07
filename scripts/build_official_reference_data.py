#!/usr/bin/env python3
"""Build normals, operational climate records, and historical reference tables.

Sources
-------
* NOAA/NCEI 1991-2020 U.S. Climate Normals daily station CSV files.
* RCC ACIS daily station service using ThreadEx climate series where available.

The ACIS ThreadEx series preserve the operational climate thread across station
moves. This is essential for Mobile and Pensacola, where a single current-airport
GHCN station does not cover the full official climate record.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "mob-summer-climate-dashboard/2.1 (climate data audit)"
NCEI_ACCESS = "https://www.ncei.noaa.gov/access/services/data/v1"
NORMALS_BASE = "https://www.ncei.noaa.gov/data/normals-daily/1991-2020/access"
ACIS_STN_DATA = "https://data.rcc-acis.org/StnData"
SUMMER_MONTHS = {6, 7, 8, 9}
DISPLAY_YEARS = (2025, 2026)
HISTORY_THROUGH = 2025
EARLIEST_YEAR = 1890

STATIONS: dict[str, dict[str, Any]] = {
    "KMOB": {
        "name": "Mobile, AL",
        "ghcn": "USW00013894",
        "record_sid": "MOBthr",
        "record_kind": "thread",
        "lat": 30.6882,
        "lon": -88.2460,
    },
    "KPNS": {
        "name": "Pensacola, FL",
        "ghcn": "USW00013899",
        "record_sid": "PNSthr",
        "record_kind": "thread",
        "lat": 30.4761,
        "lon": -87.1858,
    },
    "KGZH": {
        "name": "Evergreen, AL",
        "ghcn": "USW00053820",
        "record_sid": "USW00053820",
        "record_kind": "ghcn",
        "lat": 31.4158,
        "lon": -87.0441,
    },
    "KCEW": {
        "name": "Crestview, FL",
        "ghcn": "USW00013884",
        "record_sid": "USW00013884",
        "record_kind": "ghcn",
        "lat": 30.77715,
        "lon": -86.51938,
    },
    "KDTS": {
        "name": "Destin, FL",
        "ghcn": "USW00053853",
        "record_sid": "USW00053853",
        "record_kind": "ghcn",
        "lat": 30.39333,
        "lon": -86.46738,
    },
}


def request_text(url: str, attempts: int = 4) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/csv,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8-sig")
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def post_json(url: str, payload: dict[str, Any], attempts: int = 4) -> Any:
    last_error: Exception | None = None
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                data=data,
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def parse_number(value: Any) -> float | int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {
        "M",
        "NA",
        "N/A",
        "NULL",
        "NONE",
        "-9999",
        "-7777",
    }:
        return None
    if text.upper() == "T":
        return 0
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= -900:
        return None
    return int(number) if number.is_integer() else round(number, 2)


def date_key(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-":
        return text[5:10]
    if len(text) == 5 and text[2] == "-":
        return text
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) >= 4:
        return f"{digits[-4:-2]}-{digits[-2:]}"
    return None


def fetch_normals(ghcn: str) -> tuple[dict[str, dict[str, Any]], str]:
    url = f"{NORMALS_BASE}/{ghcn}.csv"
    rows = csv.DictReader(io.StringIO(request_text(url)))
    daily: dict[str, dict[str, Any]] = {}
    cumulative = 0.0
    for row in rows:
        key = date_key(row.get("DATE", ""))
        if not key:
            continue
        daily_precip = parse_number(row.get("DLY-PRCP-NORMAL"))
        if isinstance(daily_precip, (int, float)):
            cumulative += float(daily_precip)
        ytd = parse_number(row.get("YTD-PRCP-NORMAL"))
        if ytd is None:
            ytd = round(cumulative, 2)
        if int(key[:2]) not in SUMMER_MONTHS:
            continue
        daily[key] = {
            "normalHigh": parse_number(row.get("DLY-TMAX-NORMAL")),
            "normalLow": parse_number(row.get("DLY-TMIN-NORMAL")),
            "normalYtdPrecip": ytd,
        }
    return daily, url


def fetch_acis_daily(
    sid: str,
    start: date,
    end: date,
    chunk_years: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    source_meta: dict[str, Any] = {}
    cursor = start
    while cursor <= end:
        chunk_end = min(end, date(cursor.year + chunk_years - 1, 12, 31))
        payload = post_json(
            ACIS_STN_DATA,
            {
                "sid": sid,
                "sdate": cursor.isoformat(),
                "edate": chunk_end.isoformat(),
                "elems": [
                    {"name": "maxt", "interval": "dly", "duration": 1},
                    {"name": "mint", "interval": "dly", "duration": 1},
                    {"name": "pcpn", "interval": "dly", "duration": 1},
                ],
                "meta": ["name", "state", "sids", "valid_daterange", "ll"],
            },
        )
        if payload.get("error"):
            raise RuntimeError(f"ACIS {sid}: {payload['error']}")
        if not source_meta:
            source_meta = payload.get("meta", {})
        for row in payload.get("data", []):
            if not row:
                continue
            try:
                day = date.fromisoformat(str(row[0])[:10])
            except ValueError:
                continue
            output.append(
                {
                    "date": day,
                    "high": parse_number(row[1] if len(row) > 1 else None),
                    "low": parse_number(row[2] if len(row) > 2 else None),
                    "precip": parse_number(row[3] if len(row) > 3 else None),
                }
            )
        cursor = chunk_end + timedelta(days=1)
    deduped = {item["date"]: item for item in output}
    return [deduped[key] for key in sorted(deduped)], source_meta


def record_for_day(
    rows: Iterable[dict[str, Any]], field: str
) -> tuple[float | int | None, str]:
    valid = [
        (item[field], item["date"].year)
        for item in rows
        if isinstance(item.get(field), (int, float))
    ]
    if not valid:
        return None, ""
    value = max(item[0] for item in valid)
    years = sorted({year for observed, year in valid if observed == value})
    return value, ", ".join(str(year) for year in years)


def expected_days(year: int, month: int | None = None) -> int:
    if month is None:
        return sum(expected_days(year, item) for item in sorted(SUMMER_MONTHS))
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return (end - start).days


def longest_streaks(
    rows: list[dict[str, Any]], threshold: int
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    start: date | None = None
    previous: date | None = None
    count = 0

    def date_label(value: date) -> str:
        return f"{value:%b} {value.day}"

    def finish() -> None:
        nonlocal start, previous, count
        if start is not None and previous is not None and count:
            output.append(
                {
                    "days": count,
                    "year": start.year,
                    "dates": f"{date_label(start)}–{date_label(previous)}, {previous.year}",
                }
            )
        start = previous = None
        count = 0

    for item in sorted(rows, key=lambda value: value["date"]):
        day = item["date"]
        high = item.get("high")
        qualifying = isinstance(high, (int, float)) and high >= threshold
        consecutive = previous is not None and day == previous + timedelta(days=1)
        same_year = start is None or day.year == start.year
        if qualifying:
            if start is None or not consecutive or not same_year:
                finish()
                start = day
                count = 1
            else:
                count += 1
            previous = day
        else:
            finish()
    finish()
    return sorted(
        output,
        key=lambda item: (-item["days"], item["year"], item["dates"]),
    )[:10]


def yearly_hot_counts(
    rows: list[dict[str, Any]], threshold: int
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        grouped[item["date"].year].append(item)
    result = []
    for year, items in grouped.items():
        valid_days = {
            item["date"]
            for item in items
            if isinstance(item.get("high"), (int, float))
        }
        if len(valid_days) < expected_days(year) - 1:
            continue
        result.append(
            {
                "count": sum(
                    1
                    for item in items
                    if isinstance(item.get("high"), (int, float))
                    and item["high"] >= threshold
                ),
                "year": year,
            }
        )
    return sorted(result, key=lambda item: (-item["count"], item["year"]))[:10]


def monthly_precip_records(
    rows: list[dict[str, Any]], through_year: int
) -> dict[str, Any]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        day = item["date"]
        if day.year <= through_year and day.month in SUMMER_MONTHS:
            grouped[(day.year, day.month)].append(item)
    output: dict[str, Any] = {}
    for month in sorted(SUMMER_MONTHS):
        totals = []
        for (year, item_month), items in grouped.items():
            if item_month != month:
                continue
            valid = [
                item
                for item in items
                if isinstance(item.get("precip"), (int, float))
            ]
            if len({item["date"] for item in valid}) != expected_days(year, month):
                continue
            totals.append(
                {
                    "amount": round(
                        sum(float(item["precip"]) for item in valid), 2
                    ),
                    "date": str(year),
                }
            )
        output[f"{month:02d}"] = {
            "highest": sorted(
                totals, key=lambda item: (-item["amount"], item["date"])
            )[:5],
            "lowest": sorted(
                totals, key=lambda item: (item["amount"], item["date"])
            )[:5],
        }
    return output


def record_year_counts(
    rows: list[dict[str, Any]], through_year: int
) -> list[dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        if (
            item["date"].year <= through_year
            and item["date"].month in SUMMER_MONTHS
        ):
            by_key[item["date"].strftime("%m-%d")].append(item)
    counts: Counter[int] = Counter()
    for items in by_key.values():
        value, years_text = record_for_day(items, "high")
        if value is None:
            continue
        for year in years_text.split(", "):
            if year:
                counts[int(year)] += 1
    return [
        {"count": count, "year": year}
        for year, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )[:10]
    ]


def source_period(
    rows: list[dict[str, Any]], through_year: int | None = None
) -> dict[str, str | None]:
    observed_dates = [
        item["date"]
        for item in rows
        if (through_year is None or item["date"].year <= through_year)
        and any(
            isinstance(item.get(key), (int, float))
            for key in ("high", "low", "precip")
        )
    ]
    return {
        "start": min(observed_dates).isoformat() if observed_dates else None,
        "end": max(observed_dates).isoformat() if observed_dates else None,
    }


def acis_source(
    meta: dict[str, Any],
    acis_meta: dict[str, Any],
    through_year: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    is_thread = meta.get("record_kind", "thread") == "thread"
    return {
        "agency": "NOAA Regional Climate Center Program / RCC ACIS",
        "dataset": "ACIS ThreadEx daily climate series" if is_thread else "ACIS GHCN-Daily station series",
        "stationId": meta["record_sid"],
        "stationName": acis_meta.get("name"),
        "sourceIds": acis_meta.get("sids", []),
        "throughYear": through_year,
        "periodOfRecord": source_period(rows, through_year),
        "basis": "Operational threaded climate series used for station records" if is_thread else "Station-specific GHCN-Daily climate series used for station records",
        "url": ACIS_STN_DATA,
    }


def history_payload(
    code: str,
    meta: dict[str, Any],
    acis_meta: dict[str, Any],
    rows: list[dict[str, Any]],
    generated: str,
) -> dict[str, Any]:
    summer = [
        item
        for item in rows
        if item["date"].month in SUMMER_MONTHS
        and item["date"].year <= HISTORY_THROUGH
    ]
    streak_99 = longest_streaks(summer, 99)
    streak_100 = longest_streaks(summer, 100)
    yearly_99 = yearly_hot_counts(summer, 99)
    yearly_100 = yearly_hot_counts(summer, 100)
    record_years = record_year_counts(summer, HISTORY_THROUGH)

    def rows_of(
        items: list[dict[str, Any]], fields: tuple[str, ...]
    ) -> list[list[Any]]:
        return [[item[field] for field in fields] for item in items]

    source = acis_source(meta, acis_meta, HISTORY_THROUGH, rows)
    source["recordThrough"] = source.pop("throughYear")
    return {
        "station": code,
        "generatedAt": generated,
        "source": source,
        "referenceTables": [
            {
                "title": "Longest consecutive days at or above 99°F",
                "updated": f"Through {HISTORY_THROUGH}",
                "headers": ["Days", "Year", "Dates"],
                "rows": rows_of(streak_99, ("days", "year", "dates")),
            },
            {
                "title": "Longest consecutive days at or above 100°F",
                "updated": f"Through {HISTORY_THROUGH}",
                "headers": ["Days", "Year", "Dates"],
                "rows": rows_of(streak_100, ("days", "year", "dates")),
            },
            {
                "title": "Yearly greatest number of days at or above 99°F",
                "updated": f"Through {HISTORY_THROUGH}",
                "headers": ["Total #", "Year"],
                "rows": rows_of(yearly_99, ("count", "year")),
            },
            {
                "title": "Yearly greatest number of days at or above 100°F",
                "updated": f"Through {HISTORY_THROUGH}",
                "headers": ["Total #", "Year"],
                "rows": rows_of(yearly_100, ("count", "year")),
            },
            {
                "title": "Years holding the most June–September daily record highs",
                "updated": f"Records through {HISTORY_THROUGH}",
                "headers": ["Total #", "Year"],
                "rows": rows_of(record_years, ("count", "year")),
            },
        ],
        "monthlyPrecipRecords": monthly_precip_records(
            summer, HISTORY_THROUGH
        ),
    }


def climate_payload(
    code: str,
    meta: dict[str, Any],
    acis_meta: dict[str, Any],
    normals: dict[str, dict[str, Any]],
    normals_url: str,
    rows: list[dict[str, Any]],
    target_year: int,
    generated: str,
) -> dict[str, Any]:
    baseline = [
        item
        for item in rows
        if item["date"].year < target_year
        and item["date"].month in SUMMER_MONTHS
    ]
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in baseline:
        by_key[item["date"].strftime("%m-%d")].append(item)
    daily: dict[str, dict[str, Any]] = {}
    for key in sorted(normals):
        high, high_years = record_for_day(by_key.get(key, []), "high")
        warm_low, warm_low_years = record_for_day(by_key.get(key, []), "low")
        daily[key] = {
            **normals[key],
            "recordHigh": high,
            "recordHighYears": high_years,
            "recordWarmLow": warm_low,
            "recordWarmLowYears": warm_low_years,
        }
    return {
        "station": code,
        "displayYear": target_year,
        "generatedAt": generated,
        "source": {
            "normals": {
                "agency": "NOAA National Centers for Environmental Information",
                "dataset": "U.S. Climate Normals 1991-2020, Daily",
                "stationId": meta["ghcn"],
                "url": normals_url,
            },
            "records": acis_source(
                meta, acis_meta, target_year - 1, rows
            ),
        },
        "daily": daily,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build(
    output: Path,
    start_year: int = EARLIEST_YEAR,
    through_year: int = HISTORY_THROUGH,
) -> list[Path]:
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed: list[Path] = []
    for code, meta in STATIONS.items():
        print(
            f"Downloading NCEI normals and ACIS climate series for {code} "
            f"({meta['record_sid']})..."
        )
        normals, normals_url = fetch_normals(meta["ghcn"])
        rows, acis_meta = fetch_acis_daily(
            meta["record_sid"],
            date(start_year, 1, 1),
            date(through_year, 12, 31),
        )
        if len(normals) != 122:
            raise RuntimeError(
                f"{code}: expected 122 summer normal rows, found {len(normals)}"
            )
        if not rows:
            raise RuntimeError(
                f"{code}: ACIS returned no daily data for {meta['record_sid']}"
            )
        for year in DISPLAY_YEARS:
            path = output / "climatology" / str(year) / f"{code}.json"
            payload = climate_payload(
                code,
                meta,
                acis_meta,
                normals,
                normals_url,
                rows,
                year,
                generated,
            )
            write_json(path, payload)
            changed.append(path)
        compatibility = output / "climatology" / f"{code}.json"
        write_json(
            compatibility,
            climate_payload(
                code,
                meta,
                acis_meta,
                normals,
                normals_url,
                rows,
                2026,
                generated,
            ),
        )
        changed.append(compatibility)
        history = output / "history" / f"{code}.json"
        write_json(
            history,
            history_payload(code, meta, acis_meta, rows, generated),
        )
        changed.append(history)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--start-year", type=int, default=EARLIEST_YEAR)
    parser.add_argument("--through-year", type=int, default=HISTORY_THROUGH)
    args = parser.parse_args()
    paths = build(args.output, args.start_year, args.through_year)
    print(f"Wrote {len(paths)} official reference files")


if __name__ == "__main__":
    main()
