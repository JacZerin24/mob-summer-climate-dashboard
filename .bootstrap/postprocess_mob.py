#!/usr/bin/env python3
"""Apply source-specific refinements after the LIX-to-MOB conversion."""

from __future__ import annotations

from pathlib import Path


def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    # Mobile's temperature record begins in 1872. The ThreadEx precipitation
    # archive reaches back into 1871, so the data fetch intentionally begins
    # earlier than the minimum temperature-record period enforced by the audit.
    replace_required(
        root / "scripts" / "audit_dashboard_data.py",
        '"KMOB": date(1871, 1, 1),',
        '"KMOB": date(1872, 1, 1),',
    )

    replace_required(
        root / "README.md",
        "| Site | RCC ACIS ThreadEx series | Operational record begins |",
        "| Site | RCC ACIS ThreadEx series | Temperature record begins |",
    )
    replace_required(
        root / "README.md",
        "| KMOB | MOBthr — Mobile Area | January 1, 1871 |",
        "| KMOB | MOBthr — Mobile Area | January 1, 1872 |",
    )
    replace_required(
        root / "README.md",
        "ThreadEx preserves each official climate record across station moves.",
        "The Mobile ThreadEx precipitation archive includes data from 1871, while the official temperature record begins in 1872. ThreadEx preserves each official climate record across station moves.",
    )

    print("Applied Mobile climate-period refinements")


if __name__ == "__main__":
    main()
