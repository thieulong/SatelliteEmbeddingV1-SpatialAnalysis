#!/usr/bin/env python3
"""Build browser-ready AusHabitat assets from map-grid and region-context outputs."""

from __future__ import annotations

import gzip
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image


APP_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = APP_ROOT
PHASE9_DIR = PROJECT_ROOT / "data" / "processed" / "map_grid"
PHASE10_DIR = PROJECT_ROOT / "data" / "processed" / "region_context"
DATA_DIR = APP_ROOT / "public" / "data"
DETAIL_DIR = DATA_DIR / "details"
SHARD_SIZE = 1_000

YEARS = list(range(2017, 2025))
INTERVALS = [f"{year}_{year + 1}" for year in YEARS[:-1]]


def clean_value(value):
    if value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else round(float(value), 7)
    return value


def clean_record(record):
    return {key: clean_value(value) for key, value in record.items()}


def round_coordinates(value):
    if isinstance(value, list):
        return [round_coordinates(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def compact_detail(row: dict, annual_rows: list[dict]) -> dict:
    keep = [
        "feature_id", "feature_type", "lon", "lat", "area_m2",
        "endpoint_change_mean", "endpoint_change_max", "endpoint_hotspot_fraction",
        "variance_mean", "slope_mean", "cumulative_change_mean", "max_annual_change_mean",
        "mean_hotspot_intervals", "maximum_hotspot_intervals", "repeat_change_coverage",
        "active_interval_count", "strongest_change_interval", "region_behaviour",
        "overall_activity", "year_to_year_pattern", "change_intensity_trend",
        "dea_level3_changed", "dea_level4_changed", "dea_level3_first_change_year",
        "dea_level4_first_change_year", "ndvi_start", "ndvi_end", "ndvi_endpoint_change",
        "ndvi_slope", "ndvi_variance", "ndvi_largest_change_interval",
        "ndvi_largest_signed_change", "ndvi_direction", "ndvi_change_signal",
        "dea_transition_signal", "embedding_change_signal", "evidence_source_count",
        "evidence_pattern",
    ]
    for interval in INTERVALS:
        keep.extend([f"annual_change_{interval}", f"annual_hotspot_{interval}_fraction"])
    detail = {key: clean_value(row.get(key)) for key in keep}
    detail["annual_context"] = {
        str(int(item["year"])): {
            "dea_level3": clean_value(item.get("dea_level3_label")),
            "dea_level3_share": clean_value(item.get("dea_level3_share")),
            "dea_level3_secondary": clean_value(item.get("dea_level3_secondary_label")),
            "dea_level3_secondary_share": clean_value(item.get("dea_level3_secondary_share")),
            "dea_level4": clean_value(item.get("dea_level4_label")),
            "dea_level4_share": clean_value(item.get("dea_level4_share")),
            "dea_level4_secondary": clean_value(item.get("dea_level4_secondary_label")),
            "dea_level4_secondary_share": clean_value(item.get("dea_level4_secondary_share")),
            "dea_level3_changed_area_share": clean_value(item.get("dea_level3_changed_area_share")),
            "ndvi_mean": clean_value(item.get("ndvi_mean")),
            "ndvi_median": clean_value(item.get("ndvi_median")),
            "ndvi_previous_year_change": clean_value(item.get("ndvi_previous_year_change")),
            "ndvi_change_event": clean_value(item.get("ndvi_change_event")),
            "clear_observations": clean_value(item.get("ndvi_mean_clear_observations")),
        }
        for item in annual_rows
    }
    return detail


def build_surface_overlays(raster_path, hotspot_output_path, coldspot_output_path):
    with rasterio.open(raster_path) as src:
        state = src.read(1)
        bounds = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]

    hotspot_rgba = np.zeros((*state.shape, 4), dtype=np.uint8)
    hotspot_palette = {
        3: (238, 145, 45, 105),
        4: (190, 45, 66, 170),
    }
    for code, color in hotspot_palette.items():
        hotspot_rgba[state == code] = color
    Image.fromarray(hotspot_rgba, "RGBA").save(hotspot_output_path, optimize=True)

    coldspot_rgba = np.zeros((*state.shape, 4), dtype=np.uint8)
    coldspot_rgba[state == 1] = (35, 111, 168, 150)
    Image.fromarray(coldspot_rgba, "RGBA").save(coldspot_output_path, optimize=True)
    return bounds


def build_annual_overlay(raster_path, output_path):
    with rasterio.open(raster_path) as src:
        values = src.read(1, masked=True).filled(0).astype(np.float32)
    values = np.clip(values, 0, 1)
    visible = values >= 0.05
    alpha = np.zeros(values.shape, dtype=np.uint8)
    alpha[visible] = np.clip(35 + np.sqrt(values[visible]) * 185, 0, 220).astype(np.uint8)
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    rgba[..., 0] = 220
    rgba[..., 1] = (174 - 105 * values).astype(np.uint8)
    rgba[..., 2] = (55 - 30 * values).astype(np.uint8)
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").save(output_path, optimize=True)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DETAIL_DIR.exists():
        shutil.rmtree(DETAIL_DIR)
    DETAIL_DIR.mkdir(parents=True)

    summary = pd.read_csv(PHASE10_DIR / "basscoast_phase10_region_summary.csv")
    annual = pd.read_csv(PHASE10_DIR / "basscoast_phase10_region_year_context.csv")
    annual_groups = {
        str(feature_id): group.sort_values("year").to_dict("records")
        for feature_id, group in annual.groupby("feature_id", sort=False)
    }
    summary_by_id = {str(row["feature_id"]): row for row in summary.to_dict("records")}

    shards: dict[int, dict[str, dict]] = {}
    for position, row in enumerate(summary.to_dict("records")):
        feature_id = str(row["feature_id"])
        shard = position // SHARD_SIZE
        shards.setdefault(shard, {})[feature_id] = compact_detail(
            row, annual_groups.get(feature_id, [])
        )
    for shard, records in shards.items():
        (DETAIL_DIR / f"regions_{shard:03d}.json").write_text(
            json.dumps(records, separators=(",", ":")), encoding="utf-8"
        )

    with gzip.open(PHASE9_DIR / "basscoast_phase9_features.geojson.gz", "rt") as src:
        source_geojson = json.load(src)

    map_features = []
    for feature in source_geojson["features"]:
        props = feature["properties"]
        feature_id = str(props["feature_id"])
        context = summary_by_id[feature_id]
        map_props = {
            "feature_id": feature_id,
            "feature_type": context["feature_type"],
            "behaviour": context["region_behaviour"],
            "area_ha": round(float(context["area_m2"]) / 10_000, 3),
            "lon": round(float(context["lon"]), 6),
            "lat": round(float(context["lat"]), 6),
            "endpoint_change": round(float(context["endpoint_change_mean"]), 5),
            "repeat_coverage": round(float(context["repeat_change_coverage"]), 4),
            "active_intervals": int(context["active_interval_count"]),
            "overall_activity": context["overall_activity"],
            "year_pattern": context["year_to_year_pattern"],
            "trend": context["change_intensity_trend"],
            "embedding_signal": bool(context["embedding_change_signal"]),
            "dea_signal": bool(context["dea_transition_signal"]),
            "ndvi_signal": bool(context["ndvi_change_signal"]),
            "ndvi_direction": context["ndvi_direction"],
            "evidence_count": int(context["evidence_source_count"]),
        }
        for interval in INTERVALS:
            map_props[f"change_{interval}"] = round(float(props[f"annual_change_{interval}"]), 5)
            map_props[f"hotspot_{interval}"] = round(
                float(props[f"annual_hotspot_{interval}_fraction"]), 4
            )
        map_features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "properties": map_props,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": round_coordinates(feature["geometry"]["coordinates"]),
                },
            }
        )

    feature_collection = {"type": "FeatureCollection", "features": map_features}
    (DATA_DIR / "features.geojson").write_text(
        json.dumps(feature_collection, separators=(",", ":")), encoding="utf-8"
    )
    legacy_details = DATA_DIR / "feature_details.json"
    if legacy_details.exists():
        legacy_details.unlink()

    bounds = build_surface_overlays(
        PHASE9_DIR / "rasters" / "basscoast_change_state_30m.tif",
        DATA_DIR / "change_hotspots_overlay.png",
        DATA_DIR / "change_coldspots_overlay.png",
    )
    annual_overlays = {}
    for interval in INTERVALS:
        filename = f"annual_hotspot_{interval}.png"
        build_annual_overlay(
            PHASE9_DIR / "rasters" / f"basscoast_annual_hotspot_{interval}_fraction_30m.tif",
            DATA_DIR / filename,
        )
        annual_overlays[interval] = f"data/{filename}"

    state_summary = pd.read_csv(PHASE9_DIR / "basscoast_phase9_change_state_summary.csv")
    manifest = json.loads((PHASE10_DIR / "basscoast_phase10_manifest.json").read_text())
    metadata = {
        "title": "AusHabitat",
        "subtitle": "Bass Coast landscape change · 2017–2024",
        "years": YEARS,
        "intervals": INTERVALS,
        "bounds": bounds,
        "feature_count": int(len(summary)),
        "hotspot_feature_count": int((summary["feature_type"] == "hotspot_patch").sum()),
        "coldspot_feature_count": int((summary["feature_type"] == "coldspot_patch").sum()),
        "context_feature_count": int(len(summary)),
        "region_year_rows": int(len(annual)),
        "detail_shard_size": SHARD_SIZE,
        "detail_shard_count": len(shards),
        "hotspot_surface_overlay": "data/change_hotspots_overlay.png",
        "coldspot_surface_overlay": "data/change_coldspots_overlay.png",
        "annual_overlays": annual_overlays,
        "state_summary": [clean_record(row) for row in state_summary.to_dict("records")],
        "behaviour_counts": {
            key: int(value) for key, value in summary["region_behaviour"].value_counts().items()
        },
        "evidence_counts": {
            "embedding": int(summary["embedding_change_signal"].sum()),
            "dea": int(summary["dea_transition_signal"].sum()),
            "ndvi": int(summary["ndvi_change_signal"].sum()),
            "all_three": int((summary["evidence_source_count"] == 3).sum()),
        },
        "thresholds": {
            "endpoint_p95": 0.445133,
            "annual_hotspot": 0.45,
            "variance_p95": 0.0084274,
            "ndvi_region_event": manifest["ndvi_event_threshold"],
        },
        "coverage_note": "Every interaction region has an annual context record for 2017-2024. One small region has an unknown DEA Level 4 class in 2021; DEA Level 3 and NDVI remain available.",
        "pixel_context_note": manifest["pixel_history_note"],
    }
    (DATA_DIR / "app_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(f"Prepared {len(summary):,} interactive AusHabitat regions")
    print(f"Attached {len(annual):,} annual DEA/NDVI region-year records")
    print(f"Wrote {len(shards)} lazy-loaded detail shards")
    print(f"Output: {DATA_DIR}")


if __name__ == "__main__":
    main()
