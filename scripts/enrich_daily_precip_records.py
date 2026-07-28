#!/usr/bin/env python3
"""Enrich generated climatology and history files with operational records.

The reference builder already downloads the RCC ACIS operational climate series.
This enrichment step uses the same verified station threads and year-specific
baselines to add daily precipitation records, record cool highs, record lows,
and period-to-date rainfall distributions for historical ranking graphics.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import build_operational_reference_data as operational

builder = operational.builder


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def minimum_record_for_day(
    rows: list[dict[str, Any]], field: str
) -> tuple[float | int | None, str]:
    valid = [
        (item[field], item["date"].year)
        for item in rows
        if isinstance(item.get(field), (int, float))
    ]
    if not valid:
        return None, ""
    value = min(item[0] for item in valid)
    years = sorted({year for observed, year in valid if observed == value})
    return value, ", ".join(str(year) for year in years)


def next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)


def period_to_date_precip_totals(
    rows: list[dict[str, Any]], through_year: int
) -> dict[str, dict[str, list[list[float | int]]]]:
    """Return complete historical cumulative totals for each summer end date.

    Month keys compare month-to-date totals. The season key compares totals from
    June 1 through the same ending date. A historical year is included only when
    every daily precipitation value in that comparison window is available.
    """

    by_year: dict[int, dict[date, float]] = defaultdict(dict)
    for item in rows:
        day = item["date"]
        precip = item.get("precip")
        if (
            day.year <= through_year
            and day.month in builder.SUMMER_MONTHS
            and isinstance(precip, (int, float))
        ):
            by_year[day.year][day] = float(precip)

    output: dict[str, dict[str, list[list[float | int]]]] = {
        f"{month:02d}": {} for month in sorted(builder.SUMMER_MONTHS)
    }
    output["season"] = {}

    for year, daily in sorted(by_year.items()):
        for month in sorted(builder.SUMMER_MONTHS):
            cursor = date(year, month, 1)
            end = next_month(cursor)
            running = 0.0
            complete = True
            while cursor < end:
                if cursor not in daily:
                    complete = False
                if complete:
                    running += daily[cursor]
                    key = cursor.strftime("%m-%d")
                    output[f"{month:02d}"].setdefault(key, []).append(
                        [year, round(running, 2)]
                    )
                cursor += timedelta(days=1)

        cursor = date(year, 6, 1)
        end = date(year, 10, 1)
        running = 0.0
        complete = True
        while cursor < end:
            if cursor not in daily:
                complete = False
            if complete:
                running += daily[cursor]
                key = cursor.strftime("%m-%d")
                output["season"].setdefault(key, []).append(
                    [year, round(running, 2)]
                )
            cursor += timedelta(days=1)

    return output


def enrich(data_root: Path, through_year: int) -> list[Path]:
    changed: list[Path] = []

    for code, meta in builder.STATIONS.items():
        sid = meta["record_sid"]
        verified_start = operational.VERIFIED_STARTS[sid]
        print(f"Downloading daily record history for {code} ({sid})...")
        rows, _ = builder.fetch_acis_daily(
            sid,
            verified_start,
            date(through_year, 12, 31),
        )
        if not rows:
            raise RuntimeError(f"{code}: ACIS returned no record data for {sid}")

        for display_year in builder.DISPLAY_YEARS:
            baseline = [
                item
                for item in rows
                if item["date"].year < display_year
                and item["date"].month in builder.SUMMER_MONTHS
            ]
            by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in baseline:
                by_key[item["date"].strftime("%m-%d")].append(item)

            path = data_root / "climatology" / str(display_year) / f"{code}.json"
            if not path.exists():
                raise RuntimeError(f"{code} {display_year}: missing climatology file {path}")
            payload = load_json(path)
            daily = payload.get("daily", {})

            for key, climate_row in daily.items():
                daily_history = by_key.get(key, [])
                precip_record, precip_years = builder.record_for_day(daily_history, "precip")
                cool_high, cool_high_years = minimum_record_for_day(daily_history, "high")
                record_low, record_low_years = minimum_record_for_day(daily_history, "low")
                if precip_record is None or not precip_years:
                    raise RuntimeError(
                        f"{code} {display_year} {key}: no daily precipitation record found"
                    )
                if cool_high is None or not cool_high_years:
                    raise RuntimeError(
                        f"{code} {display_year} {key}: no daily cool-high record found"
                    )
                if record_low is None or not record_low_years:
                    raise RuntimeError(
                        f"{code} {display_year} {key}: no daily record low found"
                    )
                climate_row["recordPrecip"] = precip_record
                climate_row["recordPrecipYears"] = precip_years
                climate_row["recordCoolHigh"] = cool_high
                climate_row["recordCoolHighYears"] = cool_high_years
                climate_row["recordLow"] = record_low
                climate_row["recordLowYears"] = record_low_years

            records_source = payload.setdefault("source", {}).setdefault("records", {})
            includes = set(records_source.get("includes", []))
            includes.update(
                {
                    "daily record high",
                    "daily warm-low record",
                    "daily cool-high record",
                    "daily record low",
                    "daily precipitation record",
                }
            )
            records_source["includes"] = sorted(includes)
            write_json(path, payload)
            changed.append(path)

            if display_year == 2026:
                compatibility = data_root / "climatology" / f"{code}.json"
                write_json(compatibility, payload)
                changed.append(compatibility)

        history_path = data_root / "history" / f"{code}.json"
        if not history_path.exists():
            raise RuntimeError(f"{code}: missing history file {history_path}")
        history = load_json(history_path)
        history["precipPeriodTotals"] = period_to_date_precip_totals(rows, through_year)
        history.setdefault("source", {})["precipRankingThrough"] = through_year
        write_json(history_path, history)
        changed.append(history_path)

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("public/data"))
    parser.add_argument(
        "--through-year",
        type=int,
        default=builder.HISTORY_THROUGH,
        help="Latest completed year available to the record baseline.",
    )
    args = parser.parse_args()
    paths = enrich(args.data_root, args.through_year)
    print(f"Enriched {len(paths)} climatology/history files")


if __name__ == "__main__":
    main()
