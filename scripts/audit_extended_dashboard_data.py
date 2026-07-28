#!/usr/bin/env python3
"""Audit every selectable dashboard year, including complete historical seasons."""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import audit_dashboard_data as dashboard_audit
import build_official_reference_data as reference_builder

DISPLAY_YEARS = (2023, 2024, 2025, 2026)
COMPLETED_YEARS = (2023, 2024, 2025)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(path: Path, report: dict[str, Any]) -> None:
    report["generatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report["status"] = "pass" if not report.get("errors") else "fail"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def audit_completed_seasons(data_root: Path, report: dict[str, Any]) -> None:
    errors = report.setdefault("errors", [])
    for station in reference_builder.STATIONS:
        for year in COMPLETED_YEARS:
            path = data_root / "seasons" / str(year) / f"{station}.json"
            if not path.exists():
                message = f"{station} {year}: missing completed historical season file"
                if message not in errors:
                    errors.append(message)
                continue
            observations = load_json(path).get("observations", [])
            expected = dashboard_audit.summer_day_count(year)
            if len(observations) != expected:
                message = (
                    f"{station} {year}: expected {expected} completed observations, "
                    f"found {len(observations)}"
                )
                if message not in errors:
                    errors.append(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("public/data"))
    parser.add_argument(
        "--report", type=Path, default=Path("public/data/audit/latest.json")
    )
    args = parser.parse_args()

    dashboard_audit.DISPLAY_YEARS = DISPLAY_YEARS
    report = dashboard_audit.audit(args.data_root)
    audit_completed_seasons(args.data_root, report)
    write_report(args.report, report)

    # The precipitation-record auditor imports DISPLAY_YEARS by value, so set
    # the shared builder first and import it only after that change.
    reference_builder.DISPLAY_YEARS = DISPLAY_YEARS
    precip_audit = importlib.import_module("audit_daily_precip_records")
    precip_audit.DISPLAY_YEARS = DISPLAY_YEARS
    try:
        precip_audit.audit(args.data_root, args.report)
    except SystemExit:
        # Report all failures together below instead of stopping after the
        # precipitation-specific portion of the audit.
        pass

    final_report = load_json(args.report)
    errors = final_report.get("errors", [])
    print(
        json.dumps(
            {
                "status": final_report.get("status"),
                "errors": len(errors),
                "warnings": len(final_report.get("warnings", [])),
                "displayYears": list(DISPLAY_YEARS),
            },
            indent=2,
        )
    )
    for warning in final_report.get("warnings", []):
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
