#!/usr/bin/env python3
"""Convert a fresh copy of the LIX dashboard into the WFO MOB dashboard."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}

GENERAL_REPLACEMENTS = (
    ("lix-summer-climate-dashboard", "mob-summer-climate-dashboard"),
    ("LIX Summer Climate Dashboard", "MOB Summer Climate Dashboard"),
    ("WFO LIX", "WFO MOB"),
    ("LIX climate", "MOB climate"),
    ("LIX summer", "MOB summer"),
    ("lix-climate", "mob-climate"),
    ("four primary WFO MOB climate sites", "two primary WFO MOB climate sites"),
    ("four regional climate sites", "two regional climate sites"),
    ("across all four sites", "across both sites"),
    ("all four sites", "both sites"),
    ("KBTR", "KMOB"),
    ("KMSY", "KPNS"),
    ("KGPT", "KMOB"),
    ("KMCB", "KPNS"),
)

STATION_CONFIG = '''STATIONS: dict[str, dict[str, Any]] = {
    "KMOB": {
        "name": "Mobile, AL",
        "ghcn": "USW00013894",
        "record_sid": "MOBthr",
        "lat": 30.6882,
        "lon": -88.2460,
    },
    "KPNS": {
        "name": "Pensacola, FL",
        "ghcn": "USW00013899",
        "record_sid": "PNSthr",
        "lat": 30.4761,
        "lon": -87.1858,
    },
}
'''

LIVE_STATION_CONFIG = '''STATIONS = {
    "KMOB": {**REFERENCE_STATIONS["KMOB"], "iem": "MOB", "network": "AL_ASOS"},
    "KPNS": {**REFERENCE_STATIONS["KPNS"], "iem": "PNS", "network": "FL_ASOS"},
}
'''

VERIFIED_STARTS = '''VERIFIED_STARTS = {
    "MOBthr": date(1871, 1, 1),
    "PNSthr": date(1879, 11, 1),
}
'''

EXPECTED_RECORD_STARTS = '''EXPECTED_RECORD_STARTS = {
    "KMOB": date(1871, 1, 1),
    "KPNS": date(1879, 11, 1),
}
'''

STATIONS_JSON = [
    {
        "code": "KMOB",
        "name": "Mobile, AL",
        "city": "Mobile",
        "state": "AL",
        "availableYears": [2026, 2025, 2024, 2023],
        "latestYear": 2026,
    },
    {
        "code": "KPNS",
        "name": "Pensacola, FL",
        "city": "Pensacola",
        "state": "FL",
        "availableYears": [2026, 2025, 2024, 2023],
        "latestYear": 2026,
    },
]

README = """# MOB Summer Climate Dashboard

A responsive GitHub Pages dashboard for summer climate statistics at the two official WFO Mobile climate sites:

- KMOB — Mobile, Alabama
- KPNS — Pensacola, Florida

The dashboard follows the same audited architecture as the LIX Summer Climate Dashboard. It combines current airport observations and 1991–2020 normals with long-term operational climate threads, heat products, rainfall statistics, and historical ranking tables.

## Data sources

### NOAA/NCEI observations and normals

| Site | Current GHCN-Daily station |
|---|---|
| KMOB | USW00013894 — Mobile Regional Airport |
| KPNS | USW00013899 — Pensacola International Airport |

Daily high temperature, low temperature, and precipitation preferentially come from NOAA/NCEI Daily Summaries. Daily normal high and low temperatures and year-to-date normal precipitation use the 1991–2020 U.S. Climate Normals.

### Operational climate records

| Site | RCC ACIS ThreadEx series | Operational record begins |
|---|---|---|
| KMOB | MOBthr — Mobile Area | January 1, 1871 |
| KPNS | PNSthr — Pensacola Area | November 1, 1879 |

ThreadEx preserves each official climate record across station moves. Record comparisons use only years preceding the displayed season, so the 2026 dashboard compares against records through 2025.

### Heat products

Recent Heat Advisory (`HT.Y`), Extreme Heat Watch (`XH.A`), and Extreme Heat Warning (`XH.W`) information comes from the official NWS API. The Iowa Environmental Mesonet archive of NWS-issued VTEC products reconstructs the remainder of each summer.

## Automated updates and validation

The scheduled GitHub Actions workflow:

1. Rebuilds official normals and climate-thread references when needed.
2. Refreshes completed daily observations and heat products.
3. Reconstructs completed comparison seasons.
4. Audits every published station, year, record table, and source attribution.
5. Runs JavaScript calculation tests and builds the Vite site.
6. Deploys the audited dashboard to GitHub Pages.

The latest machine-readable audit is published at:

`https://jaczerin24.github.io/mob-summer-climate-dashboard/data/audit/latest.json`

## Local development

Requires Python 3.12 and Node.js 20.19+ or 22.12+.

```bash
python scripts/build_extended_reference_data.py --through-year 2025
for year in 2023 2024 2025; do
  python scripts/update_live_data.py --year "$year" --through "$year-09-30"
done
python scripts/update_live_data.py --year 2026
python scripts/audit_extended_dashboard_data.py
npm install
npm test
npm run dev
```

Production build:

```bash
npm run build
```

## Site

`https://jaczerin24.github.io/mob-summer-climate-dashboard/`
"""


def replace_block(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"Expected one configurable block in {path}, found {count}")
    path.write_text(updated, encoding="utf-8")


def clear_generated_data(root: Path) -> None:
    data_root = root / "public" / "data"
    for name in ("audit", "climatology", "history", "seasons"):
        shutil.rmtree(data_root / name, ignore_errors=True)
    overrides = data_root / "overrides"
    shutil.rmtree(overrides, ignore_errors=True)
    overrides.mkdir(parents=True, exist_ok=True)
    (overrides / "2026.json").write_text(
        json.dumps({"stations": {}}, indent=2) + "\n", encoding="utf-8"
    )


def apply_general_replacements(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts or ".bootstrap" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in GENERAL_REPLACEMENTS:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def configure_sources(root: Path) -> None:
    builder = root / "scripts" / "build_official_reference_data.py"
    replace_block(
        builder,
        r"STATIONS: dict\[str, dict\[str, Any\]\] = \{.*?\n\}\n",
        STATION_CONFIG,
    )
    text = builder.read_text(encoding="utf-8")
    text = text.replace(
        "The ACIS ThreadEx series preserve the operational climate thread across station\n"
        "moves. This is essential for Baton Rouge, New Orleans, and Gulfport, where a\n"
        "single current-airport GHCN station does not cover the full climate record.",
        "The ACIS ThreadEx series preserve the operational climate thread across station\n"
        "moves. This is essential for Mobile and Pensacola, where a single current-airport\n"
        "GHCN station does not cover the full official climate record.",
    )
    builder.write_text(text, encoding="utf-8")

    replace_block(
        root / "scripts" / "update_live_data.py",
        r"STATIONS = \{.*?\n\}\n",
        LIVE_STATION_CONFIG,
    )
    replace_block(
        root / "scripts" / "build_operational_reference_data.py",
        r"VERIFIED_STARTS = \{.*?\n\}\n",
        VERIFIED_STARTS,
    )
    replace_block(
        root / "scripts" / "audit_dashboard_data.py",
        r"EXPECTED_RECORD_STARTS = \{.*?\n\}\n",
        EXPECTED_RECORD_STARTS,
    )


def configure_frontend(root: Path) -> None:
    constants = root / "src" / "lib" / "constants.js"
    text = constants.read_text(encoding="utf-8").replace(
        'export const DEFAULT_STATION = "KMOB";',
        'export const DEFAULT_STATION = "KMOB";',
    )
    constants.write_text(text, encoding="utf-8")

    index_path = root / "index.html"
    text = index_path.read_text(encoding="utf-8")
    text = re.sub(
        r'content="Interactive summer climate statistics for .*?\."',
        'content="Interactive summer climate statistics for Mobile and Pensacola."',
        text,
    )
    text = text.replace("<title>MOB Summer Climate Dashboard</title>", "<title>MOB Summer Climate Dashboard</title>")
    index_path.write_text(text, encoding="utf-8")

    stations_path = root / "public" / "data" / "stations.json"
    stations_path.parent.mkdir(parents=True, exist_ok=True)
    stations_path.write_text(json.dumps(STATIONS_JSON, indent=2) + "\n", encoding="utf-8")

    main_path = root / "src" / "main.js"
    text = main_path.read_text(encoding="utf-8")
    text = text.replace(
        "Audited daily observations, 1991–2020 normals, operational climate records, heat products, rainfall, and historical context for two regional climate sites.",
        "Audited daily observations, 1991–2020 normals, operational climate records, heat products, rainfall, and historical context for Mobile and Pensacola.",
    )
    main_path.write_text(text, encoding="utf-8")


def write_documentation(root: Path) -> None:
    (root / "README.md").write_text(README, encoding="utf-8")


def verify(root: Path) -> None:
    forbidden = (
        "WFO LIX",
        "lix-summer-climate-dashboard",
        "KBTR",
        "KMSY",
        "KGPT",
        "KMCB",
        "Baton Rouge",
        "New Orleans",
        "Gulfport",
        "McComb",
    )
    leftovers: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts or ".bootstrap" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        hits = [token for token in forbidden if token in text]
        if hits:
            leftovers.append(f"{path.relative_to(root)}: {', '.join(hits)}")
    if leftovers:
        raise RuntimeError("Unconverted LIX references remain:\n" + "\n".join(leftovers))

    station_codes = {item["code"] for item in STATIONS_JSON}
    if station_codes != {"KMOB", "KPNS"}:
        raise RuntimeError(f"Unexpected station set: {sorted(station_codes)}")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    clear_generated_data(root)
    apply_general_replacements(root)
    configure_sources(root)
    configure_frontend(root)
    write_documentation(root)
    verify(root)
    print("Configured MOB dashboard for KMOB and KPNS")


if __name__ == "__main__":
    main()
