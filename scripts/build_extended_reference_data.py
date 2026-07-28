#!/usr/bin/env python3
"""Build official climatology references for every dashboard display year."""

from __future__ import annotations

import argparse
from pathlib import Path

import build_operational_reference_data as operational
import enrich_daily_precip_records as precipitation

DISPLAY_YEARS = (2023, 2024, 2025, 2026)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--start-year", type=int, default=operational.builder.EARLIEST_YEAR)
    parser.add_argument("--through-year", type=int, default=operational.builder.HISTORY_THROUGH)
    args = parser.parse_args()

    # Both modules share the common builder object. Setting this once ensures
    # normals, temperature records, warm-low records, and precipitation records
    # are generated with a year-specific baseline for every selectable season.
    operational.builder.DISPLAY_YEARS = DISPLAY_YEARS
    precipitation.builder.DISPLAY_YEARS = DISPLAY_YEARS

    reference_paths = operational.builder.build(
        args.output,
        start_year=args.start_year,
        through_year=args.through_year,
    )
    print(f"Wrote {len(reference_paths)} official reference files")

    precipitation_paths = precipitation.enrich(args.output, args.through_year)
    print(
        "Added daily precipitation records to "
        f"{len(precipitation_paths)} climatology files"
    )


if __name__ == "__main__":
    main()
