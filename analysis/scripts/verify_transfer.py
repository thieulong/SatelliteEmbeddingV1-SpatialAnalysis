#!/usr/bin/env python3
"""Check whether the essential local-only AusHabitat data was transferred."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


YEARS = range(2017, 2025)
INTERVALS = [(year, year + 1) for year in YEARS[:-1]]


def check(path: Path, issues: list[str], label: str) -> None:
    if not path.exists():
        issues.append(f"MISSING: {label}: {path}")
    elif path.is_file() and path.stat().st_size == 0:
        issues.append(f"EMPTY: {label}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    issues: list[str] = []

    raster_dir = root / "GEE_BassCoast_Data"
    core = [
        "basscoast_endpoint_change_2017_2024.tif",
        "basscoast_endpoint_hotspots_2017_2024.tif",
        "basscoast_persistence_count.tif",
        "basscoast_variance_annual_change.tif",
        "basscoast_slope_annual_change.tif",
        "basscoast_first_hotspot_year.tif",
        "basscoast_max_change_year.tif",
        "basscoast_cumulative_change.tif",
        "basscoast_mean_annual_change.tif",
        "basscoast_max_annual_change.tif",
    ]
    for name in core:
        check(raster_dir / name, issues, "authoritative embedding raster")
    for start, end in INTERVALS:
        check(
            raster_dir / f"basscoast_annual_change_{start}_{end}.tif",
            issues,
            "annual embedding change raster",
        )
        check(
            raster_dir / f"basscoast_annual_hotspot_{start}_{end}.tif",
            issues,
            "annual embedding hotspot raster",
        )

    phase2 = root / "BassCoast_Phase2_Pixel_Sampling_outputs"
    check(phase2 / "basscoast_phase2_sampled_pixels.csv", issues, "Phase 2 sample")
    check(phase2 / "basscoast_phase2b_review_points.csv", issues, "Phase 2B review sample")

    phase9 = root / "BassCoast_Phase9_Map_Data_Preparation_outputs"
    check(phase9 / "basscoast_phase9_map_data_manifest.json", issues, "Phase 9 manifest")
    check(phase9 / "rasters/basscoast_change_state_30m.tif", issues, "30 m change-state raster")

    phase10 = root / "BassCoast_Phase10_WallToWall_Context_outputs"
    manifest = phase10 / "basscoast_phase10_manifest.json"
    check(manifest, issues, "Phase 10 manifest")
    check(phase10 / "basscoast_phase10_region_summary.csv", issues, "region summary")
    check(phase10 / "basscoast_phase10_region_year_context.csv", issues, "region-year context")
    for year in YEARS:
        check(
            phase10 / f"rasters/basscoast_dea_level3_{year}_30m.tif",
            issues,
            "DEA Level 3 raster",
        )
        check(
            phase10 / f"rasters/basscoast_dea_level4_{year}_30m.tif",
            issues,
            "DEA Level 4 raster",
        )
        check(
            phase10 / f"rasters/basscoast_ndvi_{year}_30m.tif",
            issues,
            "NDVI raster",
        )

    sentinel = root / "AusHabitat_Sentinel2_Annual"
    for year in range(2017, 2026):
        check(
            sentinel / f"bass_coast_sentinel2_annual_{year}.tif",
            issues,
            "optional Sentinel-2 visual export",
        )

    print(f"Project root: {root}")
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        print(
            "Phase 10 manifest: "
            f"{data.get('region_count', 'unknown')} regions, "
            f"{data.get('region_year_rows', 'unknown')} region-year rows"
        )
    if issues:
        print(f"Transfer check found {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Transfer check passed: all expected core and optional imagery files are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
