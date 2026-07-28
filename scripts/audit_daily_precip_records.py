#!/usr/bin/env python3
"""Validate daily precipitation records and append results to the data audit."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_official_reference_data import DISPLAY_YEARS, STATIONS


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_years(value: Any) -> list[int]:
    return [int(item) for item in re.findall(r"\b\d{4}\b", str(value or ""))]


def compare_precip(observed: Any, record: Any) -> str:
    if not numeric(observed) or not numeric(record):
        return "none"
    if float(observed) > float(record):
        return "broken"
    if float(observed) == float(record):
        return "tied"
    return "none"


def audit(data_root: Path, report_path: Path) -> dict[str, Any]:
    report = load_json(report_path) if report_path.exists() else {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "pass",
        "errors": [],
        "warnings": [],
        "stations": {},
    }
    new_errors: list[str] = []
    station_results: dict[str, Any] = {}
    total_checked = 0

    for station in STATIONS:
        station_results[station] = {}
        for year in DISPLAY_YEARS:
            climate_path = data_root / "climatology" / str(year) / f"{station}.json"
            season_path = data_root / "seasons" / str(year) / f"{station}.json"
            if not climate_path.exists():
                new_errors.append(f"{station} {year}: missing climatology for rainfall-record audit")
                continue

            climate = load_json(climate_path)
            daily = climate.get("daily", {})
            checked = 0
            for key, row in sorted(daily.items()):
                record = row.get("recordPrecip")
                years = parse_years(row.get("recordPrecipYears"))
                if not numeric(record) or float(record) < 0:
                    new_errors.append(
                        f"{station} {year} {key}: missing or invalid daily precipitation record"
                    )
                if not years:
                    new_errors.append(
                        f"{station} {year} {key}: missing daily precipitation record year(s)"
                    )
                elif any(record_year >= year for record_year in years):
                    new_errors.append(
                        f"{station} {year} {key}: precipitation record year is not before display year"
                    )
                checked += 1

            ties = 0
            breaks = 0
            if season_path.exists():
                season = load_json(season_path)
                for observation in season.get("observations", []):
                    climate_row = daily.get(str(observation.get("date", ""))[5:10], {})
                    status = compare_precip(
                        observation.get("precip"), climate_row.get("recordPrecip")
                    )
                    ties += status == "tied"
                    breaks += status == "broken"

            station_results[station][str(year)] = {
                "checkedRows": checked,
                "observedTies": ties,
                "observedBreaks": breaks,
            }
            total_checked += checked

    report_errors = report.setdefault("errors", [])
    for error in new_errors:
        if error not in report_errors:
            report_errors.append(error)
    report["status"] = "pass" if not report_errors else "fail"
    report["dailyPrecipRecords"] = {
        "status": "pass" if not new_errors else "fail",
        "checkedRows": total_checked,
        "stations": station_results,
    }
    report["generatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": report["dailyPrecipRecords"]["status"],
                "checkedRows": total_checked,
                "errors": len(new_errors),
            },
            indent=2,
        )
    )
    if new_errors:
        for error in new_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("public/data"))
    parser.add_argument(
        "--report", type=Path, default=Path("public/data/audit/latest.json")
    )
    args = parser.parse_args()
    audit(args.data_root, args.report)


if __name__ == "__main__":
    main()
