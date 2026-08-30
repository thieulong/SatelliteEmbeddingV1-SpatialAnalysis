#!/usr/bin/env python3
"""Prepare Bass Coast embedding, DEA and NDVI data for a future map application."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import shutil
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes, sieve
from rasterio.transform import rowcol
from rasterio.warp import reproject, transform as transform_coords
from rasterio.windows import Window, transform as window_transform


YEARS = list(range(2017, 2025))
INTERVALS = [(year, year + 1) for year in YEARS[:-1]]
DEFAULT_PROJECT = Path("data/raw/embedding_metrics")
DEFAULT_OUTPUT = Path("data/processed/map_grid")
DEFAULT_THRESHOLDS = Path(
    "data/processed/sampling/tables/phase2_thresholds.csv"
)
DEFAULT_REVIEW_POINTS = Path(
    "data/processed/sampling/basscoast_phase2b_review_points.csv"
)
DEFAULT_PHASE8_INTERVALS = Path(
    "data/processed/ndvi_pilot/basscoast_phase8_embedding_ndvi_intervals.csv"
)
DEFAULT_PHASE8_METADATA = Path(
    "data/processed/ndvi_pilot/basscoast_phase8_run_metadata.csv"
)

STATE_LABELS = {
    0: "no_data",
    1: "cold",
    2: "background",
    3: "episodic_hotspot",
    4: "persistent_hotspot",
}
STATE_COLOURS = {
    0: "#00000000",
    1: "#2f6da8",
    2: "#b9b9b2",
    3: "#e18a27",
    4: "#b8322a",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-folder", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--review-points", type=Path, default=DEFAULT_REVIEW_POINTS)
    parser.add_argument("--phase8-intervals", type=Path, default=DEFAULT_PHASE8_INTERVALS)
    parser.add_argument("--phase8-metadata", type=Path, default=DEFAULT_PHASE8_METADATA)
    parser.add_argument("--aggregation-factor", type=int, default=3)
    parser.add_argument("--min-hot-patch-cells", type=int, default=9)
    parser.add_argument("--min-cold-patch-cells", type=int, default=100)
    parser.add_argument("--test-enrichment-features", type=int, default=90)
    parser.add_argument("--skip-external", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def required_rasters(folder: Path) -> dict[str, Path]:
    paths = {
        "endpoint_change": folder / "basscoast_endpoint_change_2017_2024.tif",
        "endpoint_hotspot": folder / "basscoast_endpoint_hotspots_2017_2024.tif",
        "persistence": folder / "basscoast_persistence_count.tif",
        "variance": folder / "basscoast_variance_annual_change.tif",
        "slope": folder / "basscoast_slope_annual_change.tif",
        "cumulative": folder / "basscoast_cumulative_change.tif",
        "max_annual": folder / "basscoast_max_annual_change.tif",
    }
    for start, end in INTERVALS:
        paths[f"annual_change_{start}_{end}"] = (
            folder / f"basscoast_annual_change_{start}_{end}.tif"
        )
        paths[f"annual_hotspot_{start}_{end}"] = (
            folder / f"basscoast_annual_hotspot_{start}_{end}.tif"
        )
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required rasters: {missing}")
    return paths


def load_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"Threshold table not found: {path}")
    row = pd.read_csv(path).iloc[0]
    return {
        "endpoint_p95": float(row["endpoint_p95"]),
        "endpoint_p25": float(row["endpoint_p25"]),
        "variance_p95": float(row["variance_p95"]),
        "variance_p25": float(row["variance_p25"]),
        "slope_p95": float(row["slope_p95"]),
        "slope_p05": float(row["slope_p05"]),
        "abs_slope_p25": float(row["abs_slope_p25"]),
    }


def verify_alignment(paths: dict[str, Path]) -> tuple[pd.DataFrame, dict]:
    rows = []
    reference = None
    for label, path in paths.items():
        with rasterio.open(path) as src:
            metadata = {
                "crs": str(src.crs),
                "transform": tuple(src.transform),
                "width": src.width,
                "height": src.height,
                "bounds": tuple(src.bounds),
            }
            if reference is None:
                reference = metadata
            aligned = all(
                metadata[key] == reference[key]
                for key in ["crs", "transform", "width", "height", "bounds"]
            )
            rows.append(
                {
                    "label": label,
                    "file": path.name,
                    "width": src.width,
                    "height": src.height,
                    "crs": str(src.crs),
                    "pixel_width": src.res[0],
                    "pixel_height": src.res[1],
                    "aligned": aligned,
                }
            )
    report = pd.DataFrame(rows)
    if not report["aligned"].all():
        raise ValueError("Input raster alignment failed.")
    return report, reference


def pearson(x: pd.Series, y: pd.Series) -> float:
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) < 3 or valid["x"].nunique() < 2 or valid["y"].nunique() < 2:
        return np.nan
    return float(np.corrcoef(valid["x"], valid["y"])[0, 1])


def spearman(x: pd.Series, y: pd.Series) -> float:
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    return pearson(valid["x"].rank(), valid["y"].rank())


def neighbourhood_sensitivity(
    paths: dict[str, Path], review_path: Path, interval_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    points = pd.read_csv(review_path)[["review_id", "row", "col", "category"]]
    intervals = pd.read_csv(interval_path)
    records = []
    point_rows = points.set_index("review_id")
    for start, end in INTERVALS:
        with rasterio.open(paths[f"annual_change_{start}_{end}"]) as src:
            subset = intervals[
                intervals["start_year"].eq(start) & intervals["end_year"].eq(end)
            ]
            for row in subset.itertuples(index=False):
                point = point_rows.loc[row.review_id]
                raster_row = int(point["row"])
                raster_col = int(point["col"])
                window = Window(
                    max(0, raster_col - 1),
                    max(0, raster_row - 1),
                    min(3, src.width - max(0, raster_col - 1)),
                    min(3, src.height - max(0, raster_row - 1)),
                )
                values = src.read(1, window=window, masked=True).astype("float64")
                compressed = values.compressed()
                compressed = compressed[np.isfinite(compressed)]
                records.append(
                    {
                        "review_id": row.review_id,
                        "category": row.category,
                        "start_year": start,
                        "end_year": end,
                        "abs_ndvi_change": row.abs_ndvi_change,
                        "embedding_10m_direct": row.embedding_annual_change,
                        "embedding_3x3_mean": (
                            float(compressed.mean()) if compressed.size else np.nan
                        ),
                        "embedding_3x3_max": (
                            float(compressed.max()) if compressed.size else np.nan
                        ),
                    }
                )
    detail = pd.DataFrame(records)

    def summarize(group: pd.DataFrame, method: str) -> dict:
        return {
            "embedding_method": method,
            "interval_count": int(group[[method, "abs_ndvi_change"]].dropna().shape[0]),
            "pearson_r": pearson(group[method], group["abs_ndvi_change"]),
            "spearman_rho": spearman(group[method], group["abs_ndvi_change"]),
        }

    methods = ["embedding_10m_direct", "embedding_3x3_mean", "embedding_3x3_max"]
    overall = pd.DataFrame([summarize(detail, method) for method in methods])
    category_rows = []
    for category, group in detail.groupby("category"):
        for method in methods:
            row = summarize(group, method)
            row["category"] = category
            category_rows.append(row)
    return detail, overall, pd.DataFrame(category_rows)


def target_grid(reference_path: Path, factor: int) -> dict:
    with rasterio.open(reference_path) as src:
        width = math.ceil(src.width / factor)
        height = math.ceil(src.height / factor)
        transform = src.transform * Affine.scale(src.width / width, src.height / height)
        return {
            "width": width,
            "height": height,
            "transform": transform,
            "crs": src.crs,
            "bounds": tuple(src.bounds),
            "source_width": src.width,
            "source_height": src.height,
            "source_transform": src.transform,
        }


def count_finite_source_cells(reference_path: Path) -> int:
    count = 0
    with rasterio.open(reference_path) as src:
        for _, window in src.block_windows(1):
            count += int(np.isfinite(src.read(1, window=window)).sum())
    return count


def aggregate_raster(
    path: Path, grid: dict, resampling: Resampling, dtype: str = "float32"
) -> np.ndarray:
    floating = np.issubdtype(np.dtype(dtype), np.floating)
    destination = np.full(
        (grid["height"], grid["width"]), np.nan if floating else 0, dtype=dtype
    )
    with rasterio.open(path) as src:
        source_floating = np.issubdtype(np.dtype(src.dtypes[0]), np.floating)
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid["transform"],
            dst_crs=grid["crs"],
            resampling=resampling,
            src_nodata=np.nan if source_floating else src.nodata,
            dst_nodata=np.nan if floating else 0,
            init_dest_nodata=True,
        )
    return destination


def write_cog(
    path: Path,
    data: np.ndarray,
    grid: dict,
    nodata: int | float | None = None,
    resampling: str = "AVERAGE",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="COG",
        width=grid["width"],
        height=grid["height"],
        count=1,
        dtype=str(data.dtype),
        crs=grid["crs"],
        transform=grid["transform"],
        nodata=nodata,
        compress="DEFLATE",
        blocksize=512,
        overview_resampling=resampling,
    ) as dst:
        dst.write(data, 1)


def prepare_common_support(
    paths: dict[str, Path], thresholds: dict[str, float], grid: dict, raster_dir: Path
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    arrays: dict[str, np.ndarray] = {}
    specifications = [
        ("endpoint_change_mean", "endpoint_change", Resampling.average, "float32"),
        ("endpoint_change_max", "endpoint_change", Resampling.max, "float32"),
        ("endpoint_hotspot_fraction", "endpoint_hotspot", Resampling.average, "float32"),
        ("persistence_max", "persistence", Resampling.max, "int16"),
        ("variance_mean", "variance", Resampling.average, "float32"),
        ("slope_mean", "slope", Resampling.average, "float32"),
        ("cumulative_change_mean", "cumulative", Resampling.average, "float32"),
        ("max_annual_change_mean", "max_annual", Resampling.average, "float32"),
    ]
    for output_name, source_name, resampling, dtype in specifications:
        print(f"Aggregating {output_name}")
        arrays[output_name] = aggregate_raster(
            paths[source_name], grid, resampling, dtype
        )
        write_cog(
            raster_dir / f"basscoast_{output_name}_30m.tif",
            arrays[output_name],
            grid,
            nodata=np.nan if np.issubdtype(arrays[output_name].dtype, np.floating) else None,
            resampling="NEAREST" if np.issubdtype(arrays[output_name].dtype, np.integer) else "AVERAGE",
        )

    annual_hotspot_fractions = []
    for start, end in INTERVALS:
        change_name = f"annual_change_{start}_{end}"
        hotspot_name = f"annual_hotspot_{start}_{end}"
        print(f"Aggregating {start}-{end} annual layers")
        change = aggregate_raster(paths[change_name], grid, Resampling.average)
        hotspot = aggregate_raster(paths[hotspot_name], grid, Resampling.average)
        arrays[change_name] = change
        arrays[f"{hotspot_name}_fraction"] = hotspot
        annual_hotspot_fractions.append(hotspot)
        write_cog(
            raster_dir / f"basscoast_{change_name}_mean_30m.tif",
            change,
            grid,
            nodata=np.nan,
        )
        write_cog(
            raster_dir / f"basscoast_{hotspot_name}_fraction_30m.tif",
            hotspot,
            grid,
        )

    any_hot = arrays["endpoint_hotspot_fraction"] > 0
    for hotspot in annual_hotspot_fractions:
        any_hot |= hotspot > 0
    persistent = arrays["persistence_max"] >= 2
    cold = (
        (arrays["endpoint_change_mean"] <= thresholds["endpoint_p25"])
        & (arrays["persistence_max"] == 0)
        & (arrays["variance_mean"] <= thresholds["variance_p25"])
        & (np.abs(arrays["slope_mean"]) <= thresholds["abs_slope_p25"])
        & ~any_hot
    )
    valid = (
        np.isfinite(arrays["endpoint_change_mean"])
        & np.isfinite(arrays["variance_mean"])
        & np.isfinite(arrays["slope_mean"])
    )
    state = np.zeros(any_hot.shape, dtype="uint8")
    state[valid] = 2
    state[cold] = 1
    state[valid & any_hot] = 3
    state[valid & persistent] = 4
    arrays["change_state"] = state
    write_cog(
        raster_dir / "basscoast_change_state_30m.tif",
        state,
        grid,
        nodata=0,
        resampling="NEAREST",
    )

    total = state.size
    valid_total = int((state > 0).sum())
    summary = pd.DataFrame(
        [
            {
                "state_code": code,
                "state_label": label,
                "cell_count_30m": int((state == code).sum()),
                "share_of_grid": float((state == code).sum() / total),
                "share_of_finite_grid": (
                    float((state == code).sum() / valid_total) if code > 0 else np.nan
                ),
            }
            for code, label in STATE_LABELS.items()
        ]
    )
    return arrays, summary


def projected_polygon_area(geometry: dict) -> float:
    polygons = (
        geometry["coordinates"]
        if geometry["type"] == "MultiPolygon"
        else [geometry["coordinates"]]
    )
    total = 0.0
    for polygon in polygons:
        for ring_index, ring in enumerate(polygon):
            lon = [point[0] for point in ring]
            lat = [point[1] for point in ring]
            xs, ys = transform_coords("EPSG:4326", "EPSG:3577", lon, lat)
            signed = 0.5 * sum(
                xs[index] * ys[index + 1] - xs[index + 1] * ys[index]
                for index in range(len(xs) - 1)
            )
            total += abs(signed) if ring_index == 0 else -abs(signed)
    return max(0.0, total)


def geometry_bounds(geometry: dict) -> tuple[float, float, float, float]:
    coordinates = []

    def collect(value):
        if value and isinstance(value[0], (int, float)):
            coordinates.append(value)
        else:
            for item in value:
                collect(item)

    collect(geometry["coordinates"])
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    return min(xs), min(ys), max(xs), max(ys)


def feature_stats(
    geometry: dict,
    clean_mask: np.ndarray,
    arrays: dict[str, np.ndarray],
    grid: dict,
) -> dict:
    west, south, east, north = geometry_bounds(geometry)
    row_a, col_a = rowcol(grid["transform"], west, north)
    row_b, col_b = rowcol(grid["transform"], east, south)
    row_start = max(0, min(row_a, row_b) - 1)
    row_stop = min(grid["height"], max(row_a, row_b) + 2)
    col_start = max(0, min(col_a, col_b) - 1)
    col_stop = min(grid["width"], max(col_a, col_b) + 2)
    window = Window(col_start, row_start, col_stop - col_start, row_stop - row_start)
    inside = geometry_mask(
        [geometry],
        out_shape=(int(window.height), int(window.width)),
        transform=window_transform(window, grid["transform"]),
        invert=True,
    )
    inside &= clean_mask[row_start:row_stop, col_start:col_stop]
    local_rows, local_cols = np.where(inside)
    if not len(local_rows):
        raise RuntimeError("Vector feature did not overlap its source mask.")
    mean_row = float(local_rows.mean())
    mean_col = float(local_cols.mean())
    nearest = np.argmin((local_rows - mean_row) ** 2 + (local_cols - mean_col) ** 2)
    representative_row = row_start + int(local_rows[nearest])
    representative_col = col_start + int(local_cols[nearest])
    lon, lat = rasterio.transform.xy(
        grid["transform"], representative_row, representative_col, offset="center"
    )
    result = {
        "cell_count_30m": int(inside.sum()),
        "area_m2": projected_polygon_area(geometry),
        "representative_row_30m": representative_row,
        "representative_col_30m": representative_col,
        "lon": float(lon),
        "lat": float(lat),
    }
    for key in [
        "endpoint_change_mean",
        "endpoint_change_max",
        "endpoint_hotspot_fraction",
        "persistence_max",
        "variance_mean",
        "slope_mean",
        "cumulative_change_mean",
        "max_annual_change_mean",
    ]:
        local = arrays[key][row_start:row_stop, col_start:col_stop][inside]
        finite = local[np.isfinite(local)]
        result[key] = float(finite.mean()) if finite.size else np.nan
    result["persistent_fraction"] = float(
        np.mean(arrays["persistence_max"][row_start:row_stop, col_start:col_stop][inside] >= 2)
    )
    for start, end in INTERVALS:
        change_key = f"annual_change_{start}_{end}"
        hotspot_key = f"annual_hotspot_{start}_{end}_fraction"
        local_change = arrays[change_key][row_start:row_stop, col_start:col_stop][inside]
        finite_change = local_change[np.isfinite(local_change)]
        result[change_key] = float(finite_change.mean()) if finite_change.size else np.nan
        result[hotspot_key] = float(
            np.nanmean(arrays[hotspot_key][row_start:row_stop, col_start:col_stop][inside])
        )
    return result


def extract_patch_features(
    state: np.ndarray,
    arrays: dict[str, np.ndarray],
    grid: dict,
    min_hot_cells: int,
    min_cold_cells: int,
) -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
    all_records = []
    geojson_features = []
    retention_rows = []
    definitions = [
        ("hotspot_patch", state >= 3, min_hot_cells),
        ("coldspot_patch", state == 1, min_cold_cells),
    ]
    feature_number = 1
    for feature_type, raw_mask, minimum in definitions:
        clean = sieve(raw_mask.astype("uint8"), size=minimum, connectivity=8).astype(bool)
        retention_rows.append(
            {
                "feature_type": feature_type,
                "minimum_connected_cells_30m": minimum,
                "raw_cell_count_30m": int(raw_mask.sum()),
                "retained_cell_count_30m": int(clean.sum()),
                "retained_share": float(clean.sum() / raw_mask.sum()) if raw_mask.any() else 0.0,
            }
        )
        print(f"Extracting {feature_type} polygons")
        for geometry, value in shapes(
            clean.astype("uint8"),
            mask=clean,
            transform=grid["transform"],
            connectivity=8,
        ):
            if int(value) != 1:
                continue
            stats = feature_stats(geometry, clean, arrays, grid)
            feature_id = f"BCF{feature_number:06d}"
            source_state = int(
                round(
                    arrays["change_state"][
                        stats["representative_row_30m"],
                        stats["representative_col_30m"],
                    ]
                )
            )
            record = {
                "feature_id": feature_id,
                "feature_type": feature_type,
                "source_state_code": source_state,
                "source_state_label": STATE_LABELS[source_state],
                **stats,
            }
            all_records.append(record)
            properties = {
                key: value
                for key, value in record.items()
                if key not in {"representative_row_30m", "representative_col_30m"}
            }
            geojson_features.append(
                {"type": "Feature", "geometry": geometry, "properties": properties}
            )
            feature_number += 1
    return pd.DataFrame(all_records), geojson_features, pd.DataFrame(retention_rows)


def save_geojson_gzip(path: Path, features: list[dict]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))


def select_enrichment_features(features: pd.DataFrame, target: int) -> pd.DataFrame:
    if target <= 0:
        return features.head(0).copy()
    selected = []
    groups = ["hotspot_patch", "coldspot_patch"]
    per_group = max(1, target // len(groups))
    for feature_type in groups:
        group = features[features["feature_type"].eq(feature_type)].sort_values(
            ["area_m2", "lat", "lon"]
        )
        if group.empty:
            continue
        indices = np.linspace(0, len(group) - 1, min(per_group, len(group))).round().astype(int)
        selected.append(group.iloc[np.unique(indices)])
    result = pd.concat(selected, ignore_index=True).head(target).copy()
    result.insert(0, "review_id", np.arange(1, len(result) + 1))
    result["sample_id"] = result["review_id"]
    result["pixel_key"] = result["feature_id"]
    result["category"] = result["feature_type"]
    result["google_maps_link"] = (
        "https://www.google.com/maps?q="
        + result["lat"].astype(str)
        + ","
        + result["lon"].astype(str)
    )
    annual_change_columns = [f"annual_change_{start}_{end}" for start, end in INTERVALS]
    annual_hotspot_columns = []
    for start, end in INTERVALS:
        fraction = result[f"annual_hotspot_{start}_{end}_fraction"]
        output = f"annual_hotspot_{start}_{end}"
        result[output] = (fraction > 0).astype("uint8")
        annual_hotspot_columns.append(output)
    annual_values = result[annual_change_columns].to_numpy()
    max_indices = np.nanargmax(annual_values, axis=1)
    result["max_change_year"] = [INTERVALS[index][1] for index in max_indices]
    first_years = []
    for row in result[annual_hotspot_columns].to_numpy():
        matches = np.flatnonzero(row > 0)
        first_years.append(INTERVALS[matches[0]][1] if len(matches) else 0)
    result["first_hotspot_year"] = first_years
    result["endpoint_change"] = result["endpoint_change_mean"]
    result["endpoint_hotspot"] = (result["endpoint_hotspot_fraction"] > 0).astype("uint8")
    result["persistence_count"] = result["persistence_max"]
    result["variance_annual_change"] = result["variance_mean"]
    result["slope_annual_change"] = result["slope_mean"]
    result["cumulative_change"] = result["cumulative_change_mean"]
    result["mean_annual_change"] = result[annual_change_columns].mean(axis=1)
    result["max_annual_change"] = result[annual_change_columns].max(axis=1)
    return result


def ndvi_threshold(metadata_path: Path) -> float:
    metadata = pd.read_csv(metadata_path)
    value = metadata.loc[metadata["item"].eq("ndvi_event_threshold"), "value"]
    if value.empty:
        return 0.0758
    return float(value.iloc[0])


def run_external_enrichment(
    test_points: pd.DataFrame,
    threshold: float,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    import stage03_dea_enrichment as phase3
    import stage05_ndvi_pilot as phase8

    warnings = []
    if test_points.empty:
        return pd.DataFrame(), pd.DataFrame(), warnings
    print(f"Sampling DEA Level 3/4 for {len(test_points)} feature locations")
    dea_wide, dea_long, dea_warnings = phase3.build_probe(test_points, YEARS)
    warnings.extend(
        f"DEA {record.get('feature_id', record.get('pixel_key'))}: {record.get('exception_message')}"
        for record in dea_warnings
    )
    dea_long.to_csv(output_dir / "basscoast_phase9_test_dea_long.csv", index=False)

    bbox = [
        float(test_points["lon"].min()),
        float(test_points["lat"].min()),
        float(test_points["lon"].max()),
        float(test_points["lat"].max()),
    ]
    ndvi_tables = []
    for year in YEARS:
        features = phase8.query_stac(year, bbox)
        table, year_warnings = phase8.sample_year(year, test_points, features)
        ndvi_tables.append(table)
        warnings.extend(year_warnings)
    ndvi_long = pd.concat(ndvi_tables, ignore_index=True)
    ndvi_long.to_csv(output_dir / "basscoast_phase9_test_ndvi_long.csv", index=False)

    context = dea_long.copy()
    context["dea_family"] = context["dea_level3_effective_label"]
    annual = phase8.build_annual_table(ndvi_long, context)
    intervals = phase8.build_interval_table(test_points, annual)
    intervals["ndvi_event"] = intervals["valid_interval"] & intervals[
        "abs_ndvi_change"
    ].ge(threshold)
    point_ndvi = phase8.point_summary(test_points, annual, intervals, threshold)
    enriched = test_points.merge(
        dea_wide[
            [
                "review_id",
                "dea_level3_effective_sequence",
                "dea_level4_effective_sequence",
                "dea_level3_class_changed",
                "dea_level4_class_changed",
                "dea_level3_first_change_year",
                "dea_level4_first_change_year",
            ]
        ],
        on="review_id",
        how="left",
    ).merge(point_ndvi, on=["review_id", "sample_id", "pixel_key", "category", "lon", "lat"], how="left")
    embedding_signal = enriched["feature_type"].eq("hotspot_patch")
    dea_signal = enriched["dea_level3_class_changed"].fillna(False).astype(bool)
    ndvi_signal = enriched["ndvi_evidence_label"].ne("ndvi_stable")
    support_count = embedding_signal.astype(int) + dea_signal.astype(int) + ndvi_signal.astype(int)
    enriched["embedding_signal"] = embedding_signal
    enriched["dea_level3_change_signal"] = dea_signal
    enriched["ndvi_change_signal"] = ndvi_signal
    enriched["evidence_component_count"] = support_count
    enriched["provisional_attention_tier"] = np.select(
        [
            support_count >= 3,
            support_count == 2,
            support_count == 1,
            support_count == 0,
        ],
        [
            "tier_1_multi_signal",
            "tier_2_supported",
            "tier_3_single_signal",
            "context_cold",
        ],
        default="unclassified",
    )
    enriched.to_csv(output_dir / "basscoast_phase9_test_enriched_features.csv", index=False)
    return enriched, intervals, warnings


def create_qa_figures(
    state: np.ndarray,
    features: pd.DataFrame,
    sensitivity: pd.DataFrame,
    grid: dict,
    figure_dir: Path,
) -> None:
    import stage05_ndvi_pilot as phase8

    figure_dir.mkdir(parents=True, exist_ok=True)
    step = max(1, math.ceil(max(state.shape) / 1800))
    display_state = state[::step, ::step]
    west, south, east, north = grid["bounds"]
    fig, ax = plt.subplots(figsize=(12, 8))
    try:
        basemap, basemap_bounds = phase8.osm_basemap(
            (west, south, east, north), figure_dir / "basemap_cache", zoom=9
        )
        ax.imshow(
            basemap,
            extent=[basemap_bounds[0], basemap_bounds[2], basemap_bounds[1], basemap_bounds[3]],
            origin="upper",
            alpha=0.72,
            aspect="auto",
        )
    except Exception as exc:
        print(f"WARNING: QA basemap unavailable: {exc}")
    cmap = ListedColormap([STATE_COLOURS[index] for index in range(0, 5)])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)
    ax.imshow(
        display_state,
        extent=[west, east, south, north],
        origin="upper",
        cmap=cmap,
        norm=norm,
        alpha=0.58,
        interpolation="nearest",
        aspect="auto",
    )
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_title("Bass Coast Map-Ready Hot-to-Cold Surface")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(
        handles=[Patch(color=STATE_COLOURS[code], label=STATE_LABELS[code].replace("_", " ").title()) for code in range(1, 5)],
        title="30 m common-support state",
        loc="lower left",
        framealpha=0.94,
    )
    ax.text(
        0.995,
        0.008,
        "Basemap: OpenStreetMap contributors",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2},
    )
    fig.tight_layout()
    fig.savefig(figure_dir / "phase9_hot_cold_surface.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    plot = sensitivity.sort_values("spearman_rho")
    bars = ax.barh(plot["embedding_method"], plot["spearman_rho"], color="#4f7594")
    ax.bar_label(bars, fmt="%.3f", padding=3)
    ax.set_xlim(0, max(0.75, float(plot["spearman_rho"].max()) + 0.08))
    ax.set_xlabel("Spearman correlation with absolute annual NDVI change")
    ax.set_title("10 m Versus 30 m-Neighbourhood Sensitivity")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "phase9_spatial_sensitivity.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for feature_type, colour in [("hotspot_patch", "#c34731"), ("coldspot_patch", "#2f6da8")]:
        values = features.loc[features["feature_type"].eq(feature_type), "area_m2"] / 10_000
        ax.hist(np.log10(values.clip(lower=0.01)), bins=35, alpha=0.65, color=colour, label=feature_type.replace("_", " ").title())
    ticks = [-2, -1, 0, 1, 2, 3]
    ax.set_xticks(ticks, [f"{10**value:g}" for value in ticks])
    ax.set_xlabel("Feature area (hectares, logarithmic scale)")
    ax.set_ylabel("Feature count")
    ax.set_title("Map Interaction Feature Sizes")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "phase9_feature_area_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_manifest(
    path: Path,
    args: argparse.Namespace,
    grid: dict,
    thresholds: dict[str, float],
    features: pd.DataFrame,
    raster_dir: Path,
    source_valid_cells: int,
) -> None:
    manifest = {
        "package": "Bass Coast map data preparation",
        "source_grid": {
            "width": grid["source_width"],
            "height": grid["source_height"],
            "approximate_resolution_m": 10,
            "cell_count": grid["source_width"] * grid["source_height"],
            "finite_cell_count": source_valid_cells,
            "implicit_non_data_cell_count": grid["source_width"] * grid["source_height"] - source_valid_cells,
            "authoritative_raster_folder": str(args.project_folder.resolve()),
        },
        "common_support_grid": {
            "width": grid["width"],
            "height": grid["height"],
            "approximate_resolution_m": 30,
            "cell_count": grid["width"] * grid["height"],
            "crs": str(grid["crs"]),
            "bounds": grid["bounds"],
        },
        "state_codes": STATE_LABELS,
        "thresholds": thresholds,
        "interaction_features": {
            "count": len(features),
            "hotspot_patch_count": int(features["feature_type"].eq("hotspot_patch").sum()),
            "coldspot_patch_count": int(features["feature_type"].eq("coldspot_patch").sum()),
            "minimum_hot_cells_30m": args.min_hot_patch_cells,
            "minimum_cold_cells_30m": args.min_cold_patch_cells,
            "note": "Feature thresholds affect only interaction polygons. The complete hot and cold surface remains in the raster.",
        },
        "rasters": [str(path.resolve()) for path in sorted(raster_dir.glob("*.tif"))],
        "feature_table": str((args.output_dir / "basscoast_phase9_feature_inventory.csv").resolve()),
        "feature_geojson_gzip": str((args.output_dir / "basscoast_phase9_features.geojson.gz").resolve()),
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_report(
    path: Path,
    grid_summary: pd.DataFrame,
    retention: pd.DataFrame,
    sensitivity: pd.DataFrame,
    features: pd.DataFrame,
    enriched: pd.DataFrame,
    warnings: list[str],
    source_total_cells: int,
    source_valid_cells: int,
) -> None:
    best = sensitivity.sort_values("spearman_rho", ascending=False).iloc[0]
    lines = [
        "# Bass Coast Phase 9 Map Data Preparation",
        "",
        "## Purpose",
        "",
        "This package preserves the complete embedding hot-to-cold raster surface and creates a lighter 30 m common-support layer for DEA, NDVI and future web-map interaction.",
        f"The source rectangle contains {source_total_cells:,} grid cells, of which {source_valid_cells:,} contain finite endpoint embedding values.",
        "",
        "## Spatial sensitivity",
        "",
        f"The strongest 900-point NDVI association used `{best['embedding_method']}` with Spearman correlation {best['spearman_rho']:.3f}.",
        "The three methods are retained in the sensitivity table so the 10 m-to-30 m decision remains auditable.",
        "",
        "## Complete common-support grid",
        "",
    ]
    for row in grid_summary.itertuples(index=False):
        if row.state_code == 0:
            lines.append(
                f"- {row.state_label}: {int(row.cell_count_30m):,} cells ({row.share_of_grid:.1%} of the complete rectangle)"
            )
        else:
            lines.append(
                f"- {row.state_label}: {int(row.cell_count_30m):,} cells ({row.share_of_finite_grid:.1%} of finite common-support cells)"
            )
    lines.extend(["", "## Interaction features", ""])
    for row in retention.itertuples(index=False):
        count = int(features["feature_type"].eq(row.feature_type).sum())
        lines.append(
            f"- {row.feature_type}: {count:,} polygons; retained {row.retained_share:.1%} of source-state cells at the default interaction threshold."
        )
    lines.extend(
        [
            "",
            "Small hotspot and cold cells excluded from polygons remain present in `basscoast_change_state_30m.tif` and in the authoritative 10 m rasters.",
            "",
            "## External enrichment test",
            "",
            f"- Test features: {len(enriched):,}",
        ]
    )
    if not enriched.empty:
        for tier, count in enriched["provisional_attention_tier"].value_counts().items():
            lines.append(f"- {tier}: {int(count):,}")
    lines.extend(
        [
            "",
            "The attention tier is a transparent filter assembled from separate embedding, DEA Level 3 change and NDVI-change flags. It is not an accuracy or confidence score.",
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.fresh and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raster_dir = args.output_dir / "rasters"
    figure_dir = args.output_dir / "figures"
    raster_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    paths = required_rasters(args.project_folder)
    thresholds = load_thresholds(args.thresholds)
    alignment, _ = verify_alignment(paths)
    alignment.to_csv(args.output_dir / "basscoast_phase9_alignment_report.csv", index=False)

    print("Running 900-point 10 m/30 m sensitivity check")
    sensitivity_detail, sensitivity, sensitivity_category = neighbourhood_sensitivity(
        paths, args.review_points, args.phase8_intervals
    )
    sensitivity_detail.to_csv(
        args.output_dir / "basscoast_phase9_spatial_sensitivity_detail.csv", index=False
    )
    sensitivity.to_csv(
        args.output_dir / "basscoast_phase9_spatial_sensitivity_summary.csv", index=False
    )
    sensitivity_category.to_csv(
        args.output_dir / "basscoast_phase9_spatial_sensitivity_by_category.csv", index=False
    )

    grid = target_grid(paths["endpoint_change"], args.aggregation_factor)
    source_valid_cells = count_finite_source_cells(paths["endpoint_change"])
    print(
        f"Preparing common-support grid: {grid['width']:,} x {grid['height']:,} "
        f"({grid['width'] * grid['height']:,} cells)"
    )
    arrays, grid_summary = prepare_common_support(paths, thresholds, grid, raster_dir)
    grid_summary.to_csv(
        args.output_dir / "basscoast_phase9_change_state_summary.csv", index=False
    )

    features, geojson_features, retention = extract_patch_features(
        arrays["change_state"],
        arrays,
        grid,
        args.min_hot_patch_cells,
        args.min_cold_patch_cells,
    )
    features.to_csv(
        args.output_dir / "basscoast_phase9_feature_inventory.csv", index=False
    )
    retention.to_csv(
        args.output_dir / "basscoast_phase9_feature_retention_summary.csv", index=False
    )
    save_geojson_gzip(
        args.output_dir / "basscoast_phase9_features.geojson.gz", geojson_features
    )

    test_points = select_enrichment_features(features, args.test_enrichment_features)
    test_points.to_csv(
        args.output_dir / "basscoast_phase9_test_feature_locations.csv", index=False
    )
    warnings: list[str] = []
    enriched = pd.DataFrame()
    if not args.skip_external and not test_points.empty:
        try:
            enriched, test_intervals, external_warnings = run_external_enrichment(
                test_points,
                ndvi_threshold(args.phase8_metadata),
                args.output_dir,
            )
            test_intervals.to_csv(
                args.output_dir / "basscoast_phase9_test_embedding_ndvi_intervals.csv",
                index=False,
            )
            warnings.extend(external_warnings)
        except Exception as exc:
            warnings.append(f"External enrichment failed: {type(exc).__name__}: {exc}")
            print(f"WARNING: {warnings[-1]}")

    create_qa_figures(
        arrays["change_state"], features, sensitivity, grid, figure_dir
    )
    write_manifest(
        args.output_dir / "basscoast_phase9_map_data_manifest.json",
        args,
        grid,
        thresholds,
        features,
        raster_dir,
        source_valid_cells,
    )
    write_report(
        args.output_dir / "basscoast_phase9_map_data_report.md",
        grid_summary,
        retention,
        sensitivity,
        features,
        enriched,
        warnings,
        grid["source_width"] * grid["source_height"],
        source_valid_cells,
    )
    pd.DataFrame({"warning": warnings}).to_csv(
        args.output_dir / "basscoast_phase9_warnings.csv", index=False
    )

    print("\nPhase 9 map-data preparation complete")
    print(f"- source 10 m cells: {grid['source_width'] * grid['source_height']:,}")
    print(f"- common-support cells: {grid['width'] * grid['height']:,}")
    print(f"- interaction features: {len(features):,}")
    print(f"- external test features: {len(enriched):,}")
    print(f"- output: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
