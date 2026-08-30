#!/usr/bin/env python3
"""
Benchmark external validation stacks for Bass Coast pixel history.

The script tests three candidate sources for Phase 3 validation:
1. DEA Land Cover annual class history via continental COG mosaics.
2. DEA Fractional Cover Percentiles via DEA STAC + COG assets.
3. Dynamic World via Google Earth Engine, if installed/authenticated.

It is designed to be run in Google Colab or any Python environment with the
geospatial dependencies installed. It writes CSV/JSON outputs to the local
workspace by default.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_LON = 145.5909
DEFAULT_LAT = -38.6049
DEFAULT_YEARS = list(range(2017, 2025))

DEA_LANDCOVER_PRODUCT = "ga_ls_landcover_class_cyear_3"
DEA_LANDCOVER_VERSION = "2-0-0"
DEA_FC_PRODUCT = "ga_ls_fc_pc_cyear_3"
DEA_FC_STAC_COLLECTION = "ga_ls_fc_pc_cyear_3"
DEA_STAC_SEARCH_URL = "https://explorer.dea.ga.gov.au/stac/search"

DEA_LEVEL3_LABELS = {
    111: "Cultivated Terrestrial Vegetation (CTV)",
    112: "(Semi-)Natural Terrestrial Vegetation (NTV)",
    124: "Natural Aquatic Vegetation (NAV)",
    215: "Artificial Surface (AS)",
    216: "Natural Bare Surface (NS)",
    220: "Water",
    255: "No data",
}

DW_LABELS = {
    0: "water",
    1: "trees",
    2: "grass",
    3: "flooded_vegetation",
    4: "crops",
    5: "shrub_and_scrub",
    6: "built",
    7: "bare",
    8: "snow_and_ice",
}

DW_CLASSES = [
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
]


@dataclass
class StackResult:
    stack: str
    status: str = "not_run"
    elapsed_seconds: float | None = None
    records: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def successful_records(self) -> int:
        return sum(1 for record in self.records if record.get("ok"))

    @property
    def attempted_records(self) -> int:
        return len(self.records)

    @property
    def success_rate(self) -> float:
        if not self.records:
            return 0.0
        return self.successful_records / len(self.records)


def import_or_error(module_name: str):
    try:
        return __import__(module_name)
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise RuntimeError(f"Missing dependency '{module_name}': {exc}") from exc


def parse_years(text: str) -> list[int]:
    if ":" in text:
        start, end = [int(part) for part in text.split(":", 1)]
        return list(range(start, end + 1))
    return [int(part.strip()) for part in text.split(",") if part.strip()]


def landcover_cog_url(year: int, band: str) -> str:
    return (
        "https://data.dea.ga.gov.au/derivative/"
        f"{DEA_LANDCOVER_PRODUCT}/{DEA_LANDCOVER_VERSION}/continental_mosaics/"
        f"{year}--P1Y/{DEA_LANDCOVER_PRODUCT}_mosaic_{year}--P1Y_{band}.tif"
    )


def transform_lonlat_to_dataset_xy(src, lon: float, lat: float) -> tuple[float, float]:
    rasterio_warp = import_or_error("rasterio.warp")
    xs, ys = rasterio_warp.transform("EPSG:4326", src.crs, [lon], [lat])
    return xs[0], ys[0]


def sample_cog_value(url: str, lon: float, lat: float) -> dict[str, Any]:
    rasterio = import_or_error("rasterio")

    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(url) as src:
            x, y = transform_lonlat_to_dataset_xy(src, lon, lat)
            row, col = src.index(x, y)
            value = next(src.sample([(x, y)], masked=True))[0]
            masked = bool(getattr(value, "mask", False))
            if masked:
                numeric_value = None
            else:
                numeric_value = int(value) if float(value).is_integer() else float(value)
            return {
                "ok": not masked,
                "value": numeric_value,
                "row": int(row),
                "col": int(col),
                "crs": str(src.crs),
                "resolution_x": abs(float(src.transform.a)),
                "resolution_y": abs(float(src.transform.e)),
                "url": url,
            }


def run_dea_landcover(lon: float, lat: float, years: list[int], stress_points: list[tuple[float, float]]) -> StackResult:
    result = StackResult(
        stack="dea_landcover",
        notes=[
            "Annual categorical land-cover evidence.",
            "Uses public DEA continental COG mosaics; no website crawling.",
            "Level 3 is simple and stable; Level 4 is more descriptive.",
        ],
    )
    started = time.perf_counter()
    try:
        for point_id, (point_lon, point_lat) in enumerate(stress_points, start=1):
            for year in years:
                record = {
                    "stack": result.stack,
                    "point_id": point_id,
                    "lon": point_lon,
                    "lat": point_lat,
                    "year": year,
                }
                try:
                    level3 = sample_cog_value(landcover_cog_url(year, "level3"), point_lon, point_lat)
                    level4 = sample_cog_value(landcover_cog_url(year, "level4"), point_lon, point_lat)
                    record.update(
                        ok=bool(level3["ok"] and level4["ok"]),
                        level3_code=level3["value"],
                        level3_label=DEA_LEVEL3_LABELS.get(level3["value"], f"Level 3 code {level3['value']}"),
                        level4_code=level4["value"],
                        level4_label=f"Level 4 code {level4['value']}",
                        resolution_m=level3.get("resolution_x"),
                    )
                except Exception as exc:
                    record.update(ok=False, error=str(exc))
                    result.errors.append(f"point {point_id} year {year}: {exc}")
                result.records.append(record)
        result.status = "ok" if result.successful_records else "failed"
    finally:
        result.elapsed_seconds = time.perf_counter() - started
    return result


def stac_search(collection: str, lon: float, lat: float, year: int) -> list[dict[str, Any]]:
    requests = import_or_error("requests")
    eps = 0.0001
    payload = {
        "collections": [collection],
        "bbox": [lon - eps, lat - eps, lon + eps, lat + eps],
        "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z",
        "limit": 20,
    }
    response = requests.post(DEA_STAC_SEARCH_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data.get("features", [])


def asset_href(item: dict[str, Any], asset_name: str) -> str | None:
    assets = item.get("assets", {})
    if asset_name in assets:
        return assets[asset_name].get("href")
    for key, asset in assets.items():
        if key.lower() == asset_name.lower() or key.lower().endswith(asset_name.lower()):
            return asset.get("href")
    return None


def run_dea_fractional_cover(lon: float, lat: float, years: list[int], stress_points: list[tuple[float, float]]) -> StackResult:
    result = StackResult(
        stack="dea_fractional_cover_percentiles",
        notes=[
            "Annual continuous evidence: green vegetation, non-green vegetation, bare soil.",
            "Uses DEA STAC to discover annual tile assets, then samples COG assets.",
            "More descriptive for vegetation/bare-ground dynamics, but not a categorical land-cover label.",
        ],
    )
    started = time.perf_counter()
    try:
        for point_id, (point_lon, point_lat) in enumerate(stress_points, start=1):
            for year in years:
                record = {
                    "stack": result.stack,
                    "point_id": point_id,
                    "lon": point_lon,
                    "lat": point_lat,
                    "year": year,
                }
                try:
                    items = stac_search(DEA_FC_STAC_COLLECTION, point_lon, point_lat, year)
                    if not items:
                        raise RuntimeError("No STAC items returned")
                    item = items[0]
                    values = {}
                    for band in ["pv_pc_50", "npv_pc_50", "bs_pc_50", "qa"]:
                        href = asset_href(item, band)
                        if href is None:
                            raise RuntimeError(f"Missing STAC asset for band {band}")
                        sampled = sample_cog_value(href, point_lon, point_lat)
                        values[band] = sampled["value"] if sampled["ok"] else None
                    record.update(
                        ok=all(values[b] is not None for b in ["pv_pc_50", "npv_pc_50", "bs_pc_50"]),
                        pv_pc_50=values["pv_pc_50"],
                        npv_pc_50=values["npv_pc_50"],
                        bs_pc_50=values["bs_pc_50"],
                        qa=values["qa"],
                        resolution_m=30,
                        stac_item_id=item.get("id"),
                    )
                except Exception as exc:
                    record.update(ok=False, error=str(exc))
                    result.errors.append(f"point {point_id} year {year}: {exc}")
                result.records.append(record)
        result.status = "ok" if result.successful_records else "failed"
    finally:
        result.elapsed_seconds = time.perf_counter() - started
    return result


def run_dynamic_world(lon: float, lat: float, years: list[int], stress_points: list[tuple[float, float]]) -> StackResult:
    result = StackResult(
        stack="dynamic_world",
        notes=[
            "Annual 10 m categorical/probability evidence from Sentinel-2.",
            "Requires Google Earth Engine package and authentication.",
            "Best spatial resolution match to embedding pixels, but has more operational auth/API friction.",
        ],
    )
    started = time.perf_counter()
    try:
        try:
            import ee  # type: ignore
        except Exception as exc:
            result.status = "skipped"
            result.errors.append(f"earthengine-api is not installed: {exc}")
            return result

        try:
            ee.Initialize()
        except Exception as exc:
            result.status = "skipped"
            result.errors.append(f"Earth Engine is not authenticated/initialized: {exc}")
            return result

        for point_id, (point_lon, point_lat) in enumerate(stress_points, start=1):
            point = ee.Geometry.Point([point_lon, point_lat])
            for year in years:
                record = {
                    "stack": result.stack,
                    "point_id": point_id,
                    "lon": point_lon,
                    "lat": point_lat,
                    "year": year,
                }
                try:
                    collection = (
                        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
                        .filterBounds(point)
                        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
                    )
                    count = int(collection.size().getInfo())
                    if count == 0:
                        raise RuntimeError("No Dynamic World observations returned")

                    mean_probs = collection.select(DW_CLASSES).mean()
                    label_mode = collection.select("label").mode()
                    combined = mean_probs.addBands(label_mode.rename("label_mode"))
                    sample = combined.sample(point, scale=10, numPixels=1).first().getInfo()
                    props = sample.get("properties", {}) if sample else {}
                    label_code = props.get("label_mode")
                    probs = {klass: props.get(klass) for klass in DW_CLASSES}
                    top_prob_class = max(
                        (klass for klass in DW_CLASSES if probs.get(klass) is not None),
                        key=lambda klass: probs[klass],
                        default=None,
                    )
                    record.update(
                        ok=label_code is not None,
                        observation_count=count,
                        label_code=label_code,
                        label=DW_LABELS.get(int(label_code), f"label {label_code}") if label_code is not None else None,
                        top_probability_class=top_prob_class,
                        top_probability=probs.get(top_prob_class) if top_prob_class else None,
                        resolution_m=10,
                        **{f"prob_{klass}": probs.get(klass) for klass in DW_CLASSES},
                    )
                except Exception as exc:
                    record.update(ok=False, error=str(exc))
                    result.errors.append(f"point {point_id} year {year}: {exc}")
                result.records.append(record)
        result.status = "ok" if result.successful_records else "failed"
    finally:
        result.elapsed_seconds = time.perf_counter() - started
    return result


def make_stress_points(lon: float, lat: float, stress_n: int, spacing_deg: float) -> list[tuple[float, float]]:
    if stress_n <= 1:
        return [(lon, lat)]
    side = math.ceil(math.sqrt(stress_n))
    center = (side - 1) / 2
    points = []
    for row in range(side):
        for col in range(side):
            points.append((lon + (col - center) * spacing_deg, lat + (row - center) * spacing_deg))
            if len(points) >= stress_n:
                return points
    return points


def stack_score(result: StackResult) -> dict[str, Any]:
    # Semi-quantitative scores tailored to this project.
    if result.stack == "dea_landcover":
        descriptive = 4
        implementation = 5
        scalability = 5
        stability_note = "annual categorical labels, public COGs, no auth"
    elif result.stack == "dea_fractional_cover_percentiles":
        descriptive = 4
        implementation = 3
        scalability = 4
        stability_note = "annual continuous vegetation/bare-soil values, STAC discovery required"
    elif result.stack == "dynamic_world":
        descriptive = 5
        implementation = 2
        scalability = 3
        stability_note = "10 m classes/probabilities, but Earth Engine auth/API required"
    else:
        descriptive = implementation = scalability = 0
        stability_note = ""

    success = result.success_rate
    runtime = result.elapsed_seconds or 0
    runtime_score = 5 if runtime < 15 else 4 if runtime < 60 else 3 if runtime < 180 else 2
    reliability = round(5 * success, 2)
    overall = round((reliability * 0.35) + (implementation * 0.2) + (descriptive * 0.2) + (scalability * 0.2) + (runtime_score * 0.05), 2)

    return {
        "stack": result.stack,
        "status": result.status,
        "attempted_records": result.attempted_records,
        "successful_records": result.successful_records,
        "success_rate": round(success, 3),
        "elapsed_seconds": round(runtime, 3),
        "reliability_score_0_5": reliability,
        "implementation_score_0_5": implementation,
        "descriptive_score_0_5": descriptive,
        "scalability_score_0_5": scalability,
        "runtime_score_0_5": runtime_score,
        "overall_score_0_5": overall,
        "note": stability_note,
        "errors": " | ".join(result.errors[:3]),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--years", default="2017:2024", help="Year range as start:end or comma list.")
    parser.add_argument("--stress-n", type=int, default=1, help="Number of nearby points to test.")
    parser.add_argument("--spacing-deg", type=float, default=0.002, help="Grid spacing for stress points in degrees.")
    parser.add_argument("--output-dir", default="external_stack_benchmark_outputs")
    parser.add_argument("--skip-dynamic-world", action="store_true")
    args = parser.parse_args()

    years = parse_years(args.years)
    output_dir = Path(args.output_dir)
    stress_points = make_stress_points(args.lon, args.lat, args.stress_n, args.spacing_deg)

    print("Benchmark coordinate/time setup")
    print(f"- base lon/lat: {args.lon}, {args.lat}")
    print(f"- years: {years[0]}-{years[-1]}")
    print(f"- stress points: {len(stress_points)}")
    print(f"- output dir: {output_dir.resolve()}")

    results = [
        run_dea_landcover(args.lon, args.lat, years, stress_points),
        run_dea_fractional_cover(args.lon, args.lat, years, stress_points),
    ]
    if not args.skip_dynamic_world:
        results.append(run_dynamic_world(args.lon, args.lat, years, stress_points))

    detail_rows = []
    for result in results:
        detail_rows.extend(result.records)

    score_rows = [stack_score(result) for result in results]
    score_rows = sorted(score_rows, key=lambda row: row["overall_score_0_5"], reverse=True)

    write_csv(output_dir / "external_stack_benchmark_records.csv", detail_rows)
    write_csv(output_dir / "external_stack_benchmark_scorecard.csv", score_rows)
    (output_dir / "external_stack_benchmark_raw.json").write_text(
        json.dumps(
            {
                "input": {
                    "lon": args.lon,
                    "lat": args.lat,
                    "years": years,
                    "stress_points": stress_points,
                },
                "scorecard": score_rows,
                "results": [
                    {
                        "stack": result.stack,
                        "status": result.status,
                        "elapsed_seconds": result.elapsed_seconds,
                        "records": result.records,
                        "errors": result.errors,
                        "notes": result.notes,
                    }
                    for result in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nScorecard")
    for row in score_rows:
        print(
            f"- {row['stack']}: overall={row['overall_score_0_5']} "
            f"success={row['successful_records']}/{row['attempted_records']} "
            f"elapsed={row['elapsed_seconds']}s status={row['status']}"
        )
        if row.get("errors"):
            print(f"  errors: {row['errors']}")

    print("\nOutputs")
    print(f"- {output_dir / 'external_stack_benchmark_records.csv'}")
    print(f"- {output_dir / 'external_stack_benchmark_scorecard.csv'}")
    print(f"- {output_dir / 'external_stack_benchmark_raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
