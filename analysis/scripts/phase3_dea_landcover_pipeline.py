#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform as transform_coords


DEA_LANDCOVER_PRODUCT = "ga_ls_landcover_class_cyear_3"
DEA_LANDCOVER_VERSION = "2-0-0"
YEARS = list(range(2017, 2025))
DEA_RASTER_ENV_OPTIONS = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
}
WARNING_COLUMNS = [
    "review_id",
    "sample_id",
    "pixel_key",
    "category",
    "lon",
    "lat",
    "year",
    "exception_type",
    "exception_message",
    "traceback",
]

LEVEL3_LABELS = {
    111: "Cultivated Terrestrial Vegetation",
    112: "Natural Terrestrial Vegetation",
    124: "Natural Aquatic Vegetation",
    215: "Artificial Surface",
    216: "Natural Bare Surface",
    220: "Water",
    255: "No Data",
}

LEVEL4_LABELS = {
    1: "Cultivated Terrestrial Vegetated",
    2: "Cultivated Terrestrial Vegetated: Woody",
    3: "Cultivated Terrestrial Vegetated: Herbaceous",
    9: "Cultivated Terrestrial Vegetated: Woody Closed (> 65%)",
    10: "Cultivated Terrestrial Vegetated: Woody Open (40 to 65%)",
    11: "Cultivated Terrestrial Vegetated: Woody Open (15 to 40%)",
    12: "Cultivated Terrestrial Vegetated: Woody Sparse (4 to 15%)",
    13: "Cultivated Terrestrial Vegetated: Woody Scattered (1 to 4%)",
    14: "Cultivated Terrestrial Vegetated: Herbaceous Closed (> 65%)",
    15: "Cultivated Terrestrial Vegetated: Herbaceous Open (40 to 65%)",
    16: "Cultivated Terrestrial Vegetated: Herbaceous Open (15 to 40%)",
    17: "Cultivated Terrestrial Vegetated: Herbaceous Sparse (4 to 15%)",
    18: "Cultivated Terrestrial Vegetated: Herbaceous Scattered (1 to 4%)",
    19: "Natural Terrestrial Vegetated",
    20: "Natural Terrestrial Vegetated: Woody",
    21: "Natural Terrestrial Vegetated: Herbaceous",
    27: "Natural Terrestrial Vegetated: Woody Closed (> 65%)",
    28: "Natural Terrestrial Vegetated: Woody Open (40 to 65%)",
    29: "Natural Terrestrial Vegetated: Woody Open (15 to 40%)",
    30: "Natural Terrestrial Vegetated: Woody Sparse (4 to 15%)",
    31: "Natural Terrestrial Vegetated: Woody Scattered (1 to 4%)",
    32: "Natural Terrestrial Vegetated: Herbaceous Closed (> 65%)",
    33: "Natural Terrestrial Vegetated: Herbaceous Open (40 to 65%)",
    34: "Natural Terrestrial Vegetated: Herbaceous Open (15 to 40%)",
    35: "Natural Terrestrial Vegetated: Herbaceous Sparse (4 to 15%)",
    36: "Natural Terrestrial Vegetated: Herbaceous Scattered (1 to 4%)",
    55: "Natural Aquatic Vegetated",
    56: "Natural Aquatic Vegetated: Woody",
    57: "Natural Aquatic Vegetated: Herbaceous",
    64: "Natural Aquatic Vegetated: Woody Closed (> 65%) Water > 3 months",
    65: "Natural Aquatic Vegetated: Woody Closed (> 65%) Water < 3 months",
    67: "Natural Aquatic Vegetated: Woody Open (40 to 65%) Water > 3 months",
    68: "Natural Aquatic Vegetated: Woody Open (40 to 65%) Water < 3 months",
    70: "Natural Aquatic Vegetated: Woody Open (15 to 40%) Water > 3 months",
    71: "Natural Aquatic Vegetated: Woody Open (15 to 40%) Water < 3 months",
    73: "Natural Aquatic Vegetated: Woody Sparse (4 to 15%) Water > 3 months",
    74: "Natural Aquatic Vegetated: Woody Sparse (4 to 15%) Water < 3 months",
    76: "Natural Aquatic Vegetated: Woody Scattered (1 to 4%) Water > 3 months",
    77: "Natural Aquatic Vegetated: Woody Scattered (1 to 4%) Water < 3 months",
    79: "Natural Aquatic Vegetated: Herbaceous Closed (> 65%) Water > 3 months",
    80: "Natural Aquatic Vegetated: Herbaceous Closed (> 65%) Water < 3 months",
    82: "Natural Aquatic Vegetated: Herbaceous Open (40 to 65%) Water > 3 months",
    83: "Natural Aquatic Vegetated: Herbaceous Open (40 to 65%) Water < 3 months",
    85: "Natural Aquatic Vegetated: Herbaceous Open (15 to 40%) Water > 3 months",
    86: "Natural Aquatic Vegetated: Herbaceous Open (15 to 40%) Water < 3 months",
    88: "Natural Aquatic Vegetated: Herbaceous Sparse (4 to 15%) Water > 3 months",
    89: "Natural Aquatic Vegetated: Herbaceous Sparse (4 to 15%) Water < 3 months",
    91: "Natural Aquatic Vegetated: Herbaceous Scattered (1 to 4%) Water > 3 months",
    92: "Natural Aquatic Vegetated: Herbaceous Scattered (1 to 4%) Water < 3 months",
    93: "Artificial Surface",
    95: "Natural Surface: Sparsely vegetated",
    96: "Natural Surface: Very sparsely vegetated",
    97: "Natural Surface: Bare areas, unvegetated",
    100: "Water: Tidal area",
    101: "Water: Perennial (> 9 months)",
    102: "Water: Non-perennial (7 to 9 months)",
    103: "Water: Non-perennial (4 to 6 months)",
    104: "Water: Non-perennial (1 to 3 months)",
    255: "No Data",
}


def label_for(code, labels):
    if pd.isna(code):
        return None
    return labels.get(int(code), f"Unknown code {int(code)}")


def is_valid_dea_code(code):
    if code is None or pd.isna(code):
        return False
    return int(code) != 255


def effective_class(point_code, majority_code_3x3, majority_code_5x5, labels):
    if is_valid_dea_code(point_code):
        source = "exact_point"
        code = point_code
    elif is_valid_dea_code(majority_code_3x3):
        source = "majority_3x3"
        code = majority_code_3x3
    elif is_valid_dea_code(majority_code_5x5):
        source = "majority_5x5"
        code = majority_code_5x5
    else:
        source = "missing"
        code = None
    return {
        "code": code,
        "label": label_for(code, labels),
        "source": source,
        "has_class": is_valid_dea_code(code),
    }


def sequence_string(values):
    return " | ".join(str(v) if pd.notna(v) else "Missing" for v in values)


def sequence_changed(values):
    valid_values = [v for v in values if pd.notna(v)]
    return len(valid_values) >= 2 and len(set(valid_values)) > 1


def count_adjacent_changes(values):
    return sum(
        pd.notna(a) and pd.notna(b) and a != b
        for a, b in zip(values, values[1:])
    )


def first_change_year(values, years):
    for year, prev_label, cur_label in zip(years[1:], values, values[1:]):
        if pd.notna(prev_label) and pd.notna(cur_label) and prev_label != cur_label:
            return year
    return None


def exception_details(exc):
    return {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc(limit=8),
    }


def runtime_diagnostics():
    return [
        {"item": "python_version", "value": sys.version.replace("\n", " ")},
        {"item": "platform", "value": platform.platform()},
        {"item": "executable", "value": sys.executable},
        {"item": "cwd", "value": str(Path.cwd())},
        {"item": "rasterio_version", "value": rasterio.__version__},
        {"item": "gdal_version", "value": getattr(rasterio, "__gdal_version__", "unknown")},
        {"item": "numpy_version", "value": np.__version__},
        {"item": "pandas_version", "value": pd.__version__},
        {"item": "dea_product", "value": DEA_LANDCOVER_PRODUCT},
        {"item": "dea_version", "value": DEA_LANDCOVER_VERSION},
        {"item": "years", "value": f"{YEARS[0]}-{YEARS[-1]}"},
        {"item": "gdal_env_options", "value": repr(DEA_RASTER_ENV_OPTIONS)},
        {"item": "http_proxy_set", "value": bool(os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))},
        {"item": "https_proxy_set", "value": bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))},
    ]


def selected_diagnostic_points(review_points_df, max_random_points=3):
    selected = []
    known_review_ids = [1, 10, 33, 86]
    if "review_id" in review_points_df.columns:
        for review_id in known_review_ids:
            matches = review_points_df[review_points_df["review_id"] == review_id]
            if not matches.empty:
                selected.append(matches.iloc[0])

    for _, row in review_points_df.head(3).iterrows():
        selected.append(row)

    if len(review_points_df) > 0:
        random_rows = review_points_df.sample(
            n=min(max_random_points, len(review_points_df)),
            random_state=42,
            replace=False,
        )
        for _, row in random_rows.iterrows():
            selected.append(row)

    if not selected:
        return review_points_df.head(0).copy()

    selected_df = pd.DataFrame([row.to_dict() for row in selected])
    for subset in [["review_id"], ["sample_id"], ["pixel_key"], ["row", "col"], ["lon", "lat"]]:
        if set(subset) <= set(selected_df.columns):
            return selected_df.drop_duplicates(subset=subset).reset_index(drop=True)
    return selected_df.drop_duplicates().reset_index(drop=True)


def dea_cog_url(year, band):
    return (
        "https://data.dea.ga.gov.au/derivative/"
        f"{DEA_LANDCOVER_PRODUCT}/{DEA_LANDCOVER_VERSION}/continental_mosaics/"
        f"{year}--P1Y/{DEA_LANDCOVER_PRODUCT}_mosaic_{year}--P1Y_{band}.tif"
    )


def transform_lonlat_to_dataset(src, lon, lat):
    xs, ys = transform_coords("EPSG:4326", src.crs, [float(lon)], [float(lat)])
    return xs[0], ys[0]


def clean_value(value):
    if np.ma.is_masked(value):
        return None
    value = float(value)
    if np.isnan(value):
        return None
    return int(value) if value.is_integer() else value


def majority_from_window(values):
    if np.ma.isMaskedArray(values):
        data = values.compressed()
    else:
        data = values[np.isfinite(values)]
    data = [int(v) for v in data if int(v) != 255]
    if not data:
        return None, 0, 0
    code, count = Counter(data).most_common(1)[0]
    return code, count, len(data)


def sample_dea_band(year, band, lon, lat, neighbourhood_radius=1):
    url = dea_cog_url(year, band)
    src = DATASET_CACHE.get(url)
    if src is None:
        src = rasterio.open(url)
        DATASET_CACHE[url] = src
    x, y = transform_lonlat_to_dataset(src, lon, lat)
    row, col = src.index(x, y)
    point_value = clean_value(next(src.sample([(x, y)], masked=True))[0])

    def read_majority(radius):
        row_start = max(0, row - radius)
        col_start = max(0, col - radius)
        row_stop = min(src.height, row + radius + 1)
        col_stop = min(src.width, col + radius + 1)
        window = Window(col_start, row_start, col_stop - col_start, row_stop - row_start)
        window_values = src.read(1, window=window, masked=True)
        return majority_from_window(window_values)

    majority_code_3x3, majority_count_3x3, valid_count_3x3 = read_majority(neighbourhood_radius)
    majority_code_5x5, majority_count_5x5, valid_count_5x5 = read_majority(2)
    return {
        "point_code": point_value,
        "majority_code_3x3": majority_code_3x3,
        "majority_count_3x3": majority_count_3x3,
        "valid_neighbour_count_3x3": valid_count_3x3,
        "majority_code_5x5": majority_code_5x5,
        "majority_count_5x5": majority_count_5x5,
        "valid_neighbour_count_5x5": valid_count_5x5,
        "dea_row": int(row),
        "dea_col": int(col),
        "dea_resolution_m": abs(float(src.transform.a)),
    }


def run_coordinate_diagnostics(review_points_df, years):
    diagnostic_points = selected_diagnostic_points(review_points_df)
    records = []

    global DATASET_CACHE
    DATASET_CACHE = {}
    env = rasterio.Env(**DEA_RASTER_ENV_OPTIONS)
    env.__enter__()
    try:
        for _, point in diagnostic_points.iterrows():
            for year in years:
                record = {
                    "review_id": point.get("review_id"),
                    "sample_id": point.get("sample_id"),
                    "pixel_key": point.get("pixel_key"),
                    "category": point.get("category"),
                    "lon": point.get("lon"),
                    "lat": point.get("lat"),
                    "year": year,
                }
                try:
                    l3 = sample_dea_band(year, "level3", point["lon"], point["lat"])
                    l4 = sample_dea_band(year, "level4", point["lon"], point["lat"])
                    l3_effective = effective_class(
                        l3["point_code"], l3["majority_code_3x3"], l3["majority_code_5x5"], LEVEL3_LABELS
                    )
                    l4_effective = effective_class(
                        l4["point_code"], l4["majority_code_3x3"], l4["majority_code_5x5"], LEVEL4_LABELS
                    )
                    record.update(
                        ok=True,
                        dea_level3_code=l3["point_code"],
                        dea_level3_label=label_for(l3["point_code"], LEVEL3_LABELS),
                        dea_level3_majority_code_3x3=l3["majority_code_3x3"],
                        dea_level3_majority_label_3x3=label_for(l3["majority_code_3x3"], LEVEL3_LABELS),
                        dea_level3_majority_code_5x5=l3["majority_code_5x5"],
                        dea_level3_majority_label_5x5=label_for(l3["majority_code_5x5"], LEVEL3_LABELS),
                        dea_level3_effective_label=l3_effective["label"],
                        dea_level3_effective_source=l3_effective["source"],
                        dea_level3_has_effective_class=l3_effective["has_class"],
                        dea_level4_code=l4["point_code"],
                        dea_level4_label=label_for(l4["point_code"], LEVEL4_LABELS),
                        dea_level4_effective_label=l4_effective["label"],
                        dea_level4_effective_source=l4_effective["source"],
                        dea_level4_has_effective_class=l4_effective["has_class"],
                        dea_row=l3["dea_row"],
                        dea_col=l3["dea_col"],
                        dea_resolution_m=l3["dea_resolution_m"],
                    )
                except Exception as exc:
                    record.update(ok=False, **exception_details(exc))
                records.append(record)
    finally:
        for src in DATASET_CACHE.values():
            src.close()
        DATASET_CACHE.clear()
        env.__exit__(None, None, None)

    return pd.DataFrame(records)


def effective_source_counts(long_df):
    rows = []
    source_order = ["exact_point", "majority_3x3", "majority_5x5", "missing"]
    for level in ["level3", "level4"]:
        source_col = f"dea_{level}_effective_source"
        if source_col not in long_df.columns:
            continue
        for source in source_order:
            rows.append(
                {
                    "dea_level": level,
                    "category": "ALL",
                    "effective_source": source,
                    "point_year_records": int((long_df[source_col] == source).sum()),
                }
            )
        by_category = (
            long_df.groupby(["category", source_col], dropna=False)
            .size()
            .reset_index(name="point_year_records")
            .rename(columns={source_col: "effective_source"})
        )
        by_category.insert(0, "dea_level", level)
        rows.extend(by_category.to_dict("records"))
    return pd.DataFrame(rows)


LEVEL3_YEAR_COLS = [f"dea_level3_effective_label_{year}" for year in YEARS]
LEVEL4_YEAR_COLS = [f"dea_level4_effective_label_{year}" for year in YEARS]


def safe_bool(series):
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(bool)


def is_missing_label(value):
    return pd.isna(value) or str(value).strip() in {"", "Missing", "None", "nan"}


def sequence_from_row(row, columns):
    return [row.get(col) if not is_missing_label(row.get(col)) else None for col in columns]


def first_valid(values):
    for value in values:
        if not is_missing_label(value):
            return value
    return None


def last_valid(values):
    for value in reversed(values):
        if not is_missing_label(value):
            return value
    return None


def classify_level3_sequence(values):
    values = [value if not is_missing_label(value) else None for value in values]
    valid = [value for value in values if value is not None]
    if not valid:
        return "missing_sequence"

    first = valid[0]
    last = valid[-1]
    unique = set(valid)
    if len(unique) == 1:
        compact = (
            str(first)
            .replace(" Terrestrial Vegetation", "")
            .replace("Natural ", "natural_")
            .replace("Cultivated ", "cultivated_")
            .replace("Artificial Surface", "artificial_surface")
            .replace("Natural Bare Surface", "natural_bare_surface")
            .replace("Natural Aquatic Vegetation", "natural_aquatic_vegetation")
            .replace("Water", "water")
            .replace(" ", "_")
            .lower()
        )
        return f"stable_{compact}"

    if first == last:
        return "temporary_or_return_to_start"
    if first != "Artificial Surface" and last == "Artificial Surface":
        return "transition_to_artificial_surface"
    if first == "Artificial Surface" and last != "Artificial Surface":
        return "transition_from_artificial_surface"
    if first == "Natural Terrestrial Vegetation" and last == "Cultivated Terrestrial Vegetation":
        return "natural_to_cultivated_vegetation"
    if first == "Cultivated Terrestrial Vegetation" and last == "Natural Terrestrial Vegetation":
        return "cultivated_to_natural_vegetation"
    if unique & {"Water", "Natural Aquatic Vegetation", "Natural Bare Surface"}:
        return "water_aquatic_or_bare_involved"
    return "other_level3_change"


def enrich_sequences(probe_df):
    enriched_rows = []
    for _, row in probe_df.iterrows():
        l3_values = sequence_from_row(row, LEVEL3_YEAR_COLS)
        l4_values = sequence_from_row(row, LEVEL4_YEAR_COLS)
        l3_first_change = first_change_year(l3_values, YEARS)
        l4_first_change = first_change_year(l4_values, YEARS)
        max_change_year = row.get("max_change_year")
        first_hotspot_year = row.get("first_hotspot_year")

        match_max_year = (
            pd.notna(l3_first_change)
            and pd.notna(max_change_year)
            and abs(int(l3_first_change) - int(max_change_year)) <= 1
        )
        match_hotspot_year = (
            pd.notna(l3_first_change)
            and pd.notna(first_hotspot_year)
            and abs(int(l3_first_change) - int(first_hotspot_year)) <= 1
        )

        enriched = row.to_dict()
        l3_2017 = first_valid(l3_values)
        l3_2024 = last_valid(l3_values)
        l4_2017 = first_valid(l4_values)
        l4_2024 = last_valid(l4_values)
        enriched.update(
            {
                "level3_2017": l3_2017,
                "level3_2024": l3_2024,
                "level4_2017": l4_2017,
                "level4_2024": l4_2024,
                "level3_transition_2017_2024": f"{l3_2017} -> {l3_2024}",
                "level4_transition_2017_2024": f"{l4_2017} -> {l4_2024}",
                "level3_sequence_type": classify_level3_sequence(l3_values),
                "level3_first_change_year_recomputed": l3_first_change,
                "level4_first_change_year_recomputed": l4_first_change,
                "level3_adjacent_change_count_recomputed": count_adjacent_changes(l3_values),
                "level4_adjacent_change_count_recomputed": count_adjacent_changes(l4_values),
                "level3_complete_sequence_recomputed": all(not is_missing_label(v) for v in l3_values),
                "level4_complete_sequence_recomputed": all(not is_missing_label(v) for v in l4_values),
                "level3_first_change_matches_embedding_max_year_pm1": bool(match_max_year),
                "level3_first_change_matches_first_hotspot_year_pm1": bool(match_hotspot_year),
                "level3_sequence": sequence_string(l3_values),
                "level4_sequence": sequence_string(l4_values),
                "google_maps_link": f"https://www.google.com/maps?q={row.get('lat')},{row.get('lon')}",
            }
        )
        enriched_rows.append(enriched)
    return pd.DataFrame(enriched_rows)


def summarize_categories(enriched_df):
    grouped = enriched_df.groupby("category", dropna=False)
    summary = grouped.agg(
        points=("category", "count"),
        level3_changed_points=("dea_level3_class_changed", lambda s: int(safe_bool(s).sum())),
        level4_changed_points=("dea_level4_class_changed", lambda s: int(safe_bool(s).sum())),
        level3_complete_points=("level3_complete_sequence_recomputed", lambda s: int(safe_bool(s).sum())),
        level3_mean_adjacent_changes=("level3_adjacent_change_count_recomputed", "mean"),
        level4_mean_adjacent_changes=("level4_adjacent_change_count_recomputed", "mean"),
        first_dea_change_matches_max_year_pm1=(
            "level3_first_change_matches_embedding_max_year_pm1",
            lambda s: int(safe_bool(s).sum()),
        ),
        first_dea_change_matches_hotspot_year_pm1=(
            "level3_first_change_matches_first_hotspot_year_pm1",
            lambda s: int(safe_bool(s).sum()),
        ),
        mean_endpoint_change=("endpoint_change", "mean"),
        median_endpoint_change=("endpoint_change", "median"),
        mean_persistence_count=("persistence_count", "mean"),
        mean_variance_annual_change=("variance_annual_change", "mean"),
        mean_slope_annual_change=("slope_annual_change", "mean"),
    ).reset_index()
    summary["level3_changed_share"] = summary["level3_changed_points"] / summary["points"]
    summary["level4_changed_share"] = summary["level4_changed_points"] / summary["points"]
    summary["level3_complete_share"] = summary["level3_complete_points"] / summary["points"]
    summary["first_dea_change_matches_max_year_pm1_share"] = (
        summary["first_dea_change_matches_max_year_pm1"] / summary["points"]
    )
    summary["first_dea_change_matches_hotspot_year_pm1_share"] = (
        summary["first_dea_change_matches_hotspot_year_pm1"] / summary["points"]
    )
    return summary.sort_values("level3_changed_share", ascending=False)


def high_confidence_candidates(enriched_df, limit=250):
    signal_categories = {
        "endpoint_hotspot",
        "persistent_ge2",
        "persistent_ge3",
        "high_variance",
        "positive_slope",
        "negative_slope",
        "sudden_candidate",
        "temporary_or_recovery_candidate",
    }
    df = enriched_df.copy()
    score = pd.Series(0, index=df.index, dtype=float)
    score += safe_bool(df["level3_complete_sequence_recomputed"]).astype(int) * 2
    score += safe_bool(df["dea_level3_class_changed"]).astype(int) * 2
    score += df["category"].isin(signal_categories).astype(int)
    score += safe_bool(df["level3_first_change_matches_embedding_max_year_pm1"]).astype(int) * 2
    score += safe_bool(df["level3_first_change_matches_first_hotspot_year_pm1"]).astype(int) * 2
    score += df["level3_sequence_type"].isin(
        [
            "transition_to_artificial_surface",
            "natural_to_cultivated_vegetation",
            "cultivated_to_natural_vegetation",
            "water_aquatic_or_bare_involved",
        ]
    ).astype(int)
    df["review_priority_score"] = score
    columns = [
        "review_priority_score",
        "sample_id",
        "category",
        "lon",
        "lat",
        "google_maps_link",
        "endpoint_change",
        "persistence_count",
        "variance_annual_change",
        "slope_annual_change",
        "max_change_year",
        "first_hotspot_year",
        "level3_2017",
        "level3_2024",
        "level3_transition_2017_2024",
        "level3_sequence_type",
        "level3_first_change_year_recomputed",
        "level3_first_change_matches_embedding_max_year_pm1",
        "level3_first_change_matches_first_hotspot_year_pm1",
        "level3_sequence",
        "level4_sequence",
    ]
    optional_columns = ["review_id", "selection_method"]
    columns = [*optional_columns, *columns]
    columns = [col for col in columns if col in df.columns]
    return (
        df.sort_values(
            ["review_priority_score", "endpoint_change", "persistence_count", "variance_annual_change"],
            ascending=[False, False, False, False],
        )[columns]
        .head(limit)
        .reset_index(drop=True)
    )


def markdown_table(df):
    if df.empty:
        return "_No rows._"
    table = df.copy()
    for col in table.columns:
        if pd.api.types.is_float_dtype(table[col]):
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
        else:
            table[col] = table[col].map(lambda value: "" if pd.isna(value) else str(value))
    header = "| " + " | ".join(table.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in table.to_numpy(dtype=str)]
    return "\n".join([header, divider, *rows])


def write_interpretation_report(output_path, enriched_df, category_summary, transition_counts, sequence_type_counts, alignment):
    total = len(enriched_df)
    l3_changed = int(safe_bool(enriched_df["dea_level3_class_changed"]).sum())
    l4_changed = int(safe_bool(enriched_df["dea_level4_class_changed"]).sum())
    complete = int(safe_bool(enriched_df["level3_complete_sequence_recomputed"]).sum())
    lines = [
        "# Bass Coast Phase 3 DEA Land Cover Pipeline Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Purpose",
        "",
        "This local Phase 3 pipeline attaches DEA Land Cover histories to sampled embedding-change points and summarizes the resulting DEA sequence patterns. It replaces the earlier separate Phase 3A and Phase 3B scripts.",
        "",
        "## Coverage",
        "",
        f"- Points processed: {total}",
        f"- Complete DEA Level 3 sequences: {complete}/{total} ({complete / total:.1%})",
        f"- DEA Level 3 changed points: {l3_changed}/{total} ({l3_changed / total:.1%})",
        f"- DEA Level 4 changed points: {l4_changed}/{total} ({l4_changed / total:.1%})",
        "",
        "## Category-Level DEA Agreement",
        "",
        markdown_table(category_summary[["category", "points", "level3_changed_points", "level3_changed_share", "level4_changed_points", "level4_changed_share"]]),
        "",
        "## Most Common 2017-2024 Level 3 Transitions",
        "",
        markdown_table(transition_counts.head(12)),
        "",
        "## Most Common Level 3 Sequence Types",
        "",
        markdown_table(sequence_type_counts.head(12)),
        "",
        "## First DEA Change Timing Alignment",
        "",
        markdown_table(alignment),
        "",
        "## Interpretation",
        "",
        "A high Level 3 change share in embedding-change categories compared with stable controls indicates that the embedding categories are enriched for real DEA-observed land-cover transitions. This is a validation signal, not a strict accuracy score, because DEA is a broad categorical product and does not capture every possible ecosystem or condition change.",
        "",
        "## Position For Next Phase",
        "",
        "This script is built to run either the 900-point review table or the larger Phase 2 sampled table. For the next phase, use the same local pipeline with chunk/checkpoint support on the larger sampled table, not all 191 million raster pixels.",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def interpret_sequences(probe_df, long_df, output_dir):
    enriched_df = enrich_sequences(probe_df)
    category_summary = summarize_categories(enriched_df)
    transition_counts = (
        enriched_df.groupby(["level3_2017", "level3_2024", "level3_transition_2017_2024"], dropna=False)
        .size()
        .reset_index(name="points")
        .sort_values("points", ascending=False)
    )
    sequence_type_counts = (
        enriched_df.groupby(["level3_sequence_type"], dropna=False)
        .size()
        .reset_index(name="points")
        .sort_values("points", ascending=False)
    )
    sequence_type_counts_by_category = (
        enriched_df.groupby(["category", "level3_sequence_type"], dropna=False)
        .size()
        .reset_index(name="points")
        .sort_values(["category", "points"], ascending=[True, False])
    )
    top_sequences_by_category = (
        enriched_df.groupby(["category", "level3_sequence"], dropna=False)
        .size()
        .reset_index(name="points")
        .sort_values(["category", "points"], ascending=[True, False])
    )
    alignment = (
        enriched_df.groupby("category", dropna=False)
        .agg(
            points=("category", "count"),
            level3_changed_points=("dea_level3_class_changed", lambda s: int(safe_bool(s).sum())),
            match_max_year_pm1=("level3_first_change_matches_embedding_max_year_pm1", lambda s: int(safe_bool(s).sum())),
            match_first_hotspot_year_pm1=(
                "level3_first_change_matches_first_hotspot_year_pm1",
                lambda s: int(safe_bool(s).sum()),
            ),
        )
        .reset_index()
    )
    alignment["match_max_year_pm1_share_of_changed"] = (
        alignment["match_max_year_pm1"] / alignment["level3_changed_points"].replace(0, np.nan)
    )
    alignment["match_first_hotspot_year_pm1_share_of_changed"] = (
        alignment["match_first_hotspot_year_pm1"] / alignment["level3_changed_points"].replace(0, np.nan)
    )
    first_change_year_counts = (
        enriched_df.groupby(["category", "level3_first_change_year_recomputed"], dropna=False)
        .size()
        .reset_index(name="points")
        .sort_values(["category", "level3_first_change_year_recomputed"])
    )
    label_counts = []
    for year, col in zip(YEARS, LEVEL3_YEAR_COLS):
        year_counts = enriched_df[col].value_counts(dropna=False).rename_axis("level3_label").reset_index(name="points")
        year_counts.insert(0, "year", year)
        label_counts.append(year_counts)
    label_counts_by_year = pd.concat(label_counts, ignore_index=True)
    candidates = high_confidence_candidates(enriched_df)

    outputs = {
        "basscoast_phase3_dea_enriched_points.csv": enriched_df,
        "basscoast_phase3_category_validation_summary.csv": category_summary,
        "basscoast_phase3_level3_transition_counts.csv": transition_counts,
        "basscoast_phase3_sequence_type_counts.csv": sequence_type_counts,
        "basscoast_phase3_sequence_type_counts_by_category.csv": sequence_type_counts_by_category,
        "basscoast_phase3_top_level3_sequences_by_category.csv": top_sequences_by_category,
        "basscoast_phase3_first_change_alignment.csv": alignment,
        "basscoast_phase3_first_change_year_counts.csv": first_change_year_counts,
        "basscoast_phase3_level3_label_counts_by_year.csv": label_counts_by_year,
        "basscoast_phase3_high_confidence_review_candidates.csv": candidates,
    }
    for filename, df in outputs.items():
        df.to_csv(output_dir / filename, index=False)

    report_path = output_dir / "basscoast_phase3_dea_pipeline_report.md"
    write_interpretation_report(report_path, enriched_df, category_summary, transition_counts, sequence_type_counts, alignment)
    return outputs, report_path


def build_probe(review_points_df, years):
    long_records = []
    wide_records = []
    warning_records = []

    global DATASET_CACHE
    DATASET_CACHE = {}
    env = rasterio.Env(**DEA_RASTER_ENV_OPTIONS)
    env.__enter__()
    try:
        for idx, point in review_points_df.iterrows():
            if idx == 0 or (idx + 1) % 50 == 0 or idx + 1 == len(review_points_df):
                print(f"Processing review point {idx + 1}/{len(review_points_df)}")
            wide = point.to_dict()
            sequence_l3 = []
            sequence_l4 = []
            exact_sequence_l3 = []
            exact_sequence_l4 = []
            majority_sequence_l3 = []
            majority_sequence_l4 = []
            agreement_flags_l3 = []
            agreement_flags_l4 = []

            for year in years:
                record = {
                    "review_id": point.get("review_id"),
                    "sample_id": point.get("sample_id"),
                    "pixel_key": point.get("pixel_key"),
                    "category": point.get("category"),
                    "lon": point.get("lon"),
                    "lat": point.get("lat"),
                    "year": year,
                }
                try:
                    l3 = sample_dea_band(year, "level3", point["lon"], point["lat"])
                    l4 = sample_dea_band(year, "level4", point["lon"], point["lat"])
                    l3_label = label_for(l3["point_code"], LEVEL3_LABELS)
                    l4_label = label_for(l4["point_code"], LEVEL4_LABELS)
                    l3_majority_label_3x3 = label_for(l3["majority_code_3x3"], LEVEL3_LABELS)
                    l4_majority_label_3x3 = label_for(l4["majority_code_3x3"], LEVEL4_LABELS)
                    l3_majority_label_5x5 = label_for(l3["majority_code_5x5"], LEVEL3_LABELS)
                    l4_majority_label_5x5 = label_for(l4["majority_code_5x5"], LEVEL4_LABELS)
                    l3_effective = effective_class(
                        l3["point_code"], l3["majority_code_3x3"], l3["majority_code_5x5"], LEVEL3_LABELS
                    )
                    l4_effective = effective_class(
                        l4["point_code"], l4["majority_code_3x3"], l4["majority_code_5x5"], LEVEL4_LABELS
                    )
                    l3_agree = (
                        is_valid_dea_code(l3["point_code"])
                        and is_valid_dea_code(l3["majority_code_3x3"])
                        and int(l3["point_code"]) == int(l3["majority_code_3x3"])
                    )
                    l4_agree = (
                        is_valid_dea_code(l4["point_code"])
                        and is_valid_dea_code(l4["majority_code_3x3"])
                        and int(l4["point_code"]) == int(l4["majority_code_3x3"])
                    )

                    record.update(
                        ok=True,
                        read_success=True,
                        dea_level3_code=l3["point_code"],
                        dea_level3_label=l3_label,
                        dea_level3_has_point_class=is_valid_dea_code(l3["point_code"]),
                        dea_level3_majority_code_3x3=l3["majority_code_3x3"],
                        dea_level3_majority_label_3x3=l3_majority_label_3x3,
                        dea_level3_majority_code_5x5=l3["majority_code_5x5"],
                        dea_level3_majority_label_5x5=l3_majority_label_5x5,
                        dea_level3_effective_code=l3_effective["code"],
                        dea_level3_effective_label=l3_effective["label"],
                        dea_level3_effective_source=l3_effective["source"],
                        dea_level3_has_effective_class=l3_effective["has_class"],
                        dea_level3_point_majority_agree=l3_agree,
                        dea_level4_code=l4["point_code"],
                        dea_level4_label=l4_label,
                        dea_level4_has_point_class=is_valid_dea_code(l4["point_code"]),
                        dea_level4_majority_code_3x3=l4["majority_code_3x3"],
                        dea_level4_majority_label_3x3=l4_majority_label_3x3,
                        dea_level4_majority_code_5x5=l4["majority_code_5x5"],
                        dea_level4_majority_label_5x5=l4_majority_label_5x5,
                        dea_level4_effective_code=l4_effective["code"],
                        dea_level4_effective_label=l4_effective["label"],
                        dea_level4_effective_source=l4_effective["source"],
                        dea_level4_has_effective_class=l4_effective["has_class"],
                        dea_level4_point_majority_agree=l4_agree,
                        dea_neighbour_valid_count_3x3=l3["valid_neighbour_count_3x3"],
                        dea_neighbour_valid_count_5x5=l3["valid_neighbour_count_5x5"],
                        dea_row=l3["dea_row"],
                        dea_col=l3["dea_col"],
                        dea_resolution_m=l3["dea_resolution_m"],
                    )
                    sequence_l3.append(l3_effective["label"])
                    sequence_l4.append(l4_effective["label"])
                    exact_sequence_l3.append(l3_label)
                    exact_sequence_l4.append(l4_label)
                    majority_sequence_l3.append(l3_majority_label_3x3)
                    majority_sequence_l4.append(l4_majority_label_3x3)
                    agreement_flags_l3.append(bool(l3_agree))
                    agreement_flags_l4.append(bool(l4_agree))

                    for prefix, value in [
                        ("dea_level3_code", l3["point_code"]),
                        ("dea_level3_label", l3_label),
                        ("dea_level3_has_point_class", is_valid_dea_code(l3["point_code"])),
                        ("dea_level3_majority_code_3x3", l3["majority_code_3x3"]),
                        ("dea_level3_majority_label_3x3", l3_majority_label_3x3),
                        ("dea_level3_majority_code_5x5", l3["majority_code_5x5"]),
                        ("dea_level3_majority_label_5x5", l3_majority_label_5x5),
                        ("dea_level3_effective_code", l3_effective["code"]),
                        ("dea_level3_effective_label", l3_effective["label"]),
                        ("dea_level3_effective_source", l3_effective["source"]),
                        ("dea_level3_has_effective_class", l3_effective["has_class"]),
                        ("dea_level3_point_majority_agree", l3_agree),
                        ("dea_level4_code", l4["point_code"]),
                        ("dea_level4_label", l4_label),
                        ("dea_level4_has_point_class", is_valid_dea_code(l4["point_code"])),
                        ("dea_level4_majority_code_3x3", l4["majority_code_3x3"]),
                        ("dea_level4_majority_label_3x3", l4_majority_label_3x3),
                        ("dea_level4_majority_code_5x5", l4["majority_code_5x5"]),
                        ("dea_level4_majority_label_5x5", l4_majority_label_5x5),
                        ("dea_level4_effective_code", l4_effective["code"]),
                        ("dea_level4_effective_label", l4_effective["label"]),
                        ("dea_level4_effective_source", l4_effective["source"]),
                        ("dea_level4_has_effective_class", l4_effective["has_class"]),
                        ("dea_level4_point_majority_agree", l4_agree),
                    ]:
                        wide[f"{prefix}_{year}"] = value
                except Exception as exc:
                    details = exception_details(exc)
                    warning_record = {
                        "review_id": point.get("review_id"),
                        "sample_id": point.get("sample_id"),
                        "pixel_key": point.get("pixel_key"),
                        "category": point.get("category"),
                        "lon": point.get("lon"),
                        "lat": point.get("lat"),
                        "year": year,
                        **details,
                    }
                    warning_records.append(warning_record)
                    record.update(ok=False, read_success=False, error=details["exception_message"], **details)
                    sequence_l3.append(None)
                    sequence_l4.append(None)
                    exact_sequence_l3.append(None)
                    exact_sequence_l4.append(None)
                    majority_sequence_l3.append(None)
                    majority_sequence_l4.append(None)
                long_records.append(record)

            wide["dea_level3_sequence"] = sequence_string(exact_sequence_l3)
            wide["dea_level4_sequence"] = sequence_string(exact_sequence_l4)
            wide["dea_level3_majority_sequence_3x3"] = sequence_string(majority_sequence_l3)
            wide["dea_level4_majority_sequence_3x3"] = sequence_string(majority_sequence_l4)
            wide["dea_level3_effective_sequence"] = sequence_string(sequence_l3)
            wide["dea_level4_effective_sequence"] = sequence_string(sequence_l4)
            wide["dea_level3_valid_year_count"] = sum(pd.notna(v) for v in sequence_l3)
            wide["dea_level4_valid_year_count"] = sum(pd.notna(v) for v in sequence_l4)
            wide["dea_level3_complete_sequence"] = wide["dea_level3_valid_year_count"] == len(years)
            wide["dea_level4_complete_sequence"] = wide["dea_level4_valid_year_count"] == len(years)
            wide["dea_level3_class_changed"] = sequence_changed(sequence_l3)
            wide["dea_level4_class_changed"] = sequence_changed(sequence_l4)
            wide["dea_level3_number_of_class_changes"] = count_adjacent_changes(sequence_l3)
            wide["dea_level4_number_of_class_changes"] = count_adjacent_changes(sequence_l4)
            wide["dea_level3_boundary_uncertain_any"] = not all(agreement_flags_l3) if agreement_flags_l3 else True
            wide["dea_level4_boundary_uncertain_any"] = not all(agreement_flags_l4) if agreement_flags_l4 else True
            wide["dea_level3_first_change_year"] = first_change_year(sequence_l3, years)
            wide["dea_level4_first_change_year"] = first_change_year(sequence_l4, years)
            wide_records.append(wide)
    finally:
        for src in DATASET_CACHE.values():
            src.close()
        DATASET_CACHE.clear()
        env.__exit__(None, None, None)

    return pd.DataFrame(wide_records), pd.DataFrame(long_records), warning_records


def load_or_build_chunk(chunk_df, chunk_idx, chunk_dir, resume):
    probe_path = chunk_dir / f"chunk_{chunk_idx:05d}_probe.csv"
    long_path = chunk_dir / f"chunk_{chunk_idx:05d}_long.csv"
    warnings_path = chunk_dir / f"chunk_{chunk_idx:05d}_warnings.csv"
    if resume and probe_path.exists() and long_path.exists() and warnings_path.exists():
        print(f"Reusing checkpoint chunk {chunk_idx:05d}")
        return (
            pd.read_csv(probe_path),
            pd.read_csv(long_path),
            pd.read_csv(warnings_path).to_dict("records"),
        )

    print(f"Processing chunk {chunk_idx:05d} ({len(chunk_df)} points)")
    probe_chunk, long_chunk, warnings_chunk = build_probe(chunk_df.reset_index(drop=True), YEARS)
    probe_chunk.to_csv(probe_path, index=False)
    long_chunk.to_csv(long_path, index=False)
    pd.DataFrame(warnings_chunk, columns=WARNING_COLUMNS).to_csv(warnings_path, index=False)
    return probe_chunk, long_chunk, warnings_chunk


def write_pipeline_summary(
    output_dir,
    input_path,
    points_df,
    probe_df,
    long_df,
    warning_records,
    source_counts_df,
    runtime_df,
    diagnostic_df,
    coverage_threshold,
    chunk_size,
):
    summary_csv = output_dir / "basscoast_phase3_pipeline_summary.csv"
    ok_series = long_df["ok"].fillna(False).astype(bool) if "ok" in long_df else pd.Series(dtype=bool)
    level3_point_valid = long_df["dea_level3_has_point_class"].fillna(False).astype(bool)
    level4_point_valid = long_df["dea_level4_has_point_class"].fillna(False).astype(bool)
    level3_effective_valid = long_df["dea_level3_has_effective_class"].fillna(False).astype(bool)
    level4_effective_valid = long_df["dea_level4_has_effective_class"].fillna(False).astype(bool)
    total_point_year_records = len(long_df)
    level3_complete_sequences = int(probe_df["dea_level3_complete_sequence"].fillna(False).sum())
    level4_complete_sequences = int(probe_df["dea_level4_complete_sequence"].fillna(False).sum())
    level3_complete_share = level3_complete_sequences / len(probe_df) if len(probe_df) else 0
    level4_complete_share = level4_complete_sequences / len(probe_df) if len(probe_df) else 0
    coverage_passed = level3_complete_share >= coverage_threshold
    summary_df = pd.DataFrame(
        [
            {"item": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
            {"item": "input", "value": str(input_path)},
            {"item": "total_points", "value": len(points_df)},
            {"item": "total_point_year_records", "value": total_point_year_records},
            {"item": "chunk_size", "value": chunk_size},
            {"item": "successful_year_records", "value": int(ok_series.sum()) if "ok" in long_df else 0},
            {"item": "failed_year_records", "value": int((~ok_series).sum()) if "ok" in long_df else len(long_df)},
            {"item": "level3_point_valid_year_records", "value": int(level3_point_valid.sum())},
            {"item": "level4_point_valid_year_records", "value": int(level4_point_valid.sum())},
            {"item": "level3_effective_valid_year_records", "value": int(level3_effective_valid.sum())},
            {"item": "level4_effective_valid_year_records", "value": int(level4_effective_valid.sum())},
            {"item": "level3_complete_effective_sequences", "value": level3_complete_sequences},
            {"item": "level4_complete_effective_sequences", "value": level4_complete_sequences},
            {"item": "level3_complete_effective_sequence_share", "value": level3_complete_share},
            {"item": "level4_complete_effective_sequence_share", "value": level4_complete_share},
            {"item": "level3_changed_points", "value": int(probe_df["dea_level3_class_changed"].fillna(False).sum())},
            {"item": "level4_changed_points", "value": int(probe_df["dea_level4_class_changed"].fillna(False).sum())},
            {"item": "coverage_threshold", "value": coverage_threshold},
            {"item": "coverage_passed", "value": coverage_passed},
            {"item": "warnings", "value": len(warning_records)},
            {"item": "dea_probe_csv", "value": str(output_dir / "basscoast_phase3_dea_probe.csv")},
            {"item": "dea_long_csv", "value": str(output_dir / "basscoast_phase3_dea_long.csv")},
            {"item": "warnings_csv", "value": str(output_dir / "basscoast_phase3_warnings.csv")},
            {"item": "effective_source_counts_csv", "value": str(output_dir / "basscoast_phase3_effective_source_counts.csv")},
            {"item": "runtime_diagnostics_csv", "value": str(output_dir / "basscoast_phase3_runtime_diagnostics.csv")},
            {"item": "coordinate_diagnostics_csv", "value": str(output_dir / "basscoast_phase3_sample_coordinate_diagnostics.csv")},
        ]
    )
    summary_df.to_csv(summary_csv, index=False)
    return summary_df, coverage_passed, level3_complete_share


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="BassCoast_Phase2_Pixel_Sampling_outputs/basscoast_phase2b_review_points.csv")
    parser.add_argument("--output-dir", default="BassCoast_Phase3_DEA_LandCover_Pipeline_outputs")
    parser.add_argument("--max-points", type=int, default=0, help="Use 0 for all points; use a positive integer for a smoke test.")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--coverage-threshold", type=float, default=0.8)
    parser.add_argument("--resume", action="store_true", help="Reuse completed chunk checkpoints when present.")
    parser.add_argument("--force", action="store_true", help="Remove existing output directory before running.")
    parser.add_argument("--skip-coordinate-diagnostics", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    if args.force and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    points_df = pd.read_csv(input_path)
    if args.max_points and args.max_points > 0:
        points_df = points_df.head(args.max_points).copy()
    if "sample_id" not in points_df.columns:
        points_df.insert(0, "sample_id", np.arange(1, len(points_df) + 1))
    if "pixel_key" not in points_df.columns and {"row", "col"} <= set(points_df.columns):
        points_df["pixel_key"] = points_df["row"].astype(str) + "_" + points_df["col"].astype(str)

    runtime_df = pd.DataFrame(runtime_diagnostics())
    diagnostic_df = pd.DataFrame()
    if not args.skip_coordinate_diagnostics:
        print("Running deterministic coordinate diagnostics...")
        diagnostic_df = run_coordinate_diagnostics(points_df, YEARS)

    probe_chunks = []
    long_chunks = []
    warning_records = []
    chunk_size = max(1, args.chunk_size)
    for chunk_idx, start in enumerate(range(0, len(points_df), chunk_size)):
        chunk_df = points_df.iloc[start : start + chunk_size].copy()
        probe_chunk, long_chunk, warnings_chunk = load_or_build_chunk(chunk_df, chunk_idx, checkpoint_dir, args.resume)
        probe_chunks.append(probe_chunk)
        long_chunks.append(long_chunk)
        warning_records.extend(warnings_chunk)

    probe_df = pd.concat(probe_chunks, ignore_index=True) if probe_chunks else pd.DataFrame()
    long_df = pd.concat(long_chunks, ignore_index=True) if long_chunks else pd.DataFrame()
    source_counts_df = effective_source_counts(long_df)

    probe_csv = output_dir / "basscoast_phase3_dea_probe.csv"
    long_csv = output_dir / "basscoast_phase3_dea_long.csv"
    warnings_csv = output_dir / "basscoast_phase3_warnings.csv"
    source_counts_csv = output_dir / "basscoast_phase3_effective_source_counts.csv"
    runtime_csv = output_dir / "basscoast_phase3_runtime_diagnostics.csv"
    coordinate_diagnostics_csv = output_dir / "basscoast_phase3_sample_coordinate_diagnostics.csv"

    probe_df.to_csv(probe_csv, index=False)
    long_df.to_csv(long_csv, index=False)
    pd.DataFrame(warning_records, columns=WARNING_COLUMNS).to_csv(warnings_csv, index=False)
    source_counts_df.to_csv(source_counts_csv, index=False)
    runtime_df.to_csv(runtime_csv, index=False)
    diagnostic_df.to_csv(coordinate_diagnostics_csv, index=False)

    interpretation_outputs, report_path = interpret_sequences(probe_df, long_df, output_dir)
    summary_df, coverage_passed, level3_complete_share = write_pipeline_summary(
        output_dir,
        input_path,
        points_df,
        probe_df,
        long_df,
        warning_records,
        source_counts_df,
        runtime_df,
        diagnostic_df,
        args.coverage_threshold,
        chunk_size,
    )

    print(f"Saved merged Phase 3 outputs to: {output_dir}")
    print(f"Pipeline summary: {output_dir / 'basscoast_phase3_pipeline_summary.csv'}")
    print(f"Report: {report_path}")
    print("\nEffective source counts:")
    print(source_counts_df[source_counts_df["category"] == "ALL"].to_string(index=False))
    print(f"\nLevel 3 complete sequence share: {level3_complete_share:.1%}")
    print(f"Coverage passed: {coverage_passed}")
    print("\nCategory validation summary:")
    category_summary = interpretation_outputs["basscoast_phase3_category_validation_summary.csv"]
    display_cols = [
        "category",
        "points",
        "level3_changed_points",
        "level3_changed_share",
        "level4_changed_points",
        "level4_changed_share",
    ]
    print(category_summary[display_cols].to_string(index=False))


if __name__ == "__main__":
    main()
