# MOB Summer Climate Dashboard

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

| Site | RCC ACIS ThreadEx series | Temperature record begins |
|---|---|---|
| KMOB | MOBthr — Mobile Area | January 1, 1872 |
| KPNS | PNSthr — Pensacola Area | November 1, 1879 |

The Mobile ThreadEx precipitation archive includes data from 1871, while the official temperature record begins in 1872. ThreadEx preserves each official climate record across station moves. Record comparisons use only years preceding the displayed season, so the 2026 dashboard compares against records through 2025.

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
