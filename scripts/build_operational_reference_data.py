#!/usr/bin/env python3
"""Run the official reference-data builder with verified climate-thread starts.

RCC ACIS returns a hard "No data available" error when a non-threaded station
is queried wholly before its period of record. The ThreadEx series generally
return empty rows instead. This wrapper applies the verified first date for
each operational climate series before delegating to the common builder.
"""

from __future__ import annotations

from datetime import date

import build_official_reference_data as builder

VERIFIED_STARTS = {
    "MOBthr": date(1871, 1, 1),
    "PNSthr": date(1879, 11, 1),
}

_original_fetch_acis_daily = builder.fetch_acis_daily


def fetch_acis_daily(
    sid: str,
    start: date,
    end: date,
    chunk_years: int = 10,
):
    verified_start = VERIFIED_STARTS.get(sid)
    if verified_start is not None:
        start = max(start, verified_start)
    return _original_fetch_acis_daily(sid, start, end, chunk_years)


builder.fetch_acis_daily = fetch_acis_daily


if __name__ == "__main__":
    builder.main()
