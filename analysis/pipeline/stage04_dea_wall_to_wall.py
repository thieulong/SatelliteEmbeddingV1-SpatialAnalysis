#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window

from stage03_dea_enrichment import (
    DEA_RASTER_ENV_OPTIONS,
    LEVEL3_LABELS,
    LEVEL4_LABELS,
    YEARS,
)


DEFAULT_PROJECT_FOLDER = "data/raw/embedding_metrics"
DEFAULT_OUTPUT_DIR = "data/processed/dea_wall_to_wall"
DEFAULT_THRESHOLDS = "data/processed/sampling/tables/phase2_thresholds.csv"
DEA_LANDCOVER_PRODUCT = "ga_ls_landcover_class_cyear_3"
DEA_LANDCOVER_VERSION = "2-0-0"
NODATA_CODE = 255

CATEGORY_ORDER = [
    "endpoint_hotspot",
    "persistent_ge2",
    "persistent_ge3",
    "high_variance",
    "positive_slope",
    "negative_slope",
    "sudden_candidate",
    "temporary_or_recovery_candidate",
    "stable_control",
]


def dea_cog_url(year: int, band: str) -> str:
    return (
        "https://data.dea.ga.gov.au/derivative/"
        f"{DEA_LANDCOVER_PRODUCT}/{DEA_LANDCOVER_VERSION}/continental_mosaics/"
        f"{year}--P1Y/{DEA_LANDCOVER_PRODUCT}_mosaic_{year}--P1Y_{band}.tif"
    )


def compact_level3_label(code: int) -> str:
    label = LEVEL3_LABELS.get(int(code), f"Unknown code {int(code)}")
    compact = (
        label.replace(" Terrestrial Vegetation", "")
        .replace("Natural ", "natural_")
        .replace("Cultivated ", "cultivated_")
        .replace("Artificial Surface", "artificial_surface")
        .replace("Natural Bare Surface", "natural_bare_surface")
        .replace("Natural Aquatic Vegetation", "natural_aquatic_vegetation")
        .replace("Water", "water")
        .replace(" ", "_")
        .lower()
    )
    return compact


def label_for(code, labels: dict[int, str]) -> str:
    if pd.isna(code):
        return "Missing"
    return labels.get(int(code), f"Unknown code {int(code)}")


def normalize_name(path: Path) -> str:
    return path.name.lower().replace("-", "_")


def find_one_tif(folder: Path, include: list[str], exclude: list[str] | None = None) -> Path | None:
    exclude = exclude or []
    matches = []
    for path in folder.glob("*.tif*"):
        name = normalize_name(path)
        if all(token in name for token in include) and not any(token in name for token in exclude):
            matches.append(path)
    return sorted(matches, key=lambda p: p.name.lower())[0] if matches else None


def discover_rasters(project_folder: Path) -> tuple[dict[str, Path | None], list[str]]:
    specs = {
        "endpoint_change": (["endpoint", "change", "2017", "2024"], ["hotspot"]),
        "endpoint_hotspots": (["endpoint", "hotspot", "2017", "2024"], []),
        "persistence_count": (["persistence", "count"], []),
        "variance_annual_change": (["variance", "annual", "change"], []),
        "slope_annual_change": (["slope", "annual", "change"], []),
        "first_hotspot_year": (["first", "hotspot", "year"], []),
        "max_change_year": (["max", "change", "year"], ["annual"]),
    }
    paths: dict[str, Path | None] = {}
    warnings = []
    for label, (include, exclude) in specs.items():
        path = find_one_tif(project_folder, include, exclude)
        paths[label] = path
        if path is None:
            warnings.append(f"Missing expected raster for {label}")
    return paths, warnings


def load_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        handover_reference = (
            Path(__file__).resolve().parents[1]
            / "reference_outputs"
            / "phase2"
            / "phase2_thresholds.csv"
        )
        if handover_reference.exists():
            path = handover_reference
    df = pd.read_csv(path)
    row = df.iloc[0].to_dict()
    required = [
        "endpoint_p95",
        "endpoint_p25",
        "variance_p95",
        "variance_p25",
        "slope_p95",
        "slope_p05",
        "abs_slope_p25",
    ]
    missing = [col for col in required if col not in row or pd.isna(row[col])]
    if missing:
        raise ValueError(f"Threshold file is missing required columns: {missing}")
    return {col: float(row[col]) for col in required}


def windows_for_dataset(width: int, height: int, window_size: int):
    idx = 0
    for row_off in range(0, height, window_size):
        for col_off in range(0, width, window_size):
            yield idx, Window(
                col_off=col_off,
                row_off=row_off,
                width=min(window_size, width - col_off),
                height=min(window_size, height - row_off),
            )
            idx += 1


def read_float(src, window: Window) -> tuple[np.ndarray, np.ndarray]:
    arr = src.read(1, window=window, masked=True).astype("float64")
    data = arr.filled(np.nan)
    valid = ~np.ma.getmaskarray(arr) & np.isfinite(data)
    return data, valid


def read_boolish(src, window: Window) -> np.ndarray:
    arr = src.read(1, window=window, masked=True)
    data = arr.filled(0)
    return data == 1


def read_dea_stack(vrts: dict[int, WarpedVRT], window: Window) -> np.ndarray:
    arrays = []
    for year in YEARS:
        arr = vrts[year].read(
            1,
            window=window,
            masked=True,
            out_dtype="uint16",
        )
        data = arr.filled(NODATA_CODE).astype("uint16", copy=False)
        arrays.append(data)
    return np.stack(arrays, axis=0)


def build_category_masks(
    endpoint_change: np.ndarray,
    endpoint_hotspots: np.ndarray,
    persistence_count: np.ndarray,
    variance_annual_change: np.ndarray,
    slope_annual_change: np.ndarray,
    base_valid: np.ndarray,
    thresholds: dict[str, float],
) -> dict[str, np.ndarray]:
    finite_common = (
        base_valid
        & np.isfinite(endpoint_change)
        & np.isfinite(persistence_count)
        & np.isfinite(variance_annual_change)
        & np.isfinite(slope_annual_change)
    )
    return {
        "endpoint_hotspot": finite_common & endpoint_hotspots,
        "persistent_ge2": finite_common & (persistence_count >= 2),
        "persistent_ge3": finite_common & (persistence_count >= 3),
        "high_variance": finite_common & (variance_annual_change >= thresholds["variance_p95"]),
        "positive_slope": finite_common & (slope_annual_change >= thresholds["slope_p95"]),
        "negative_slope": finite_common & (slope_annual_change <= thresholds["slope_p05"]),
        "sudden_candidate": finite_common
        & (endpoint_change >= thresholds["endpoint_p95"])
        & (persistence_count <= 1),
        "temporary_or_recovery_candidate": finite_common
        & (endpoint_change < thresholds["endpoint_p95"])
        & (variance_annual_change >= thresholds["variance_p95"]),
        "stable_control": finite_common
        & (endpoint_change <= thresholds["endpoint_p25"])
        & (persistence_count == 0)
        & (variance_annual_change <= thresholds["variance_p25"])
        & (np.abs(slope_annual_change) <= thresholds["abs_slope_p25"]),
    }


def first_change_year_array(stack: np.ndarray, complete: np.ndarray) -> np.ndarray:
    out = np.zeros(stack.shape[1:], dtype="uint16")
    for idx, year in enumerate(YEARS[1:], start=1):
        changed_here = complete & (out == 0) & (stack[idx - 1] != stack[idx])
        out[changed_here] = year
    return out


def sequence_type_array(stack: np.ndarray, complete: np.ndarray) -> np.ndarray:
    start = stack[0]
    end = stack[-1]
    stable = complete & np.all(stack == start[None, :, :], axis=0)
    changed = complete & ~stable
    water_or_bare = np.any(np.isin(stack, [124, 216, 220]), axis=0)

    out = np.full(stack.shape[1:], "missing_sequence", dtype=object)
    for code in np.unique(start[stable]):
        out[stable & (start == code)] = f"stable_{compact_level3_label(int(code))}"
    out[changed & (start == end)] = "temporary_or_return_to_start"
    out[changed & (start != 215) & (end == 215)] = "transition_to_artificial_surface"
    out[changed & (start == 215) & (end != 215)] = "transition_from_artificial_surface"
    out[changed & (start == 112) & (end == 111)] = "natural_to_cultivated_vegetation"
    out[changed & (start == 111) & (end == 112)] = "cultivated_to_natural_vegetation"
    remaining = changed & (out == "missing_sequence")
    out[remaining & water_or_bare] = "water_aquatic_or_bare_involved"
    out[remaining & ~water_or_bare] = "other_level3_change"
    return out


def count_transitions(stack: np.ndarray, mask: np.ndarray, labels: dict[int, str]) -> list[dict]:
    selected = mask & np.all(stack != NODATA_CODE, axis=0)
    if not selected.any():
        return []
    pairs = np.stack([stack[0][selected], stack[-1][selected]], axis=1)
    unique_pairs, counts = np.unique(pairs, axis=0, return_counts=True)
    rows = []
    for (start, end), count in zip(unique_pairs, counts):
        rows.append(
            {
                "start_code": int(start),
                "end_code": int(end),
                "start_label": label_for(start, labels),
                "end_label": label_for(end, labels),
                "transition": f"{label_for(start, labels)} -> {label_for(end, labels)}",
                "pixel_count": int(count),
            }
        )
    return rows


def count_values(values: np.ndarray, mask: np.ndarray, column: str) -> list[dict]:
    if not mask.any():
        return []
    selected = values[mask]
    unique_values, counts = np.unique(selected, return_counts=True)
    return [{column: value, "pixel_count": int(count)} for value, count in zip(unique_values, counts)]


def safe_match_pm1(first_change: np.ndarray, reference_year: np.ndarray, mask: np.ndarray) -> int:
    valid = mask & (first_change > 0) & np.isfinite(reference_year) & (reference_year > 0)
    if not valid.any():
        return 0
    return int((np.abs(first_change[valid].astype("int32") - reference_year[valid].astype("int32")) <= 1).sum())


def process_window(window_idx: int, window: Window, datasets: dict, dea_vrts: dict, thresholds: dict) -> dict[str, pd.DataFrame]:
    endpoint_change, base_valid = read_float(datasets["endpoint_change"], window)
    persistence_count, persistence_valid = read_float(datasets["persistence_count"], window)
    variance_annual_change, variance_valid = read_float(datasets["variance_annual_change"], window)
    slope_annual_change, slope_valid = read_float(datasets["slope_annual_change"], window)
    first_hotspot_year, _ = read_float(datasets["first_hotspot_year"], window)
    max_change_year, _ = read_float(datasets["max_change_year"], window)
    endpoint_hotspots = read_boolish(datasets["endpoint_hotspots"], window)
    base_valid = base_valid & persistence_valid & variance_valid & slope_valid

    category_masks = build_category_masks(
        endpoint_change,
        endpoint_hotspots,
        persistence_count,
        variance_annual_change,
        slope_annual_change,
        base_valid,
        thresholds,
    )

    l3_stack = read_dea_stack(dea_vrts["level3"], window)
    l4_stack = read_dea_stack(dea_vrts["level4"], window)
    l3_complete = np.all(l3_stack != NODATA_CODE, axis=0)
    l4_complete = np.all(l4_stack != NODATA_CODE, axis=0)
    l3_changed = l3_complete & (np.max(l3_stack, axis=0) != np.min(l3_stack, axis=0))
    l4_changed = l4_complete & (np.max(l4_stack, axis=0) != np.min(l4_stack, axis=0))
    l3_first_change = first_change_year_array(l3_stack, l3_complete)
    sequence_types = sequence_type_array(l3_stack, l3_complete)

    summary_rows = []
    level3_transition_rows = []
    level4_transition_rows = []
    sequence_type_rows = []
    timing_rows = []

    for category in CATEGORY_ORDER:
        mask = category_masks[category]
        category_pixels = int(mask.sum())
        if category_pixels == 0:
            summary_rows.append(
                {
                    "window_idx": window_idx,
                    "category": category,
                    "pixel_count": 0,
                    "level3_complete_pixels": 0,
                    "level4_complete_pixels": 0,
                    "level3_changed_pixels": 0,
                    "level4_changed_pixels": 0,
                    "match_max_change_year_pm1": 0,
                    "match_first_hotspot_year_pm1": 0,
                }
            )
            continue

        level3_complete_pixels = int((mask & l3_complete).sum())
        level4_complete_pixels = int((mask & l4_complete).sum())
        level3_changed_pixels = int((mask & l3_changed).sum())
        level4_changed_pixels = int((mask & l4_changed).sum())
        match_max = safe_match_pm1(l3_first_change, max_change_year, mask & l3_changed)
        match_hotspot = safe_match_pm1(l3_first_change, first_hotspot_year, mask & l3_changed)

        summary_rows.append(
            {
                "window_idx": window_idx,
                "category": category,
                "pixel_count": category_pixels,
                "level3_complete_pixels": level3_complete_pixels,
                "level4_complete_pixels": level4_complete_pixels,
                "level3_changed_pixels": level3_changed_pixels,
                "level4_changed_pixels": level4_changed_pixels,
                "match_max_change_year_pm1": match_max,
                "match_first_hotspot_year_pm1": match_hotspot,
            }
        )

        for row in count_transitions(l3_stack, mask, LEVEL3_LABELS):
            row.update(window_idx=window_idx, category=category)
            level3_transition_rows.append(row)
        for row in count_transitions(l4_stack, mask, LEVEL4_LABELS):
            row.update(window_idx=window_idx, category=category)
            level4_transition_rows.append(row)
        for row in count_values(sequence_types, mask & l3_complete, "level3_sequence_type"):
            row.update(window_idx=window_idx, category=category)
            sequence_type_rows.append(row)

        del mask

    return {
        "category_summary": pd.DataFrame(summary_rows),
        "level3_transitions": pd.DataFrame(level3_transition_rows),
        "level4_transitions": pd.DataFrame(level4_transition_rows),
        "sequence_types": pd.DataFrame(sequence_type_rows),
        "timing_alignment": pd.DataFrame(timing_rows),
    }


def aggregate_csvs(paths: list[Path], group_cols: list[str]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame(columns=[*group_cols, "pixel_count"])
    frames = []
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            frames.append(pd.read_csv(path))
        except pd.errors.EmptyDataError:
            continue
    if not frames:
        return pd.DataFrame(columns=[*group_cols, "pixel_count"])
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df
    numeric_cols = [col for col in df.columns if col.endswith("_pixels") or col == "pixel_count" or col.startswith("match_")]
    return df.groupby(group_cols, dropna=False)[numeric_cols].sum().reset_index()


def finalize_outputs(output_dir: Path, checkpoint_dir: Path, pixel_area_m2: float | None, metadata: dict):
    category_df = aggregate_csvs(
        sorted(checkpoint_dir.glob("window_*_category_summary.csv")),
        ["category"],
    )
    if not category_df.empty:
        category_df["level3_changed_share"] = category_df["level3_changed_pixels"] / category_df["pixel_count"].replace(0, np.nan)
        category_df["level4_changed_share"] = category_df["level4_changed_pixels"] / category_df["pixel_count"].replace(0, np.nan)
        category_df["level3_complete_share"] = category_df["level3_complete_pixels"] / category_df["pixel_count"].replace(0, np.nan)
        category_df["match_max_change_year_pm1_share_of_l3_changed"] = (
            category_df["match_max_change_year_pm1"] / category_df["level3_changed_pixels"].replace(0, np.nan)
        )
        category_df["match_first_hotspot_year_pm1_share_of_l3_changed"] = (
            category_df["match_first_hotspot_year_pm1"] / category_df["level3_changed_pixels"].replace(0, np.nan)
        )
        if pixel_area_m2:
            category_df["area_ha"] = category_df["pixel_count"] * pixel_area_m2 / 10000.0
        category_df = category_df.sort_values("level3_changed_share", ascending=False)

    level3_df = aggregate_csvs(
        sorted(checkpoint_dir.glob("window_*_level3_transitions.csv")),
        ["category", "start_code", "end_code", "start_label", "end_label", "transition"],
    ).sort_values(["category", "pixel_count"], ascending=[True, False])
    level4_df = aggregate_csvs(
        sorted(checkpoint_dir.glob("window_*_level4_transitions.csv")),
        ["category", "start_code", "end_code", "start_label", "end_label", "transition"],
    ).sort_values(["category", "pixel_count"], ascending=[True, False])
    sequence_df = aggregate_csvs(
        sorted(checkpoint_dir.glob("window_*_sequence_types.csv")),
        ["category", "level3_sequence_type"],
    ).sort_values(["category", "pixel_count"], ascending=[True, False])
    timing_cols = [
        "category",
        "level3_changed_pixels",
        "match_max_change_year_pm1",
        "match_first_hotspot_year_pm1",
        "match_max_change_year_pm1_share_of_l3_changed",
        "match_first_hotspot_year_pm1_share_of_l3_changed",
    ]
    timing_df = category_df[[col for col in timing_cols if col in category_df.columns]].copy()

    category_df.to_csv(output_dir / "basscoast_phase5_wall_to_wall_category_summary.csv", index=False)
    level3_df.to_csv(output_dir / "basscoast_phase5_wall_to_wall_level3_transition_counts.csv", index=False)
    level4_df.to_csv(output_dir / "basscoast_phase5_wall_to_wall_level4_transition_counts.csv", index=False)
    sequence_df.to_csv(output_dir / "basscoast_phase5_wall_to_wall_sequence_type_counts.csv", index=False)
    timing_df.to_csv(output_dir / "basscoast_phase5_wall_to_wall_timing_alignment.csv", index=False)

    report_rows = [{"item": key, "value": value} for key, value in metadata.items()]
    report_rows.extend(
        [
            {"item": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
            {"item": "category_summary_csv", "value": str(output_dir / "basscoast_phase5_wall_to_wall_category_summary.csv")},
            {"item": "level3_transition_counts_csv", "value": str(output_dir / "basscoast_phase5_wall_to_wall_level3_transition_counts.csv")},
            {"item": "level4_transition_counts_csv", "value": str(output_dir / "basscoast_phase5_wall_to_wall_level4_transition_counts.csv")},
            {"item": "sequence_type_counts_csv", "value": str(output_dir / "basscoast_phase5_wall_to_wall_sequence_type_counts.csv")},
            {"item": "timing_alignment_csv", "value": str(output_dir / "basscoast_phase5_wall_to_wall_timing_alignment.csv")},
            {"item": "pixel_area_m2", "value": pixel_area_m2 if pixel_area_m2 else ""},
        ]
    )
    pd.DataFrame(report_rows).to_csv(output_dir / "basscoast_phase5_wall_to_wall_processing_report.csv", index=False)
    return category_df, level3_df, level4_df, sequence_df, timing_df


def open_dea_vrts(reference, level3_template: str | None = None, level4_template: str | None = None):
    sources: dict[str, dict[int, rasterio.io.DatasetReader]] = {"level3": {}, "level4": {}}
    vrts: dict[str, dict[int, WarpedVRT]] = {"level3": {}, "level4": {}}
    for level, template in [("level3", level3_template), ("level4", level4_template)]:
        for year in YEARS:
            url = template.format(year=year, band=level) if template else dea_cog_url(year, level)
            src = rasterio.open(url)
            sources[level][year] = src
            vrts[level][year] = WarpedVRT(
                src,
                crs=reference.crs,
                transform=reference.transform,
                width=reference.width,
                height=reference.height,
                resampling=Resampling.nearest,
                src_nodata=NODATA_CODE,
                nodata=NODATA_CODE,
            )
    return sources, vrts


def close_dea(sources, vrts):
    for level in vrts.values():
        for vrt in level.values():
            vrt.close()
    for level in sources.values():
        for src in level.values():
            src.close()


def check_alignment(datasets: dict) -> pd.DataFrame:
    ref = datasets["endpoint_change"]
    rows = []
    for label, src in datasets.items():
        rows.append(
            {
                "raster": label,
                "path": src.name,
                "crs_matches": src.crs == ref.crs,
                "transform_matches": src.transform == ref.transform,
                "width_matches": src.width == ref.width,
                "height_matches": src.height == ref.height,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
            }
        )
    return pd.DataFrame(rows)


def run_pipeline(args) -> int:
    project_folder = Path(args.project_folder)
    output_dir = Path(args.output_dir)
    checkpoint_dir = output_dir / "checkpoints"
    if args.force and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    thresholds = load_thresholds(Path(args.thresholds))
    raster_paths, warnings = discover_rasters(project_folder)
    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")
    missing = [label for label, path in raster_paths.items() if path is None]
    if missing:
        raise FileNotFoundError(f"Cannot run Phase 5 because these rasters are missing: {missing}")

    datasets = {label: rasterio.open(path) for label, path in raster_paths.items() if path is not None}
    try:
        alignment_df = check_alignment(datasets)
        alignment_df.to_csv(output_dir / "basscoast_phase5_alignment_report.csv", index=False)
        if not alignment_df[["crs_matches", "transform_matches", "width_matches", "height_matches"]].all().all():
            raise ValueError(f"Raster alignment failed. See {output_dir / 'basscoast_phase5_alignment_report.csv'}")

        ref = datasets["endpoint_change"]
        pixel_area_m2 = abs(float(ref.transform.a * ref.transform.e)) if not ref.crs.is_geographic else None
        windows = list(windows_for_dataset(ref.width, ref.height, args.window_size))
        if args.window_start and args.window_start > 0:
            windows = windows[args.window_start :]
        if args.max_windows and args.max_windows > 0:
            windows = windows[: args.max_windows]

        metadata = {
            "project_folder": str(project_folder),
            "output_dir": str(output_dir),
            "reference_raster": ref.name,
            "reference_crs": str(ref.crs),
            "reference_width": ref.width,
            "reference_height": ref.height,
            "window_size": args.window_size,
            "window_start": args.window_start,
            "windows_planned": len(windows),
            "max_windows": args.max_windows,
            "thresholds": json.dumps(thresholds, sort_keys=True),
            "dea_mode": "local_template" if args.dea_level3_template or args.dea_level4_template else "remote_dea_cog",
            "notes": "DEA 30 m labels are nearest-neighbour resampled to the embedding raster grid for category summaries.",
        }

        with rasterio.Env(**DEA_RASTER_ENV_OPTIONS):
            sources, dea_vrts = open_dea_vrts(ref, args.dea_level3_template, args.dea_level4_template)
            try:
                for position, (window_idx, window) in enumerate(windows, start=1):
                    done_marker = checkpoint_dir / f"window_{window_idx:06d}.done"
                    if args.resume and done_marker.exists():
                        print(f"Reusing checkpoint window {window_idx:06d} ({position}/{len(windows)})")
                        continue
                    print(f"Processing window {window_idx:06d} ({position}/{len(windows)})")
                    outputs = process_window(window_idx, window, datasets, dea_vrts, thresholds)
                    for name, df in outputs.items():
                        df.to_csv(checkpoint_dir / f"window_{window_idx:06d}_{name}.csv", index=False)
                    done_marker.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
            finally:
                close_dea(sources, dea_vrts)

        category_df, level3_df, level4_df, sequence_df, timing_df = finalize_outputs(output_dir, checkpoint_dir, pixel_area_m2, metadata)
        print(f"Saved Phase 5 outputs to: {output_dir}")
        print(f"Category summary: {output_dir / 'basscoast_phase5_wall_to_wall_category_summary.csv'}")
        print("\nCategory summary preview:")
        preview_cols = [
            "category",
            "pixel_count",
            "level3_changed_pixels",
            "level3_changed_share",
            "level4_changed_pixels",
            "level4_changed_share",
        ]
        print(category_df[[col for col in preview_cols if col in category_df.columns]].to_string(index=False))
        print("\nTop Level 3 transitions preview:")
        print(level3_df.head(12).to_string(index=False))
        return 0
    finally:
        for src in datasets.values():
            src.close()


def create_test_raster(path: Path, data: np.ndarray, transform, crs: str, nodata=None):
    dtype = data.dtype
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def run_self_test(base_dir: Path) -> int:
    project = base_dir / "phase5_self_test_project"
    output = base_dir / "phase5_self_test_outputs"
    if project.exists():
        shutil.rmtree(project)
    if output.exists():
        shutil.rmtree(output)
    project.mkdir(parents=True)
    dea_dir = project / "mock_dea"
    dea_dir.mkdir()

    rng = np.random.default_rng(42)
    height, width = 40, 50
    transform = from_origin(145.0, -38.0, 0.0001, 0.0001)
    crs = "EPSG:4326"
    endpoint = rng.uniform(0.05, 0.7, size=(height, width)).astype("float32")
    persistence = rng.integers(0, 5, size=(height, width)).astype("int16")
    variance = rng.uniform(0.0001, 0.02, size=(height, width)).astype("float32")
    slope = rng.uniform(-0.03, 0.03, size=(height, width)).astype("float32")
    hotspots = (endpoint >= 0.445133).astype("uint8")
    first_year = np.where(persistence > 0, rng.integers(2018, 2025, size=(height, width)), 0).astype("int16")
    max_year = rng.integers(2018, 2025, size=(height, width)).astype("int16")

    create_test_raster(project / "basscoast_endpoint_change_2017_2024.tif", endpoint, transform, crs, -9999)
    create_test_raster(project / "basscoast_endpoint_hotspots_2017_2024.tif", hotspots, transform, crs, 0)
    create_test_raster(project / "basscoast_persistence_count.tif", persistence, transform, crs, -9999)
    create_test_raster(project / "basscoast_variance_annual_change.tif", variance, transform, crs, -9999)
    create_test_raster(project / "basscoast_slope_annual_change.tif", slope, transform, crs, -9999)
    create_test_raster(project / "basscoast_first_hotspot_year.tif", first_year, transform, crs, 0)
    create_test_raster(project / "basscoast_max_change_year.tif", max_year, transform, crs, 0)

    for year in YEARS:
        l3 = np.full((height, width), 112, dtype="uint16")
        l4 = np.full((height, width), 20, dtype="uint16")
        if year >= 2020:
            l3[:, width // 2 :] = 111
            l4[:, width // 2 :] = 3
        if year >= 2022:
            l3[height // 2 :, : width // 4] = 215
            l4[height // 2 :, : width // 4] = 93
        create_test_raster(dea_dir / f"mock_dea_{year}_level3.tif", l3, transform, crs, NODATA_CODE)
        create_test_raster(dea_dir / f"mock_dea_{year}_level4.tif", l4, transform, crs, NODATA_CODE)

    args = argparse.Namespace(
        project_folder=str(project),
        output_dir=str(output),
        thresholds=DEFAULT_THRESHOLDS,
        window_size=20,
        window_start=0,
        max_windows=2,
        resume=False,
        force=True,
        dea_level3_template=str(dea_dir / "mock_dea_{year}_level3.tif"),
        dea_level4_template=str(dea_dir / "mock_dea_{year}_level4.tif"),
    )
    code = run_pipeline(args)
    required = [
        output / "basscoast_phase5_wall_to_wall_category_summary.csv",
        output / "basscoast_phase5_wall_to_wall_level3_transition_counts.csv",
        output / "basscoast_phase5_wall_to_wall_level4_transition_counts.csv",
        output / "basscoast_phase5_wall_to_wall_sequence_type_counts.csv",
        output / "basscoast_phase5_wall_to_wall_processing_report.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Self-test did not create expected outputs: {missing}")
    print(f"\nSelf-test completed successfully in {output}")
    return code


def parse_args():
    parser = argparse.ArgumentParser(description="Phase 5 wall-to-wall DEA summary for Bass Coast embedding rasters.")
    parser.add_argument("--project-folder", default=DEFAULT_PROJECT_FOLDER)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--window-size", type=int, default=512)
    parser.add_argument("--window-start", type=int, default=0, help="Skip this many windows before processing; useful for targeted tests.")
    parser.add_argument("--max-windows", type=int, default=0, help="Use a small value for testing; 0 means all windows.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed window checkpoints.")
    parser.add_argument("--force", action="store_true", help="Delete the output directory before running.")
    parser.add_argument("--dea-level3-template", default=None, help="Optional local template containing {year}, used for tests.")
    parser.add_argument("--dea-level4-template", default=None, help="Optional local template containing {year}, used for tests.")
    parser.add_argument("--self-test", action="store_true", help="Run a synthetic local test that does not require project rasters or network.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.self_test:
        return run_self_test(Path("/tmp"))
    return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
