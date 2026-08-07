from pathlib import Path
import json
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one replacement target, found {text.count(old)}")
    p.write_text(text.replace(old, new), encoding="utf-8")


build_path = Path("scripts/build_official_reference_data.py")
text = build_path.read_text(encoding="utf-8")
old_stations = '''STATIONS: dict[str, dict[str, Any]] = {
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
}'''
new_stations = '''STATIONS: dict[str, dict[str, Any]] = {
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
}'''
if text.count(old_stations) != 1:
    raise SystemExit("build_official_reference_data.py: station block did not match")
text = text.replace(old_stations, new_stations)
old_source = '''def acis_source(
    meta: dict[str, Any],
    acis_meta: dict[str, Any],
    through_year: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "agency": "NOAA Regional Climate Center Program / RCC ACIS",
        "dataset": "ACIS ThreadEx daily climate series",
        "stationId": meta["record_sid"],
        "stationName": acis_meta.get("name"),
        "sourceIds": acis_meta.get("sids", []),
        "throughYear": through_year,
        "periodOfRecord": source_period(rows, through_year),
        "basis": "Operational threaded climate series used for station records",
        "url": ACIS_STN_DATA,
    }'''
new_source = '''def acis_source(
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
    }'''
if text.count(old_source) != 1:
    raise SystemExit("build_official_reference_data.py: ACIS source block did not match")
text = text.replace(old_source, new_source)
text = text.replace(
    'f"Downloading NCEI normals and ACIS climate thread for {code} "',
    'f"Downloading NCEI normals and ACIS climate series for {code} "',
)
build_path.write_text(text, encoding="utf-8")

replace_once(
    "scripts/update_live_data.py",
    '''STATIONS = {
    "KMOB": {**REFERENCE_STATIONS["KMOB"], "iem": "MOB", "network": "AL_ASOS"},
    "KPNS": {**REFERENCE_STATIONS["KPNS"], "iem": "PNS", "network": "FL_ASOS"},
}''',
    '''STATIONS = {
    "KMOB": {**REFERENCE_STATIONS["KMOB"], "iem": "MOB", "network": "AL_ASOS"},
    "KPNS": {**REFERENCE_STATIONS["KPNS"], "iem": "PNS", "network": "FL_ASOS"},
    "KGZH": {**REFERENCE_STATIONS["KGZH"], "iem": "GZH", "network": "AL_ASOS"},
    "KCEW": {**REFERENCE_STATIONS["KCEW"], "iem": "CEW", "network": "FL_ASOS"},
    "KDTS": {**REFERENCE_STATIONS["KDTS"], "iem": "DTS", "network": "FL_ASOS"},
}''',
)

replace_once(
    "scripts/build_operational_reference_data.py",
    '''VERIFIED_STARTS = {
    "MOBthr": date(1871, 1, 1),
    "PNSthr": date(1879, 11, 1),
}''',
    '''VERIFIED_STARTS = {
    "MOBthr": date(1871, 1, 1),
    "PNSthr": date(1879, 11, 1),
    "USW00053820": date(1997, 6, 1),
    "USW00013884": date(1948, 1, 1),
    "USW00053853": date(1996, 12, 2),
}''',
)

audit_path = Path("scripts/audit_dashboard_data.py")
audit = audit_path.read_text(encoding="utf-8")
old_starts = '''EXPECTED_RECORD_STARTS = {
    "KMOB": date(1872, 1, 1),
    "KPNS": date(1879, 11, 1),
}'''
new_starts = '''EXPECTED_RECORD_STARTS = {
    "KMOB": date(1872, 1, 1),
    "KPNS": date(1879, 11, 1),
    "KGZH": date(1997, 6, 1),
    "KCEW": date(1948, 1, 1),
    "KDTS": date(1996, 12, 2),
}'''
if audit.count(old_starts) != 1:
    raise SystemExit("audit_dashboard_data.py: expected-start block did not match")
audit = audit.replace(old_starts, new_starts)
pattern = re.compile(r'def valid_record_source\(.*?\n\ndef audit\(', re.S)
replacement = '''def valid_record_source(
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


def audit('''
audit, count = pattern.subn(replacement, audit, count=1)
if count != 1:
    raise SystemExit("audit_dashboard_data.py: valid_record_source function did not match")
audit = audit.replace(
    '"2026 heat-product archive contains zero product days across both sites"',
    '"2026 heat-product archive contains zero product days across all sites"',
)
audit_path.write_text(audit, encoding="utf-8")

stations = [
    {"code": "KMOB", "name": "Mobile, AL", "city": "Mobile", "state": "AL", "availableYears": [2026, 2025, 2024, 2023], "latestYear": 2026},
    {"code": "KPNS", "name": "Pensacola, FL", "city": "Pensacola", "state": "FL", "availableYears": [2026, 2025, 2024, 2023], "latestYear": 2026},
    {"code": "KGZH", "name": "Evergreen, AL", "city": "Evergreen", "state": "AL", "availableYears": [2026, 2025, 2024, 2023], "latestYear": 2026},
    {"code": "KCEW", "name": "Crestview, FL", "city": "Crestview", "state": "FL", "availableYears": [2026, 2025, 2024, 2023], "latestYear": 2026},
    {"code": "KDTS", "name": "Destin, FL", "city": "Destin", "state": "FL", "availableYears": [2026, 2025, 2024, 2023], "latestYear": 2026},
]
Path("public/data/stations.json").write_text(json.dumps(stations, indent=2) + "\n", encoding="utf-8")

replace_once(
    "index.html",
    "Interactive summer climate statistics for Mobile and Pensacola.",
    "Interactive summer climate statistics for Mobile, Pensacola, Evergreen, Crestview, and Destin.",
)
replace_once(
    "src/main.js",
    "Audited daily observations, 1991–2020 normals, operational climate records, heat products, rainfall, and historical context for Mobile and Pensacola.",
    "Audited daily observations, 1991–2020 normals, operational climate records, heat products, rainfall, and historical context for Mobile, Pensacola, Evergreen, Crestview, and Destin.",
)
