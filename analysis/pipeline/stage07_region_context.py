#!/usr/bin/env python3
"""Build complete 30 m DEA/NDVI pixel histories and region summaries for AusHabitat."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from stage03_dea_enrichment import LEVEL3_LABELS, LEVEL4_LABELS
from stage04_dea_wall_to_wall import DEA_RASTER_ENV_OPTIONS, dea_cog_url
from stage05_ndvi_pilot import public_href, query_stac, tile_name


YEARS = list(range(2017, 2025))
INTERVALS = [(year, year + 1) for year in YEARS[:-1]]
NODATA_CODE = 255
NDVI_PRODUCT = "ga_ls8cls9c_gm_cyear_3"
DEFAULT_PHASE9 = Path("data/processed/map_grid")
DEFAULT_OUTPUT = Path("data/processed/region_context")

RASTER_ENV_OPTIONS = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "6",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "100000000",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase9-dir", type=Path, default=DEFAULT_PHASE9)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--years", default=",".join(map(str, YEARS)))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-years", type=int, default=0)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def selected_years(value: str, max_years: int) -> list[int]:
    years = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    invalid = [year for year in years if year not in YEARS]
    if invalid:
        raise ValueError(f"Unsupported years: {invalid}")
    if max_years > 0:
        years = years[:max_years]
    return years


def grid_from_raster(path: Path) -> dict:
    with rasterio.open(path) as src:
        return {
            "width": src.width,
            "height": src.height,
            "transform": src.transform,
            "crs": src.crs,
            "bounds": tuple(src.bounds),
        }


def load_feature_inputs(phase9_dir: Path) -> tuple[pd.DataFrame, list[dict]]:
    inventory_path = phase9_dir / "basscoast_phase9_feature_inventory.csv"
    geometry_path = phase9_dir / "basscoast_phase9_features.geojson.gz"
    if not inventory_path.exists() or not geometry_path.exists():
        raise FileNotFoundError("Phase 9 feature inventory or geometry file is missing.")
    inventory = pd.read_csv(inventory_path).sort_values("feature_id").reset_index(drop=True)
    with gzip.open(geometry_path, "rt", encoding="utf-8") as handle:
        collection = json.load(handle)
    geometries = collection.get("features", [])
    geometry_by_id = {feature["properties"]["feature_id"]: feature["geometry"] for feature in geometries}
    missing = [feature_id for feature_id in inventory["feature_id"] if feature_id not in geometry_by_id]
    if missing:
        raise ValueError(f"Missing geometry for {len(missing)} features.")
    ordered = [geometry_by_id[feature_id] for feature_id in inventory["feature_id"]]
    return inventory, ordered


def feature_label_raster(geometries: list[dict], grid: dict) -> np.ndarray:
    shapes = ((geometry, index) for index, geometry in enumerate(geometries, start=1))
    return rasterize(
        shapes,
        out_shape=(grid["height"], grid["width"]),
        transform=grid["transform"],
        fill=0,
        dtype="int32",
        all_touched=False,
    )


def write_cog(path: Path, data: np.ndarray, grid: dict, nodata, resampling: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with rasterio.open(
        temporary,
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
    temporary.replace(path)


def read_cog(path: Path, dtype=None) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1, out_dtype=dtype)


def read_dea_layer(year: int, band: str, grid: dict) -> np.ndarray:
    url = dea_cog_url(year, band)
    with rasterio.Env(**DEA_RASTER_ENV_OPTIONS), rasterio.open(url) as src:
        with WarpedVRT(
            src,
            crs=grid["crs"],
            transform=grid["transform"],
            width=grid["width"],
            height=grid["height"],
            resampling=Resampling.nearest,
            src_nodata=src.nodata,
            nodata=NODATA_CODE,
            dtype="uint8",
        ) as vrt:
            return vrt.read(1, out_dtype="uint8", masked=True).filled(NODATA_CODE)


def clipped_window(src, grid: dict) -> Window | None:
    west, south, east, north = transform_bounds(
        src.crs, grid["crs"], *src.bounds, densify_pts=21
    )
    grid_west, grid_south, grid_east, grid_north = grid["bounds"]
    west = max(west, grid_west)
    south = max(south, grid_south)
    east = min(east, grid_east)
    north = min(north, grid_north)
    if west >= east or south >= north:
        return None
    raw = from_bounds(west, south, east, north, grid["transform"])
    col_start = max(0, math.floor(raw.col_off))
    row_start = max(0, math.floor(raw.row_off))
    col_stop = min(grid["width"], math.ceil(raw.col_off + raw.width))
    row_stop = min(grid["height"], math.ceil(raw.row_off + raw.height))
    if col_start >= col_stop or row_start >= row_stop:
        return None
    return Window(col_start, row_start, col_stop - col_start, row_stop - row_start)


def read_warped_window(url: str, grid: dict, window: Window, dtype: str) -> np.ma.MaskedArray:
    with rasterio.Env(**RASTER_ENV_OPTIONS), rasterio.open(url) as src:
        nodata = np.nan if dtype.startswith("float") else src.nodata
        with WarpedVRT(
            src,
            crs=grid["crs"],
            transform=grid["transform"],
            width=grid["width"],
            height=grid["height"],
            resampling=Resampling.nearest,
            src_nodata=src.nodata,
            nodata=nodata,
            dtype=dtype,
        ) as vrt:
            return vrt.read(1, window=window, masked=True, out_dtype=dtype)


def read_ndvi_year(year: int, grid: dict) -> tuple[np.ndarray, np.ndarray, list[str]]:
    ndvi = np.full((grid["height"], grid["width"]), np.nan, dtype="float32")
    observations = np.zeros((grid["height"], grid["width"]), dtype="uint16")
    assigned = np.zeros((grid["height"], grid["width"]), dtype=bool)
    warnings: list[str] = []
    features = query_stac(year, list(grid["bounds"]))

    for feature in features:
        assets = feature.get("assets", {})
        required = {"nbart_red", "nbart_nir", "count"}
        if not required.issubset(assets):
            warnings.append(f"{year}: {feature.get('id')} missing {sorted(required - set(assets))}")
            continue
        red_url = public_href(assets["nbart_red"]["href"])
        nir_url = public_href(assets["nbart_nir"]["href"])
        count_url = public_href(assets["count"]["href"])
        name = tile_name(feature)
        try:
            with rasterio.Env(**RASTER_ENV_OPTIONS), rasterio.open(red_url) as src:
                window = clipped_window(src, grid)
            if window is None:
                continue
            rows, cols = window.toslices()
            red = read_warped_window(red_url, grid, window, "float32")
            nir = read_warped_window(nir_url, grid, window, "float32")
            count = read_warped_window(count_url, grid, window, "float32")
            red_data = red.filled(np.nan)
            nir_data = nir.filled(np.nan)
            count_data = count.filled(0)
            denominator = nir_data + red_data
            valid = (
                np.isfinite(red_data)
                & np.isfinite(nir_data)
                & np.isfinite(count_data)
                & (red_data > 0)
                & (nir_data > 0)
                & (count_data > 0)
                & (denominator != 0)
            )
            tile_ndvi = np.full(red_data.shape, np.nan, dtype="float32")
            tile_ndvi[valid] = (nir_data[valid] - red_data[valid]) / denominator[valid]
            valid &= np.isfinite(tile_ndvi) & (tile_ndvi >= -1) & (tile_ndvi <= 1)
            destination_available = ~assigned[rows, cols]
            use = valid & destination_available
            ndvi[rows, cols][use] = tile_ndvi[use]
            observations[rows, cols][use] = np.clip(count_data[use], 0, 65535).astype("uint16")
            assigned[rows, cols][use] = True
            print(f"  {year} NDVI tile {name}: {int(use.sum()):,} cells")
        except Exception as exc:
            warnings.append(f"{year}: failed NDVI tile {name}: {type(exc).__name__}: {exc}")
    return ndvi, observations, warnings


def class_region_summary(
    values: np.ndarray,
    feature_labels: np.ndarray,
    region_cell_counts: np.ndarray,
    code_labels: dict[int, str],
) -> dict[str, np.ndarray]:
    region_count = len(region_cell_counts) - 1
    valid = (feature_labels > 0) & (values != NODATA_CODE)
    combined = feature_labels[valid].astype("int64") * 256 + values[valid].astype("int64")
    counts = np.bincount(combined, minlength=(region_count + 1) * 256).reshape(region_count + 1, 256)
    counts[:, NODATA_CODE] = 0
    valid_counts = counts.sum(axis=1)
    dominant_code = counts.argmax(axis=1)
    dominant_count = counts[np.arange(region_count + 1), dominant_code]
    counts[np.arange(region_count + 1), dominant_code] = -1
    secondary_code = counts.argmax(axis=1)
    secondary_count = counts[np.arange(region_count + 1), secondary_code]
    coverage = np.divide(
        valid_counts,
        region_cell_counts,
        out=np.zeros(region_count + 1, dtype="float64"),
        where=region_cell_counts > 0,
    )
    dominant_share = np.divide(
        dominant_count,
        valid_counts,
        out=np.zeros(region_count + 1, dtype="float64"),
        where=valid_counts > 0,
    )
    secondary_share = np.divide(
        secondary_count,
        valid_counts,
        out=np.zeros(region_count + 1, dtype="float64"),
        where=valid_counts > 0,
    )
    return {
        "coverage": coverage[1:],
        "dominant_code": dominant_code[1:],
        "dominant_label": np.array([code_labels.get(int(code), f"Unknown {int(code)}") for code in dominant_code[1:]], dtype=object),
        "dominant_share": dominant_share[1:],
        "secondary_code": secondary_code[1:],
        "secondary_label": np.array([code_labels.get(int(code), f"Unknown {int(code)}") for code in secondary_code[1:]], dtype=object),
        "secondary_share": secondary_share[1:],
    }


def numeric_region_summary(
    values: np.ndarray,
    observations: np.ndarray,
    feature_labels: np.ndarray,
    region_cell_counts: np.ndarray,
) -> dict[str, np.ndarray]:
    region_count = len(region_cell_counts) - 1
    valid = (feature_labels > 0) & np.isfinite(values)
    labels = feature_labels[valid]
    selected = values[valid].astype("float64")
    valid_counts = np.bincount(labels, minlength=region_count + 1)
    sums = np.bincount(labels, weights=selected, minlength=region_count + 1)
    means = np.divide(sums, valid_counts, out=np.full(region_count + 1, np.nan), where=valid_counts > 0)
    obs_sums = np.bincount(
        labels,
        weights=observations[valid].astype("float64"),
        minlength=region_count + 1,
    )
    obs_means = np.divide(obs_sums, valid_counts, out=np.full(region_count + 1, np.nan), where=valid_counts > 0)
    medians = np.full(region_count + 1, np.nan)
    if valid.any():
        med = pd.Series(selected).groupby(labels, sort=False).median()
        medians[med.index.to_numpy(dtype=int)] = med.to_numpy(dtype=float)
    coverage = np.divide(
        valid_counts,
        region_cell_counts,
        out=np.zeros(region_count + 1, dtype="float64"),
        where=region_cell_counts > 0,
    )
    return {
        "coverage": coverage[1:],
        "mean": means[1:],
        "median": medians[1:],
        "mean_observations": obs_means[1:],
    }


def changed_area_share(
    previous: np.ndarray | None,
    current: np.ndarray,
    feature_labels: np.ndarray,
    region_count: int,
) -> np.ndarray:
    if previous is None:
        return np.full(region_count, np.nan)
    valid = (feature_labels > 0) & (previous != NODATA_CODE) & (current != NODATA_CODE)
    labels = feature_labels[valid]
    valid_counts = np.bincount(labels, minlength=region_count + 1)
    changed_counts = np.bincount(
        labels,
        weights=(previous[valid] != current[valid]).astype("uint8"),
        minlength=region_count + 1,
    )
    shares = np.divide(
        changed_counts,
        valid_counts,
        out=np.full(region_count + 1, np.nan),
        where=valid_counts > 0,
    )
    return shares[1:]


def summarize_embedding_regions(
    inventory: pd.DataFrame,
    feature_labels: np.ndarray,
    phase9_dir: Path,
) -> pd.DataFrame:
    result = inventory.copy()
    region_count = len(result)
    region_cell_counts = np.bincount(feature_labels.ravel(), minlength=region_count + 1)
    persistence = read_cog(phase9_dir / "rasters" / "basscoast_persistence_max_30m.tif", "float32")
    valid = (feature_labels > 0) & np.isfinite(persistence)
    labels = feature_labels[valid]
    sums = np.bincount(labels, weights=persistence[valid], minlength=region_count + 1)
    counts = np.bincount(labels, minlength=region_count + 1)
    mean_persistence = np.divide(sums, counts, out=np.zeros(region_count + 1), where=counts > 0)
    maximum = np.zeros(region_count + 1, dtype="float32")
    np.maximum.at(maximum, labels, persistence[valid])
    repeated = np.bincount(
        labels,
        weights=(persistence[valid] >= 2).astype("uint8"),
        minlength=region_count + 1,
    )
    repeated_share = np.divide(repeated, counts, out=np.zeros(region_count + 1), where=counts > 0)
    result["mean_hotspot_intervals"] = mean_persistence[1:]
    result["maximum_hotspot_intervals"] = maximum[1:]
    result["repeat_change_coverage"] = repeated_share[1:]

    hotspot_columns = [f"annual_hotspot_{a}_{b}_fraction" for a, b in INTERVALS]
    change_columns = [f"annual_change_{a}_{b}" for a, b in INTERVALS]
    hotspot_values = result[hotspot_columns].to_numpy(dtype=float)
    change_values = result[change_columns].to_numpy(dtype=float)
    result["active_interval_count"] = (hotspot_values >= 0.05).sum(axis=1)
    strongest = np.nanargmax(change_values, axis=1)
    result["strongest_change_interval"] = [f"{INTERVALS[index][0]}-{INTERVALS[index][1]}" for index in strongest]

    result["region_behaviour"] = np.select(
        [
            result["feature_type"].eq("coldspot_patch"),
            result["repeat_change_coverage"].ge(0.50),
            result["repeat_change_coverage"].ge(0.10),
        ],
        ["low_change_reference", "repeated_change", "mixed_change",],
        default="mostly_single_period_change",
    )
    hot = result["feature_type"].eq("hotspot_patch")
    low_cut = result.loc[hot, "cumulative_change_mean"].quantile(1 / 3)
    high_cut = result.loc[hot, "cumulative_change_mean"].quantile(2 / 3)
    result["overall_activity"] = np.select(
        [
            result["feature_type"].eq("coldspot_patch"),
            result["cumulative_change_mean"].ge(high_cut),
            result["cumulative_change_mean"].ge(low_cut),
        ],
        ["low", "high", "moderate"],
        default="low",
    )
    variance_low = result.loc[hot, "variance_mean"].quantile(1 / 3)
    variance_high = result.loc[hot, "variance_mean"].quantile(2 / 3)
    result["year_to_year_pattern"] = np.select(
        [
            result["variance_mean"].ge(variance_high),
            result["variance_mean"].ge(variance_low),
        ],
        ["highly_uneven", "mixed"],
        default="fairly_consistent",
    )
    result["change_intensity_trend"] = np.select(
        [result["slope_mean"].ge(0.01), result["slope_mean"].le(-0.01)],
        ["increasing", "decreasing"],
        default="no_clear_trend",
    )
    return result


def annual_context_rows(
    year: int,
    inventory: pd.DataFrame,
    feature_labels: np.ndarray,
    region_cell_counts: np.ndarray,
    l3: np.ndarray,
    l4: np.ndarray,
    ndvi: np.ndarray,
    observations: np.ndarray,
    previous_l3: np.ndarray | None,
    previous_l4: np.ndarray | None,
) -> pd.DataFrame:
    l3_summary = class_region_summary(l3, feature_labels, region_cell_counts, LEVEL3_LABELS)
    l4_summary = class_region_summary(l4, feature_labels, region_cell_counts, LEVEL4_LABELS)
    ndvi_summary = numeric_region_summary(ndvi, observations, feature_labels, region_cell_counts)
    region_count = len(inventory)
    return pd.DataFrame(
        {
            "feature_id": inventory["feature_id"],
            "year": year,
            "dea_level3_code": l3_summary["dominant_code"],
            "dea_level3_label": l3_summary["dominant_label"],
            "dea_level3_share": l3_summary["dominant_share"],
            "dea_level3_secondary_code": l3_summary["secondary_code"],
            "dea_level3_secondary_label": l3_summary["secondary_label"],
            "dea_level3_secondary_share": l3_summary["secondary_share"],
            "dea_level3_coverage": l3_summary["coverage"],
            "dea_level4_code": l4_summary["dominant_code"],
            "dea_level4_label": l4_summary["dominant_label"],
            "dea_level4_share": l4_summary["dominant_share"],
            "dea_level4_secondary_code": l4_summary["secondary_code"],
            "dea_level4_secondary_label": l4_summary["secondary_label"],
            "dea_level4_secondary_share": l4_summary["secondary_share"],
            "dea_level4_coverage": l4_summary["coverage"],
            "dea_level3_changed_area_share": changed_area_share(previous_l3, l3, feature_labels, region_count),
            "dea_level4_changed_area_share": changed_area_share(previous_l4, l4, feature_labels, region_count),
            "ndvi_mean": ndvi_summary["mean"],
            "ndvi_median": ndvi_summary["median"],
            "ndvi_coverage": ndvi_summary["coverage"],
            "ndvi_mean_clear_observations": ndvi_summary["mean_observations"],
        }
    )


def first_changed_year(values: np.ndarray, years: list[int]) -> np.ndarray:
    output = np.zeros(values.shape[0], dtype="int16")
    for index in range(1, len(years)):
        changed = (output == 0) & (values[:, index] != values[:, index - 1])
        output[changed] = years[index]
    return output


def linear_slope(values: np.ndarray) -> np.ndarray:
    x = np.arange(values.shape[1], dtype="float64")
    mask = np.isfinite(values)
    count = mask.sum(axis=1)
    x_mean = np.divide((mask * x).sum(axis=1), count, out=np.zeros(len(values)), where=count > 0)
    y_sum = np.nansum(values, axis=1)
    y_mean = np.divide(y_sum, count, out=np.zeros(len(values)), where=count > 0)
    numerator = np.nansum(mask * (x - x_mean[:, None]) * (values - y_mean[:, None]), axis=1)
    denominator = np.sum(mask * (x - x_mean[:, None]) ** 2, axis=1)
    return np.divide(numerator, denominator, out=np.full(len(values), np.nan), where=denominator > 0)


def finalize_region_tables(
    embedding: pd.DataFrame,
    annual: pd.DataFrame,
    years: list[int],
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    annual = annual.sort_values(["feature_id", "year"]).reset_index(drop=True)
    feature_ids = embedding["feature_id"].tolist()
    annual_index = annual.set_index(["feature_id", "year"])

    l3 = np.column_stack([
        annual_index.loc[(feature_ids, year), "dea_level3_code"].to_numpy() for year in years
    ])
    l4 = np.column_stack([
        annual_index.loc[(feature_ids, year), "dea_level4_code"].to_numpy() for year in years
    ])
    ndvi = np.column_stack([
        annual_index.loc[(feature_ids, year), "ndvi_mean"].to_numpy(dtype=float) for year in years
    ])
    ndvi_deltas = np.diff(ndvi, axis=1)

    cold = embedding["feature_type"].eq("coldspot_patch").to_numpy()
    cold_deltas = np.abs(ndvi_deltas[cold])
    finite_cold = cold_deltas[np.isfinite(cold_deltas)]
    ndvi_event_threshold = float(np.quantile(finite_cold, 0.95)) if finite_cold.size else 0.0758

    summary = embedding.copy()
    summary["dea_level3_sequence"] = [" | ".join(LEVEL3_LABELS.get(int(code), f"Unknown {int(code)}") for code in row) for row in l3]
    summary["dea_level4_sequence"] = [" | ".join(LEVEL4_LABELS.get(int(code), f"Unknown {int(code)}") for code in row) for row in l4]
    summary["dea_level3_changed"] = (np.max(l3, axis=1) != np.min(l3, axis=1))
    summary["dea_level4_changed"] = (np.max(l4, axis=1) != np.min(l4, axis=1))
    summary["dea_level3_first_change_year"] = first_changed_year(l3, years)
    summary["dea_level4_first_change_year"] = first_changed_year(l4, years)

    summary["ndvi_start"] = ndvi[:, 0]
    summary["ndvi_end"] = ndvi[:, -1]
    summary["ndvi_endpoint_change"] = ndvi[:, -1] - ndvi[:, 0]
    summary["ndvi_slope"] = linear_slope(ndvi)
    summary["ndvi_variance"] = np.nanvar(ndvi, axis=1)
    max_delta_index = np.nanargmax(np.where(np.isfinite(ndvi_deltas), np.abs(ndvi_deltas), -np.inf), axis=1)
    summary["ndvi_largest_change_interval"] = [f"{years[index]}-{years[index + 1]}" for index in max_delta_index]
    summary["ndvi_largest_signed_change"] = ndvi_deltas[np.arange(len(summary)), max_delta_index]
    summary["ndvi_direction"] = np.select(
        [
            summary["ndvi_endpoint_change"].ge(ndvi_event_threshold),
            summary["ndvi_endpoint_change"].le(-ndvi_event_threshold),
        ],
        ["greening", "browning"],
        default="stable",
    )
    summary["ndvi_change_signal"] = np.any(np.abs(ndvi_deltas) >= ndvi_event_threshold, axis=1)
    transition_max = annual.groupby("feature_id")["dea_level3_changed_area_share"].max().reindex(feature_ids).fillna(0).to_numpy()
    summary["dea_transition_signal"] = summary["dea_level3_changed"] | (transition_max >= 0.10)
    summary["embedding_change_signal"] = summary["feature_type"].eq("hotspot_patch")
    summary["evidence_source_count"] = (
        summary["embedding_change_signal"].astype(int)
        + summary["dea_transition_signal"].astype(int)
        + summary["ndvi_change_signal"].astype(int)
    )
    summary["evidence_pattern"] = [
        "+".join(
            name
            for name, active in [
                ("embedding", embedding_active),
                ("dea", dea_active),
                ("ndvi", ndvi_active),
            ]
            if active
        ) or "none"
        for embedding_active, dea_active, ndvi_active in zip(
            summary["embedding_change_signal"],
            summary["dea_transition_signal"],
            summary["ndvi_change_signal"],
        )
    ]

    annual["ndvi_previous_year_change"] = annual.groupby("feature_id")["ndvi_mean"].diff()
    annual["dea_level3_transition"] = annual.groupby("feature_id")["dea_level3_label"].shift().fillna(annual["dea_level3_label"]) + " -> " + annual["dea_level3_label"]
    annual["dea_level4_transition"] = annual.groupby("feature_id")["dea_level4_label"].shift().fillna(annual["dea_level4_label"]) + " -> " + annual["dea_level4_label"]
    annual["ndvi_change_event"] = annual["ndvi_previous_year_change"].abs().ge(ndvi_event_threshold)

    annual.to_csv(output_dir / "basscoast_phase10_region_year_context.csv", index=False)
    summary.to_csv(output_dir / "basscoast_phase10_region_summary.csv", index=False)
    return summary, annual, ndvi_event_threshold


def coverage_report(
    annual: pd.DataFrame,
    feature_labels: np.ndarray,
    raster_dir: Path,
    years: list[int],
) -> pd.DataFrame:
    region_cells = feature_labels > 0
    rows = []
    for year in years:
        l3 = read_cog(raster_dir / f"basscoast_dea_level3_{year}_30m.tif", "uint8")
        l4 = read_cog(raster_dir / f"basscoast_dea_level4_{year}_30m.tif", "uint8")
        ndvi = read_cog(raster_dir / f"basscoast_ndvi_{year}_30m.tif", "float32")
        subset = annual[annual["year"].eq(year)]
        rows.append(
            {
                "year": year,
                "region_count": int(len(subset)),
                "regions_with_dea_level3": int(subset["dea_level3_coverage"].gt(0).sum()),
                "regions_with_dea_level4": int(subset["dea_level4_coverage"].gt(0).sum()),
                "regions_with_ndvi": int(subset["ndvi_coverage"].gt(0).sum()),
                "dea_level3_region_cell_coverage": float((region_cells & (l3 != NODATA_CODE)).sum() / region_cells.sum()),
                "dea_level4_region_cell_coverage": float((region_cells & (l4 != NODATA_CODE)).sum() / region_cells.sum()),
                "ndvi_region_cell_coverage": float((region_cells & np.isfinite(ndvi)).sum() / region_cells.sum()),
            }
        )
    return pd.DataFrame(rows)


def write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    coverage: pd.DataFrame,
    ndvi_threshold: float,
    warnings: list[str],
) -> None:
    lines = [
        "# Bass Coast Phase 10 Wall-to-Wall Context",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Coverage",
        "",
        f"- Interactive regions: {len(summary):,}",
        f"- Region-year records: {len(annual):,}",
        f"- Annual pixel-history years: {annual['year'].nunique()}",
        f"- Region-level NDVI event threshold from cold-reference annual changes: {ndvi_threshold:.6f}",
        "",
    ]
    for row in coverage.itertuples(index=False):
        lines.append(
            f"- {row.year}: DEA L3 {row.dea_level3_region_cell_coverage:.3%} "
            f"({row.regions_with_dea_level3:,}/{row.region_count:,} regions), "
            f"DEA L4 {row.dea_level4_region_cell_coverage:.3%} "
            f"({row.regions_with_dea_level4:,}/{row.region_count:,} regions), and "
            f"NDVI {row.ndvi_region_cell_coverage:.3%} "
            f"({row.regions_with_ndvi:,}/{row.region_count:,} regions) of interaction-region cells."
        )
    lines.extend(
        [
            "",
            "## Evidence patterns",
            "",
        ]
    )
    for pattern, count in summary["evidence_pattern"].value_counts().items():
        lines.append(f"- {pattern}: {int(count):,} regions")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in warnings] or ["- None."])
    (output_dir / "basscoast_phase10_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_self_test() -> int:
    labels = np.array([[1, 1, 2], [1, 2, 2]], dtype="int32")
    counts = np.bincount(labels.ravel(), minlength=3)
    classes = np.array([[112, 112, 111], [111, 111, 111]], dtype="uint8")
    result = class_region_summary(classes, labels, counts, LEVEL3_LABELS)
    assert result["dominant_code"].tolist() == [112, 111]
    values = np.array([[0.2, 0.4, 0.6], [0.4, 0.5, np.nan]], dtype="float32")
    obs = np.full(values.shape, 10, dtype="uint16")
    numeric = numeric_region_summary(values, obs, labels, counts)
    assert np.allclose(numeric["mean"], [1 / 3, 0.55], equal_nan=True)
    share = changed_area_share(classes, np.where(classes == 112, 111, classes), labels, 2)
    assert np.allclose(share, [2 / 3, 0], equal_nan=True)
    print("Phase 10 aggregation self-test passed.")
    return 0


def run(args: argparse.Namespace) -> int:
    if args.self_test:
        return run_self_test()
    years = selected_years(args.years, args.max_years)
    if years != YEARS:
        raise ValueError("The production region summary requires the complete 2017-2024 sequence.")

    phase9_dir = args.phase9_dir
    output_dir = args.output_dir
    raster_dir = output_dir / "rasters"
    checkpoint_dir = output_dir / "checkpoints"
    if args.force and output_dir.exists():
        shutil.rmtree(output_dir)
    raster_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    state_path = phase9_dir / "rasters" / "basscoast_change_state_30m.tif"
    grid = grid_from_raster(state_path)
    inventory, geometries = load_feature_inputs(phase9_dir)
    feature_labels = feature_label_raster(geometries, grid)
    region_cell_counts = np.bincount(feature_labels.ravel(), minlength=len(inventory) + 1)
    embedding = summarize_embedding_regions(inventory, feature_labels, phase9_dir)
    embedding.to_csv(output_dir / "basscoast_phase10_embedding_region_summary.csv", index=False)
    write_cog(
        raster_dir / "basscoast_interaction_region_id_30m.tif",
        feature_labels,
        grid,
        nodata=0,
        resampling="NEAREST",
    )

    warnings: list[str] = []
    annual_tables = []
    previous_l3 = None
    previous_l4 = None
    for year in years:
        print(f"\nProcessing complete context for {year}")
        checkpoint = checkpoint_dir / f"region_context_{year}.csv"
        l3_path = raster_dir / f"basscoast_dea_level3_{year}_30m.tif"
        l4_path = raster_dir / f"basscoast_dea_level4_{year}_30m.tif"
        ndvi_path = raster_dir / f"basscoast_ndvi_{year}_30m.tif"
        count_path = raster_dir / f"basscoast_ndvi_clear_observations_{year}_30m.tif"

        reusable = args.resume and all(path.exists() for path in [checkpoint, l3_path, l4_path, ndvi_path, count_path])
        if reusable:
            print(f"Reusing {year} pixel and region checkpoints")
            l3 = read_cog(l3_path, "uint8")
            l4 = read_cog(l4_path, "uint8")
            annual_tables.append(pd.read_csv(checkpoint))
        else:
            print(f"  Reading DEA Level 3 for {year}")
            l3 = read_dea_layer(year, "level3", grid)
            print(f"  Reading DEA Level 4 for {year}")
            l4 = read_dea_layer(year, "level4", grid)
            print(f"  Reading Landsat GeoMAD NDVI for {year}")
            ndvi, observations, year_warnings = read_ndvi_year(year, grid)
            warnings.extend(year_warnings)
            write_cog(l3_path, l3, grid, nodata=NODATA_CODE, resampling="NEAREST")
            write_cog(l4_path, l4, grid, nodata=NODATA_CODE, resampling="NEAREST")
            write_cog(ndvi_path, ndvi, grid, nodata=np.nan, resampling="AVERAGE")
            write_cog(count_path, observations, grid, nodata=0, resampling="AVERAGE")
            table = annual_context_rows(
                year,
                inventory,
                feature_labels,
                region_cell_counts,
                l3,
                l4,
                ndvi,
                observations,
                previous_l3,
                previous_l4,
            )
            table.to_csv(checkpoint, index=False)
            annual_tables.append(table)
            del ndvi, observations
        previous_l3 = l3
        previous_l4 = l4

    annual = pd.concat(annual_tables, ignore_index=True)
    summary, annual, ndvi_threshold = finalize_region_tables(
        embedding, annual, years, output_dir
    )
    coverage = coverage_report(annual, feature_labels, raster_dir, years)
    coverage.to_csv(output_dir / "basscoast_phase10_coverage_report.csv", index=False)
    pd.DataFrame({"warning": warnings}).to_csv(output_dir / "basscoast_phase10_warnings.csv", index=False)
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "grid": {
            "width": grid["width"],
            "height": grid["height"],
            "crs": str(grid["crs"]),
            "bounds": grid["bounds"],
            "approximate_resolution_m": 30,
        },
        "years": years,
        "region_count": len(summary),
        "region_year_rows": len(annual),
        "ndvi_product": NDVI_PRODUCT,
        "ndvi_event_threshold": ndvi_threshold,
        "pixel_history_note": "Annual DEA Level 3, Level 4, NDVI and clear-observation COGs are aligned to the Phase 9 30 m grid.",
    }
    (output_dir / "basscoast_phase10_manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    write_report(output_dir, summary, annual, coverage, ndvi_threshold, warnings)
    print(f"\nSaved complete Phase 10 context to {output_dir}")
    print(f"Regions: {len(summary):,}; region-year rows: {len(annual):,}")
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
