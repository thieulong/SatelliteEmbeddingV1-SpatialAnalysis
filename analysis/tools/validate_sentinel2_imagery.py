#!/usr/bin/env python3
"""Validate annual Sentinel-2 RGB exports before publishing them as map tiles."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import rasterio


EXPECTED_YEARS = tuple(range(2017, 2026))
YEAR_PATTERN = re.compile(r"(20\d{2})")


def find_year(path: Path) -> int | None:
    matches = YEAR_PATTERN.findall(path.stem)
    return int(matches[-1]) if matches else None


def inspect(path: Path) -> dict:
    with rasterio.open(path) as src:
        resolution = tuple(abs(value) for value in src.res)
        problems = []
        if src.count not in (3, 4):
            problems.append(f"expected 3 or 4 bands, found {src.count}")
        if any(dtype != "uint8" for dtype in src.dtypes):
            problems.append(f"expected uint8 bands, found {src.dtypes}")
        if not src.crs or not src.crs.is_projected:
            problems.append(f"expected a projected CRS, found {src.crs}")
        if src.crs and src.crs.is_projected and max(abs(value - 10) for value in resolution) > 0.5:
            problems.append(f"expected approximately 10 m pixels, found {resolution}")
        return {
            "file": str(path),
            "width": src.width,
            "height": src.height,
            "bands": src.count,
            "dtypes": list(src.dtypes),
            "crs": str(src.crs),
            "resolution": list(resolution),
            "cloud_optimized": bool(src.profile.get("tiled")),
            "problems": problems,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, help="Folder containing annual Sentinel-2 GeoTIFFs")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    paths = sorted([*args.folder.glob("*.tif"), *args.folder.glob("*.tiff")])
    records = []
    by_year = {}
    for path in paths:
        year = find_year(path)
        if year not in EXPECTED_YEARS:
            continue
        record = inspect(path)
        record["year"] = year
        records.append(record)
        by_year.setdefault(year, []).append(record)

    missing = [year for year in EXPECTED_YEARS if year not in by_year]
    duplicates = {year: len(items) for year, items in by_year.items() if len(items) > 1}
    invalid = [record for record in records if record["problems"]]
    report = {
        "expected_years": list(EXPECTED_YEARS),
        "files_checked": len(records),
        "missing_years": missing,
        "duplicate_years": duplicates,
        "invalid_files": invalid,
        "files": records,
        "passed": not missing and not duplicates and not invalid,
    }

    print(f"Checked {len(records)} annual Sentinel-2 file(s).")
    print(f"Missing years: {missing or 'none'}")
    print(f"Duplicate years: {duplicates or 'none'}")
    for record in invalid:
        print(f"INVALID {record['file']}: {'; '.join(record['problems'])}")
    print("Validation passed." if report["passed"] else "Validation needs attention.")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Report saved to {args.report}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
