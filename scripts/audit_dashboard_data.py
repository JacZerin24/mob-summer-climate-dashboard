#!/usr/bin/env python3
"""Audit generated dashboard data for provenance and internal accuracy."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from build_official_reference_data import STATIONS, SUMMER_MONTHS

ALLOWED_HAZARDS = {"HT.Y", "XH.A", "XH.W"}
DISPLAY_YEARS = (2025, 2026)
EXPECTED_RECORD_STARTS = {
    "KMOB": date(1872, 1, 1),
    "KPNS": date(1879, 11, 1),
    "KGZH": date(1997, 6, 1),
    "KCEW": date(1948, 1, 1),
    "KDTS": date(1996, 12, 2),
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summer_day_count(year: int) -> int:
    total = 0
    for month in sorted(SUMMER_MONTHS):
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        total += (end - start).days
    return total


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_years(value: Any) -> list[int]:
    return [int(item) for item in re.findall(r"\b\d{4}\b", str(value or ""))]


def valid_record_source(
    station: str, source: dict[str, Any], context: str, errors: list[str]
) -> None:
    source_text = json.dumps(source).lower()
    expected_sid = STATIONS[station]["record_sid"]
    record_kind = STATIONS[station].get("record_kind", "thread")
    if "rcc acis" not in source_text:
        errors.append(f"{station} {context}: records are not attributed to RCC ACIS")
    if record_kind == "thread" and "thread" not in source_text:
        errors.append(f"{station} {context}: expected a ThreadEx operational climate series")
    if record_kind == "ghcn" and "ghcn" not in source_text:
        errors.append(f"{station} {context}: expected a station-specific GHCN-Daily climate series")
    if source.get("stationId") != expected_sid:
        errors.append(
            f"{station} {context}: expected record station {expected_sid}, found {source.get('stationId')}"
        )
    period = source.get("periodOfRecord", {})
    start_text = period.get("start")
    try:
        start = date.fromisoformat(start_text) if start_text else None
    except ValueError:
        start = None
    if start is None or start > EXPECTED_RECORD_STARTS[station]:
        errors.append(
            f"{station} {context}: record period starts at {start_text}, later than expected {EXPECTED_RECORD_STARTS[station]}"
        )


def audit(data_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    station_results: dict[str, Any] = {}
    total_2026_hazard_days = 0

    for station in STATIONS:
        result: dict[str, Any] = {"climatology": {}, "seasons": {}, "history": {}}
        for year in DISPLAY_YEARS:
            climate_path = data_root / "climatology" / str(year) / f"{station}.json"
            if not climate_path.exists():
                errors.append(f"{station} {year}: missing official climatology file")
                continue
            climate = load(climate_path)
            source = climate.get("source", {})
            source_text = json.dumps(source).lower()
            if "workbook" in source_text or "spreadsheet" in source_text:
                errors.append(
                    f"{station} {year}: climatology still references workbook/spreadsheet"
                )
            normals_source = source.get("normals", {})
            if "national centers for environmental information" not in json.dumps(
                normals_source
            ).lower():
                errors.append(
                    f"{station} {year}: normals are not attributed to NOAA/NCEI"
                )
            valid_record_source(
                station, source.get("records", {}), f"{year} climatology", errors
            )
            daily = climate.get("daily", {})
            if len(daily) != summer_day_count(year):
                errors.append(
                    f"{station} {year}: expected 122 daily climatology rows, found {len(daily)}"
                )
            previous_ytd: float | None = None
            incomplete = 0
            for key, row in sorted(daily.items()):
                required = (
                    "normalHigh",
                    "normalLow",
                    "normalYtdPrecip",
                    "recordHigh",
                    "recordWarmLow",
                )
                if any(not numeric(row.get(field)) for field in required):
                    incomplete += 1
                ytd = row.get("normalYtdPrecip")
                if numeric(ytd):
                    if previous_ytd is not None and float(ytd) + 0.011 < previous_ytd:
                        errors.append(
                            f"{station} {year} {key}: normal YTD precipitation decreased"
                        )
                    previous_ytd = float(ytd)
                for field in ("recordHighYears", "recordWarmLowYears"):
                    if any(item >= year for item in parse_years(row.get(field))):
                        errors.append(
                            f"{station} {year} {key}: {field} includes a year not preceding display year"
                        )
            if incomplete:
                errors.append(
                    f"{station} {year}: {incomplete} climatology rows have missing normal/record values"
                )
            result["climatology"][str(year)] = {
                "rows": len(daily),
                "source": source,
                "complete": incomplete == 0,
            }

            season_path = data_root / "seasons" / str(year) / f"{station}.json"
            if not season_path.exists():
                errors.append(f"{station} {year}: missing season file")
                continue
            season = load(season_path)
            observations = season.get("observations", [])
            dates = [item.get("date") for item in observations]
            if dates != sorted(dates) or len(dates) != len(set(dates)):
                errors.append(
                    f"{station} {year}: observation dates are not sorted and unique"
                )
            if any(
                "workbook" in str(value).lower()
                for value in season.get("sources", {}).values()
            ):
                errors.append(
                    f"{station} {year}: observation source still references workbook"
                )
            prior_accum: float | None = None
            prior_date: date | None = None
            hazard_days = 0
            source_counts: dict[str, int] = {}
            for item in observations:
                try:
                    day = date.fromisoformat(item["date"])
                except (KeyError, ValueError):
                    errors.append(
                        f"{station} {year}: invalid observation date {item.get('date')}"
                    )
                    continue
                if day.year != year or day.month not in SUMMER_MONTHS:
                    errors.append(
                        f"{station} {year}: out-of-season observation {day}"
                    )
                high, low = item.get("high"), item.get("low")
                if numeric(high) and numeric(low) and high < low:
                    errors.append(
                        f"{station} {day}: high temperature is below low temperature"
                    )
                precip = item.get("precip")
                if numeric(precip) and precip < 0:
                    errors.append(f"{station} {day}: negative precipitation")
                accumulated = item.get("accumulatedPrecip")
                if numeric(accumulated):
                    if (
                        prior_accum is not None
                        and float(accumulated) + 0.011 < prior_accum
                    ):
                        errors.append(
                            f"{station} {day}: accumulated precipitation decreased"
                        )
                    if (
                        prior_accum is not None
                        and prior_date is not None
                        and day == prior_date + timedelta(days=1)
                        and numeric(precip)
                        and abs(
                            (float(accumulated) - prior_accum) - float(precip)
                        )
                        > 0.03
                    ):
                        errors.append(
                            f"{station} {day}: accumulated precipitation does not match daily precipitation"
                        )
                    prior_accum = float(accumulated)
                    prior_date = day
                hazards = item.get("hazards", [])
                invalid = set(hazards) - ALLOWED_HAZARDS
                if invalid:
                    errors.append(
                        f"{station} {day}: invalid/legacy heat codes {sorted(invalid)}"
                    )
                if hazards:
                    hazard_days += 1
                source_name = item.get("dailySource", "unspecified")
                source_counts[source_name] = source_counts.get(source_name, 0) + 1
            if year == 2025 and len(observations) != summer_day_count(year):
                errors.append(
                    f"{station} 2025: expected 122 completed observations, found {len(observations)}"
                )
            if year == 2026:
                total_2026_hazard_days += hazard_days
                if observations and hazard_days == 0:
                    warnings.append(f"{station} 2026: no heat-product days found")
            result["seasons"][str(year)] = {
                "rows": len(observations),
                "dataThrough": season.get("dataThrough"),
                "hazardDays": hazard_days,
                "hazardCounts": {
                    code: sum(
                        code in item.get("hazards", []) for item in observations
                    )
                    for code in sorted(ALLOWED_HAZARDS)
                },
                "dailySources": source_counts,
            }

        history_path = data_root / "history" / f"{station}.json"
        if not history_path.exists():
            errors.append(f"{station}: missing history file")
        else:
            history = load(history_path)
            history_source = history.get("source", {})
            source_text = json.dumps(history_source).lower()
            if "workbook" in source_text or "spreadsheet" in source_text:
                errors.append(
                    f"{station}: history still references workbook/spreadsheet"
                )
            valid_record_source(station, history_source, "history", errors)
            tables = history.get("referenceTables", [])
            if len(tables) < 5 or any(not table.get("rows") for table in tables):
                errors.append(f"{station}: reference tables are incomplete")
            for month in ("06", "07", "08", "09"):
                records = history.get("monthlyPrecipRecords", {}).get(month, {})
                if not records.get("highest") or not records.get("lowest"):
                    errors.append(
                        f"{station}: missing monthly precipitation records for {month}"
                    )
            result["history"] = {
                "source": history_source,
                "tables": len(tables),
                "monthlyPrecipMonths": sorted(
                    history.get("monthlyPrecipRecords", {})
                ),
            }
        station_results[station] = result

    if total_2026_hazard_days == 0:
        errors.append(
            "2026 heat-product archive contains zero product days across all sites"
        )

    return {
        "generatedAt": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "stations": station_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("public/data"))
    parser.add_argument(
        "--report", type=Path, default=Path("public/data/audit/latest.json")
    )
    args = parser.parse_args()
    report = audit(args.data_root)
    if args.report.exists():
        existing = load(args.report)
        comparable_existing = {
            key: value for key, value in existing.items() if key != "generatedAt"
        }
        comparable_report = {
            key: value for key, value in report.items() if key != "generatedAt"
        }
        if comparable_existing == comparable_report:
            report["generatedAt"] = existing.get(
                "generatedAt", report["generatedAt"]
            )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "errors": len(report["errors"]),
                "warnings": len(report["warnings"]),
            },
            indent=2,
        )
    )
    for item in report["warnings"]:
        print(f"WARNING: {item}")
    if report["errors"]:
        for item in report["errors"]:
            print(f"ERROR: {item}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
