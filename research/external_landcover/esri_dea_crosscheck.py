#!/usr/bin/env python3
"""
Cross-check Esri Annual Land Cover against completed DEA Land Cover histories.

The default run uses the 900 Phase 2B review points and the completed Phase 3
DEA output. It samples the Esri class at each review coordinate and at nine
locations spanning the corresponding 30 m DEA pixel. Requests are batched and
checkpointed so an interrupted run can resume without repeating completed work.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(".cache").resolve()))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy
from rasterio.warp import transform as transform_coords


YEARS = list(range(2017, 2025))
ESRI_SERVICE_URL = (
    "https://ic.imagery1.arcgis.com/arcgis/rest/services/"
    "Sentinel2_10m_LandCover/ImageServer/getSamples"
)
DEA_LEVEL3_COG_2017 = (
    "https://data.dea.ga.gov.au/derivative/"
    "ga_ls_landcover_class_cyear_3/2-0-0/continental_mosaics/"
    "2017--P1Y/ga_ls_landcover_class_cyear_3_mosaic_2017--P1Y_level3.tif"
)

DEFAULT_REVIEW_POINTS = (
    "data/processed/sampling/"
    "basscoast_phase2b_review_points.csv"
)
DEFAULT_DEA_LONG = (
    "data/processed/dea_sample/"
    "basscoast_phase3_dea_long.csv"
)
DEFAULT_OUTPUT_DIR = "research/outputs/esri_dea_crosscheck"

ESRI_LABELS = {
    1: "Water",
    2: "Trees",
    4: "Flooded Vegetation",
    5: "Crops",
    7: "Built Area",
    8: "Bare Ground",
    9: "Snow/Ice",
    10: "Clouds",
    11: "Rangeland",
}

DEA_FAMILIES = {
    111: "terrestrial_vegetation",
    112: "terrestrial_vegetation",
    124: "aquatic_vegetation",
    215: "artificial",
    216: "bare",
    220: "water",
}

ESRI_FAMILIES = {
    1: "water",
    2: "terrestrial_vegetation",
    4: "aquatic_vegetation",
    5: "terrestrial_vegetation",
    7: "artificial",
    8: "bare",
    9: "unavailable",
    10: "unavailable",
    11: "terrestrial_vegetation",
}

STRONG_MATCHES = {
    (220, 1),
    (215, 7),
    (216, 8),
    (111, 5),
}

BROAD_MATCHES = {
    (112, 2),
    (112, 11),
    (124, 4),
}

AMBIGUOUS_MATCHES = {
    (111, 2),
    (111, 11),
    (112, 5),
    (124, 1),
    (220, 4),
}

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

PALETTE = {
    "endpoint_hotspot": "#b33b3b",
    "persistent_ge2": "#8a5a24",
    "persistent_ge3": "#5f4528",
    "high_variance": "#bf7a1a",
    "positive_slope": "#25875f",
    "negative_slope": "#4d6ea8",
    "sudden_candidate": "#a04c85",
    "temporary_or_recovery_candidate": "#6d5aa7",
    "stable_control": "#667078",
}

DEA_RASTER_ENV_OPTIONS = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_VERSION": "2",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-points", default=DEFAULT_REVIEW_POINTS)
    parser.add_argument("--dea-long", default=DEFAULT_DEA_LONG)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=40,
        help="Review points per Esri request. Each point creates 10 locations.",
    )
    parser.add_argument("--max-points", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Concurrent Esri requests. Keep modest to avoid overloading the service.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Remove Phase 7 checkpoints and outputs before running.",
    )
    return parser.parse_args()


def ensure_inputs(review_path: Path, dea_path: Path) -> None:
    missing = [str(path) for path in (review_path, dea_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required input(s): " + ", ".join(missing))


def load_review_points(path: Path, max_points: int | None) -> pd.DataFrame:
    review = pd.read_csv(path)
    required = {
        "review_id",
        "sample_id",
        "pixel_key",
        "category",
        "lon",
        "lat",
    }
    missing = sorted(required - set(review.columns))
    if missing:
        raise ValueError(f"Review table is missing columns: {missing}")

    review = review.drop_duplicates(subset=["review_id"]).copy()
    review = review.sort_values("review_id").reset_index(drop=True)
    if max_points is not None:
        review = review.head(max(0, max_points)).copy()
    if review.empty:
        raise ValueError("No review points were selected.")
    return review


def load_dea_records(path: Path, review: pd.DataFrame) -> pd.DataFrame:
    required_columns = [
        "sample_id",
        "pixel_key",
        "category",
        "lon",
        "lat",
        "year",
        "ok",
        "dea_level3_effective_code",
        "dea_level3_effective_label",
        "dea_level3_effective_source",
        "dea_level4_effective_code",
        "dea_level4_effective_label",
        "dea_level4_effective_source",
        "dea_row",
        "dea_col",
        "dea_resolution_m",
    ]
    review_ids = set(review["sample_id"].astype(int))
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=required_columns, chunksize=100_000):
        chunks.append(chunk[chunk["sample_id"].isin(review_ids)])
    dea = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    key = review[["review_id", "sample_id", "pixel_key", "category"]]
    dea = dea.merge(
        key,
        on=["sample_id", "pixel_key", "category"],
        how="inner",
        validate="many_to_one",
    )
    dea = dea[dea["year"].isin(YEARS)].copy()
    dea["year"] = dea["year"].astype(int)

    expected = len(review) * len(YEARS)
    if len(dea) != expected:
        raise ValueError(
            f"DEA join produced {len(dea):,} rows; expected {expected:,}."
        )
    if dea.duplicated(["review_id", "year"]).any():
        raise ValueError("DEA records contain duplicate review_id/year rows.")
    return dea


def build_sample_locations(review: pd.DataFrame, dea: pd.DataFrame) -> pd.DataFrame:
    dea_grid = (
        dea.sort_values("year")
        .drop_duplicates("review_id")
        [["review_id", "dea_row", "dea_col"]]
    )
    points = review.merge(dea_grid, on="review_id", validate="one_to_one")

    records: list[dict[str, Any]] = []
    with rasterio.Env(**DEA_RASTER_ENV_OPTIONS):
        with rasterio.open(DEA_LEVEL3_COG_2017) as src:
            for point in points.itertuples(index=False):
                records.append(
                    {
                        "review_id": int(point.review_id),
                        "sample_id": int(point.sample_id),
                        "position_kind": "center",
                        "position_index": 0,
                        "sample_lon": float(point.lon),
                        "sample_lat": float(point.lat),
                    }
                )

                row = int(point.dea_row)
                col = int(point.dea_col)
                center_x, center_y = xy(src.transform, row, col, offset="center")
                resolution_x = abs(float(src.transform.a))
                resolution_y = abs(float(src.transform.e))

                grid_x: list[float] = []
                grid_y: list[float] = []
                for row_offset in (-1.0 / 3.0, 0.0, 1.0 / 3.0):
                    for col_offset in (-1.0 / 3.0, 0.0, 1.0 / 3.0):
                        grid_x.append(center_x + col_offset * resolution_x)
                        grid_y.append(center_y - row_offset * resolution_y)
                lons, lats = transform_coords(
                    src.crs, "EPSG:4326", grid_x, grid_y
                )
                for index, (lon, lat) in enumerate(zip(lons, lats), start=1):
                    records.append(
                        {
                            "review_id": int(point.review_id),
                            "sample_id": int(point.sample_id),
                            "position_kind": "dea_footprint",
                            "position_index": index,
                            "sample_lon": float(lon),
                            "sample_lat": float(lat),
                        }
                    )
    return pd.DataFrame(records)


def post_esri_samples(
    locations: pd.DataFrame,
    timeout: int,
    retries: int,
) -> list[dict[str, Any]]:
    geometry = {
        "points": locations[["sample_lon", "sample_lat"]].values.tolist(),
        "spatialReference": {"wkid": 4326},
    }
    form = {
        "f": "json",
        "geometryType": "esriGeometryMultipoint",
        "geometry": json.dumps(geometry, separators=(",", ":")),
        "returnFirstValueOnly": "false",
        "outFields": "Year,Name",
        "interpolation": "RSP_NearestNeighbor",
    }
    payload = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        ESRI_SERVICE_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "BassCoast-Esri-DEA-Crosscheck/1.0",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            if result.get("error"):
                raise RuntimeError(json.dumps(result["error"], sort_keys=True))
            return result.get("samples", [])
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries:
                break
            delay = min(30, 2 ** (attempt - 1))
            print(f"  request attempt {attempt} failed; retrying in {delay}s: {exc}")
            time.sleep(delay)
    raise RuntimeError(f"Esri request failed after {retries} attempts: {last_error}")


def parse_esri_response(
    samples: list[dict[str, Any]],
    batch_locations: pd.DataFrame,
    batch_index: int,
) -> pd.DataFrame:
    location_lookup = batch_locations.reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for sample in samples:
        location_id = sample.get("locationId")
        if location_id is None or not 0 <= int(location_id) < len(location_lookup):
            continue
        year = sample.get("attributes", {}).get("Year")
        if year is None or int(year) not in YEARS:
            continue
        metadata = location_lookup.iloc[int(location_id)]
        value = sample.get("value")
        try:
            code = int(float(value))
        except (TypeError, ValueError):
            code = None
        rows.append(
            {
                "batch_index": batch_index,
                "review_id": int(metadata["review_id"]),
                "sample_id": int(metadata["sample_id"]),
                "position_kind": metadata["position_kind"],
                "position_index": int(metadata["position_index"]),
                "sample_lon": float(metadata["sample_lon"]),
                "sample_lat": float(metadata["sample_lat"]),
                "year": int(year),
                "esri_code": code,
                "esri_label": ESRI_LABELS.get(code, f"Unknown code {code}"),
                "esri_resolution_m": sample.get("resolution"),
                "esri_raster_id": sample.get("rasterId"),
            }
        )
    return pd.DataFrame(rows)


def acquire_esri_samples(
    locations: pd.DataFrame,
    review: pd.DataFrame,
    checkpoint_dir: Path,
    batch_size: int,
    timeout: int,
    retries: int,
    workers: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    point_ids = review["review_id"].astype(int).tolist()
    diagnostics: list[dict[str, Any]] = []
    batches: list[pd.DataFrame] = []
    pending: list[tuple[int, list[int], pd.DataFrame, Path, int]] = []
    total_batches = math.ceil(len(point_ids) / batch_size)

    def diagnostic_row(
        batch_index: int,
        batch_ids: list[int],
        expected_locations: pd.DataFrame,
        checkpoint: Path,
        expected_rows: int,
        batch_df: pd.DataFrame,
        source: str,
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        return {
            "batch_index": batch_index,
            "review_point_count": len(batch_ids),
            "sample_location_count": len(expected_locations),
            "expected_position_year_rows": expected_rows,
            "actual_position_year_rows": len(batch_df),
            "unique_review_point_years": batch_df[
                ["review_id", "year"]
            ].drop_duplicates().shape[0],
            "source": source,
            "elapsed_seconds": elapsed_seconds,
            "complete": len(batch_df) == expected_rows,
            "checkpoint": str(checkpoint),
        }

    for batch_index, start in enumerate(range(0, len(point_ids), batch_size)):
        batch_ids = point_ids[start : start + batch_size]
        checkpoint = checkpoint_dir / f"batch_{batch_index:04d}.csv"
        expected_locations = locations[locations["review_id"].isin(batch_ids)].copy()
        expected_rows = len(expected_locations) * len(YEARS)
        if checkpoint.exists():
            started = time.perf_counter()
            batch_df = pd.read_csv(checkpoint)
            batches.append(batch_df)
            diagnostics.append(
                diagnostic_row(
                    batch_index,
                    batch_ids,
                    expected_locations,
                    checkpoint,
                    expected_rows,
                    batch_df,
                    "checkpoint",
                    time.perf_counter() - started,
                )
            )
        else:
            pending.append(
                (
                    batch_index,
                    batch_ids,
                    expected_locations,
                    checkpoint,
                    expected_rows,
                )
            )

    def request_batch(
        job: tuple[int, list[int], pd.DataFrame, Path, int],
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        batch_index, batch_ids, expected_locations, checkpoint, expected_rows = job
        started = time.perf_counter()
        print(
            f"Requesting batch {batch_index + 1}/{total_batches} "
            f"({len(batch_ids)} review points, {len(expected_locations)} locations)",
            flush=True,
        )
        samples = post_esri_samples(expected_locations, timeout, retries)
        batch_df = parse_esri_response(samples, expected_locations, batch_index)
        batch_df.to_csv(checkpoint, index=False)
        diagnostic = diagnostic_row(
            batch_index,
            batch_ids,
            expected_locations,
            checkpoint,
            expected_rows,
            batch_df,
            "api",
            time.perf_counter() - started,
        )
        return batch_df, diagnostic

    if pending:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, workers)
        ) as executor:
            futures = {executor.submit(request_batch, job): job[0] for job in pending}
            for future in concurrent.futures.as_completed(futures):
                batch_df, diagnostic = future.result()
                batches.append(batch_df)
                diagnostics.append(diagnostic)

    raw = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
    raw = raw.sort_values(
        ["batch_index", "review_id", "position_kind", "position_index", "year"]
    ).reset_index(drop=True)
    diagnostics_df = pd.DataFrame(diagnostics).sort_values("batch_index").reset_index(
        drop=True
    )
    return raw, diagnostics_df


def valid_esri_code(code: Any) -> bool:
    if pd.isna(code):
        return False
    return int(code) in ESRI_LABELS and int(code) not in {9, 10}


def majority_esri(values: pd.Series) -> tuple[float, str | None, int, int, float]:
    valid = [int(value) for value in values if valid_esri_code(value)]
    if not valid:
        return np.nan, None, 0, 0, np.nan
    counts = Counter(valid)
    code, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return float(code), ESRI_LABELS[code], count, len(valid), count / len(valid)


def build_point_year_table(
    raw: pd.DataFrame,
    review: pd.DataFrame,
    dea: pd.DataFrame,
) -> pd.DataFrame:
    center = raw[raw["position_kind"] == "center"].copy()
    center = center.rename(
        columns={
            "esri_code": "esri_center_code",
            "esri_label": "esri_center_label",
            "esri_resolution_m": "esri_center_resolution_m",
        }
    )
    center = center[
        [
            "review_id",
            "year",
            "esri_center_code",
            "esri_center_label",
            "esri_center_resolution_m",
        ]
    ]

    footprint_rows: list[dict[str, Any]] = []
    footprint = raw[raw["position_kind"] == "dea_footprint"]
    for (review_id, year), group in footprint.groupby(["review_id", "year"]):
        code, label, majority_count, valid_count, majority_share = majority_esri(
            group["esri_code"]
        )
        footprint_rows.append(
            {
                "review_id": int(review_id),
                "year": int(year),
                "esri_footprint_majority_code": code,
                "esri_footprint_majority_label": label,
                "esri_footprint_majority_count": majority_count,
                "esri_footprint_valid_count": valid_count,
                "esri_footprint_majority_share": majority_share,
                "esri_footprint_distinct_class_count": len(
                    {
                        int(value)
                        for value in group["esri_code"]
                        if valid_esri_code(value)
                    }
                ),
            }
        )
    footprint_summary = pd.DataFrame(footprint_rows)

    review_fields = [
        "review_id",
        "sample_id",
        "row",
        "col",
        "pixel_key",
        "category",
        "selection_method",
        "lon",
        "lat",
        "endpoint_change",
        "persistence_count",
        "variance_annual_change",
        "slope_annual_change",
        "first_hotspot_year",
        "max_change_year",
        "google_maps_link",
    ]
    available_fields = [field for field in review_fields if field in review.columns]
    review_base = review[available_fields]

    table = dea.merge(
        review_base,
        on=["review_id", "sample_id", "pixel_key", "category", "lon", "lat"],
        how="left",
        validate="many_to_one",
    )
    table = table.merge(center, on=["review_id", "year"], how="left", validate="one_to_one")
    table = table.merge(
        footprint_summary,
        on=["review_id", "year"],
        how="left",
        validate="one_to_one",
    )

    table["dea_level3_effective_code"] = pd.to_numeric(
        table["dea_level3_effective_code"], errors="coerce"
    )
    table["esri_center_code"] = pd.to_numeric(table["esri_center_code"], errors="coerce")
    table["esri_footprint_majority_code"] = pd.to_numeric(
        table["esri_footprint_majority_code"], errors="coerce"
    )

    table["dea_family"] = table["dea_level3_effective_code"].map(DEA_FAMILIES)
    table["esri_center_family"] = table["esri_center_code"].map(ESRI_FAMILIES)
    table["esri_footprint_family"] = table[
        "esri_footprint_majority_code"
    ].map(ESRI_FAMILIES)

    table["esri_center_valid"] = table["esri_center_code"].map(valid_esri_code)
    table["esri_footprint_valid"] = table[
        "esri_footprint_majority_code"
    ].map(valid_esri_code)
    table["family_comparable"] = (
        table["dea_family"].notna()
        & table["esri_footprint_valid"]
        & table["esri_footprint_family"].ne("unavailable")
    )
    table["family_match"] = (
        table["family_comparable"]
        & table["dea_family"].eq(table["esri_footprint_family"])
    )

    def semantic_relation(row: pd.Series) -> str:
        dea_code = row["dea_level3_effective_code"]
        esri_code = row["esri_footprint_majority_code"]
        if pd.isna(dea_code) or pd.isna(esri_code) or not row["family_comparable"]:
            return "unavailable"
        pair = (int(dea_code), int(esri_code))
        if pair in STRONG_MATCHES:
            return "strong_match"
        if pair in BROAD_MATCHES:
            return "broad_match"
        if pair in AMBIGUOUS_MATCHES:
            return "ambiguous"
        if row["family_match"]:
            return "broad_match"
        return "mismatch"

    table["semantic_relation"] = table.apply(semantic_relation, axis=1)
    table["center_footprint_agree"] = (
        table["esri_center_valid"]
        & table["esri_footprint_valid"]
        & table["esri_center_code"].eq(table["esri_footprint_majority_code"])
    )
    return table.sort_values(["review_id", "year"]).reset_index(drop=True)


def first_change_year(values: list[Any], years: list[int]) -> float:
    if len(values) != len(years) or any(pd.isna(value) for value in values):
        return np.nan
    for index in range(1, len(values)):
        if values[index] != values[index - 1]:
            return float(years[index])
    return np.nan


def adjacent_change_count(values: list[Any]) -> float:
    if any(pd.isna(value) for value in values):
        return np.nan
    return float(sum(values[index] != values[index - 1] for index in range(1, len(values))))


def sequence_type(values: list[Any]) -> str:
    if any(pd.isna(value) for value in values):
        return "incomplete"
    changes = int(adjacent_change_count(values))
    if changes == 0:
        return "stable"
    if values[0] == values[-1]:
        return "temporary_or_return_to_start"
    if changes == 1:
        return "single_transition"
    return "multiple_transitions"


def sequence_text(values: list[Any]) -> str:
    return " | ".join("Unknown" if pd.isna(value) else str(value) for value in values)


def build_point_summary(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for review_id, group in table.groupby("review_id", sort=True):
        group = group.sort_values("year")
        base = group.iloc[0]
        years = group["year"].astype(int).tolist()
        dea_codes = group["dea_level3_effective_code"].tolist()
        dea_labels = group["dea_level3_effective_label"].tolist()
        esri_center_codes = group["esri_center_code"].tolist()
        esri_center_labels = group["esri_center_label"].tolist()
        esri_codes = group["esri_footprint_majority_code"].tolist()
        esri_labels = group["esri_footprint_majority_label"].tolist()
        dea_families = group["dea_family"].tolist()
        esri_families = group["esri_footprint_family"].tolist()

        dea_changed_count = adjacent_change_count(dea_codes)
        esri_changed_count = adjacent_change_count(esri_codes)
        dea_changed = bool(dea_changed_count > 0) if not pd.isna(dea_changed_count) else np.nan
        esri_changed = bool(esri_changed_count > 0) if not pd.isna(esri_changed_count) else np.nan
        dea_first = first_change_year(dea_codes, years)
        esri_first = first_change_year(esri_codes, years)

        if pd.isna(dea_changed) or pd.isna(esri_changed):
            change_status = "incomplete"
        elif dea_changed and esri_changed:
            change_status = "both_changed"
        elif not dea_changed and not esri_changed:
            change_status = "both_stable"
        elif dea_changed:
            change_status = "dea_only_changed"
        else:
            change_status = "esri_only_changed"

        comparable = group["family_comparable"].sum()
        family_matches = group["family_match"].sum()
        timing_difference = (
            esri_first - dea_first
            if not pd.isna(esri_first) and not pd.isna(dea_first)
            else np.nan
        )
        dea_family_change_count = adjacent_change_count(dea_families)
        esri_family_change_count = adjacent_change_count(esri_families)
        dea_family_changed = bool(dea_family_change_count > 0)
        esri_family_changed = bool(esri_family_change_count > 0)
        dea_family_first = first_change_year(dea_families, years)
        esri_family_first = first_change_year(esri_families, years)
        family_timing_difference = (
            esri_family_first - dea_family_first
            if not pd.isna(esri_family_first) and not pd.isna(dea_family_first)
            else np.nan
        )
        if dea_family_changed and esri_family_changed:
            family_change_status = "both_changed"
        elif not dea_family_changed and not esri_family_changed:
            family_change_status = "both_stable"
        elif dea_family_changed:
            family_change_status = "dea_only_changed"
        else:
            family_change_status = "esri_only_changed"

        rows.append(
            {
                "review_id": int(review_id),
                "sample_id": int(base["sample_id"]),
                "pixel_key": base["pixel_key"],
                "category": base["category"],
                "selection_method": base.get("selection_method"),
                "lon": base["lon"],
                "lat": base["lat"],
                "google_maps_link": base.get("google_maps_link"),
                "endpoint_change": base.get("endpoint_change"),
                "persistence_count": base.get("persistence_count"),
                "variance_annual_change": base.get("variance_annual_change"),
                "slope_annual_change": base.get("slope_annual_change"),
                "embedding_first_hotspot_year": base.get("first_hotspot_year"),
                "embedding_max_change_year": base.get("max_change_year"),
                "dea_level3_sequence": sequence_text(dea_labels),
                "dea_level4_sequence": sequence_text(
                    group["dea_level4_effective_label"].tolist()
                ),
                "esri_center_sequence": sequence_text(esri_center_labels),
                "esri_footprint_sequence": sequence_text(esri_labels),
                "dea_family_sequence": sequence_text(dea_families),
                "esri_family_sequence": sequence_text(esri_families),
                "dea_valid_year_count": int(pd.Series(dea_codes).notna().sum()),
                "esri_center_valid_year_count": int(group["esri_center_valid"].sum()),
                "esri_footprint_valid_year_count": int(group["esri_footprint_valid"].sum()),
                "comparable_year_count": int(comparable),
                "family_match_year_count": int(family_matches),
                "family_match_share": (
                    float(family_matches / comparable) if comparable else np.nan
                ),
                "center_footprint_agree_year_count": int(
                    group["center_footprint_agree"].sum()
                ),
                "mean_esri_footprint_majority_share": group[
                    "esri_footprint_majority_share"
                ].mean(),
                "dea_level3_class_changed": dea_changed,
                "esri_class_changed": esri_changed,
                "change_status_comparison": change_status,
                "dea_adjacent_change_count": dea_changed_count,
                "esri_adjacent_change_count": esri_changed_count,
                "dea_first_change_year": dea_first,
                "esri_first_change_year": esri_first,
                "first_change_year_difference": timing_difference,
                "first_change_year_exact_match": (
                    bool(timing_difference == 0) if not pd.isna(timing_difference) else np.nan
                ),
                "first_change_year_match_pm1": (
                    bool(abs(timing_difference) <= 1)
                    if not pd.isna(timing_difference)
                    else np.nan
                ),
                "dea_sequence_type": sequence_type(dea_codes),
                "esri_sequence_type": sequence_type(esri_codes),
                "dea_family_changed": dea_family_changed,
                "esri_family_changed": esri_family_changed,
                "family_change_status_comparison": family_change_status,
                "dea_family_adjacent_change_count": dea_family_change_count,
                "esri_family_adjacent_change_count": esri_family_change_count,
                "dea_family_first_change_year": dea_family_first,
                "esri_family_first_change_year": esri_family_first,
                "family_first_change_year_difference": family_timing_difference,
                "family_first_change_year_exact_match": (
                    bool(family_timing_difference == 0)
                    if not pd.isna(family_timing_difference)
                    else np.nan
                ),
                "family_first_change_year_match_pm1": (
                    bool(abs(family_timing_difference) <= 1)
                    if not pd.isna(family_timing_difference)
                    else np.nan
                ),
                "endpoint_family_match_2017": bool(group.iloc[0]["family_match"]),
                "endpoint_family_match_2024": bool(group.iloc[-1]["family_match"]),
            }
        )
    return pd.DataFrame(rows)


def safe_share(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else np.nan


def build_summaries(
    table: pd.DataFrame,
    points: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    annual_rows: list[dict[str, Any]] = []
    for year, group in table.groupby("year"):
        comparable = int(group["family_comparable"].sum())
        matches = int(group["family_match"].sum())
        annual_rows.append(
            {
                "year": int(year),
                "point_year_records": len(group),
                "esri_center_valid": int(group["esri_center_valid"].sum()),
                "esri_footprint_valid": int(group["esri_footprint_valid"].sum()),
                "comparable_records": comparable,
                "family_matches": matches,
                "family_match_share": safe_share(matches, comparable),
                "center_footprint_agreements": int(
                    group["center_footprint_agree"].sum()
                ),
                "center_footprint_agreement_share": safe_share(
                    int(group["center_footprint_agree"].sum()),
                    int(group["esri_center_valid"].sum()),
                ),
                "mean_footprint_majority_share": group[
                    "esri_footprint_majority_share"
                ].mean(),
            }
        )

    category_rows: list[dict[str, Any]] = []
    for category, group in table.groupby("category"):
        point_group = points[points["category"] == category]
        comparable = int(group["family_comparable"].sum())
        matches = int(group["family_match"].sum())
        both_changed = int(
            point_group["change_status_comparison"].eq("both_changed").sum()
        )
        dea_changed = int(point_group["dea_level3_class_changed"].eq(True).sum())
        timing_eligible = point_group["first_change_year_difference"].notna()
        timing_pm1 = int(
            point_group.loc[timing_eligible, "first_change_year_match_pm1"]
            .fillna(False)
            .sum()
        )
        family_both_changed = int(
            point_group["family_change_status_comparison"].eq("both_changed").sum()
        )
        family_status_agree = int(
            point_group["family_change_status_comparison"]
            .isin(["both_changed", "both_stable"])
            .sum()
        )
        category_rows.append(
            {
                "category": category,
                "review_points": point_group["review_id"].nunique(),
                "point_year_records": len(group),
                "comparable_records": comparable,
                "family_matches": matches,
                "family_match_share": safe_share(matches, comparable),
                "dea_changed_points": dea_changed,
                "both_changed_points": both_changed,
                "both_changed_share_of_dea_changed": safe_share(
                    both_changed, dea_changed
                ),
                "timing_comparable_points": int(timing_eligible.sum()),
                "timing_pm1_matches": timing_pm1,
                "timing_pm1_match_share": safe_share(
                    timing_pm1, int(timing_eligible.sum())
                ),
                "common_family_both_changed_points": family_both_changed,
                "common_family_change_status_agree_points": family_status_agree,
                "common_family_change_status_agreement_share": safe_share(
                    family_status_agree, len(point_group)
                ),
                "mean_family_match_share_per_point": point_group[
                    "family_match_share"
                ].mean(),
                "mean_footprint_majority_share": point_group[
                    "mean_esri_footprint_majority_share"
                ].mean(),
            }
        )

    crosswalk = (
        table.groupby(
            [
                "dea_level3_effective_code",
                "dea_level3_effective_label",
                "dea_family",
                "esri_footprint_majority_code",
                "esri_footprint_majority_label",
                "esri_footprint_family",
                "semantic_relation",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="point_year_count")
    )
    dea_totals = crosswalk.groupby(
        ["dea_level3_effective_code", "dea_level3_effective_label"],
        dropna=False,
    )["point_year_count"].transform("sum")
    crosswalk["share_within_dea_level3_label"] = (
        crosswalk["point_year_count"] / dea_totals
    )
    crosswalk = crosswalk.sort_values(
        ["dea_level3_effective_label", "point_year_count"],
        ascending=[True, False],
    )

    change_status = (
        points.groupby(
            [
                "dea_level3_class_changed",
                "esri_class_changed",
                "change_status_comparison",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="review_point_count")
    )

    timing = points[
        points["first_change_year_difference"].notna()
    ][
        [
            "review_id",
            "sample_id",
            "pixel_key",
            "category",
            "dea_first_change_year",
            "esri_first_change_year",
            "first_change_year_difference",
            "first_change_year_exact_match",
            "first_change_year_match_pm1",
            "google_maps_link",
        ]
    ].copy()

    family_change_status = (
        points.groupby(
            [
                "dea_family_changed",
                "esri_family_changed",
                "family_change_status_comparison",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="review_point_count")
    )

    family_timing = points[
        points["family_first_change_year_difference"].notna()
    ][
        [
            "review_id",
            "sample_id",
            "pixel_key",
            "category",
            "dea_family_first_change_year",
            "esri_family_first_change_year",
            "family_first_change_year_difference",
            "family_first_change_year_exact_match",
            "family_first_change_year_match_pm1",
            "google_maps_link",
        ]
    ].copy()

    relation_counts = (
        table["semantic_relation"]
        .value_counts(dropna=False)
        .rename_axis("semantic_relation")
        .reset_index(name="point_year_count")
    )
    relation_counts["share_of_all_point_years"] = (
        relation_counts["point_year_count"] / len(table)
    )

    esri_label_counts = (
        table.groupby(
            ["year", "esri_footprint_majority_code", "esri_footprint_majority_label"],
            dropna=False,
        )
        .size()
        .reset_index(name="review_point_count")
    )

    return {
        "annual_agreement": pd.DataFrame(annual_rows),
        "agreement_by_category": pd.DataFrame(category_rows),
        "class_crosswalk": crosswalk,
        "change_status_comparison": change_status,
        "timing_alignment": timing,
        "common_family_change_status_comparison": family_change_status,
        "common_family_timing_alignment": family_timing,
        "semantic_relation_counts": relation_counts,
        "esri_label_counts_by_year": esri_label_counts,
    }


def disagreement_review(table: pd.DataFrame) -> pd.DataFrame:
    relation_rank = {
        "mismatch": 0,
        "ambiguous": 1,
        "broad_match": 2,
        "strong_match": 3,
        "unavailable": 4,
    }
    result = table[
        table["semantic_relation"].isin(["mismatch", "ambiguous"])
    ].copy()
    result["relation_rank"] = result["semantic_relation"].map(relation_rank)
    columns = [
        "review_id",
        "sample_id",
        "pixel_key",
        "category",
        "year",
        "lon",
        "lat",
        "dea_level3_effective_label",
        "dea_level4_effective_label",
        "esri_center_label",
        "esri_footprint_majority_label",
        "esri_footprint_majority_share",
        "semantic_relation",
        "dea_family",
        "esri_footprint_family",
        "endpoint_change",
        "persistence_count",
        "google_maps_link",
        "relation_rank",
    ]
    columns = [column for column in columns if column in result.columns]
    return result[columns].sort_values(
        ["relation_rank", "review_id", "year"]
    ).drop(columns=["relation_rank"], errors="ignore")


def save_figure(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_crosswalk(table: pd.DataFrame, output: Path) -> None:
    counts = pd.crosstab(
        table["dea_level3_effective_label"],
        table["esri_footprint_majority_label"],
    )
    matrix = counts.div(counts.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(12, 6.5))
    image = ax.imshow(matrix.values, cmap="YlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(
        [
            f"{label} (n={int(counts.loc[label].sum()):,})"
            for label in matrix.index
        ]
    )
    ax.set_xlabel("Esri 30 m footprint-majority class")
    ax.set_ylabel("DEA Level 3 class")
    ax.set_title("Esri Class Distribution Within Each DEA Level 3 Class")
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix.iloc[row, col]
            if value >= 0.02:
                ax.text(
                    col,
                    row,
                    f"{value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if value > 0.55 else "black",
                )
    fig.colorbar(image, ax=ax, label="Share within DEA class")
    fig.tight_layout()
    save_figure(fig, output)


def plot_annual_agreement(annual: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(
        annual["year"],
        annual["family_match_share"] * 100,
        marker="o",
        linewidth=2.2,
        color="#24755b",
        label="DEA–Esri broad-family agreement",
    )
    ax.plot(
        annual["year"],
        annual["center_footprint_agreement_share"] * 100,
        marker="s",
        linewidth=2,
        color="#4f6fa8",
        label="Esri centre–footprint agreement",
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of comparable records (%)")
    ax.set_xlabel("Year")
    ax.set_title("Annual Land-Cover Agreement")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    save_figure(fig, output)


def plot_category_agreement(category: pd.DataFrame, output: Path) -> None:
    order = [item for item in CATEGORY_ORDER if item in set(category["category"])]
    data = category.set_index("category").reindex(order)
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [PALETTE.get(item, "#65717a") for item in order]
    bars = ax.bar(
        range(len(data)),
        data["family_match_share"] * 100,
        color=colors,
        edgecolor="white",
    )
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels(
        [item.replace("_", " ") for item in order], rotation=35, ha="right"
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Broad-family agreement (%)")
    ax.set_title("DEA–Esri Agreement by Embedding Behavioural Category")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, data["family_match_share"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{value:.1%}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    save_figure(fig, output)


def plot_change_status(
    points: pd.DataFrame,
    output: Path,
    status_column: str = "change_status_comparison",
    title: str = "DEA and Esri Native-Class Changed/Stable Status",
) -> None:
    order = [
        "both_changed",
        "both_stable",
        "dea_only_changed",
        "esri_only_changed",
        "incomplete",
    ]
    counts = points[status_column].value_counts().reindex(order, fill_value=0)
    labels = [item.replace("_", " ") for item in order]
    colors = ["#25875f", "#65717a", "#bf7a1a", "#6d5aa7", "#b33b3b"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, counts.values, color=colors)
    ax.set_ylabel("Review points")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts.max() * 0.015, 1),
            f"{int(value)}",
            ha="center",
            va="bottom",
        )
    fig.tight_layout()
    save_figure(fig, output)


def plot_timing(
    points: pd.DataFrame,
    output: Path,
    difference_column: str = "first_change_year_difference",
    dea_year_column: str = "dea_first_change_year",
    esri_year_column: str = "esri_first_change_year",
    title: str = "First-Change Timing for Native Classes",
) -> None:
    data = points[points[difference_column].notna()].copy()
    fig, ax = plt.subplots(figsize=(7, 6))
    if data.empty:
        ax.text(0.5, 0.5, "No points changed in both datasets", ha="center", va="center")
        ax.set_axis_off()
    else:
        jitter = np.linspace(-0.12, 0.12, len(data))
        ax.scatter(
            data[dea_year_column] + jitter,
            data[esri_year_column] - jitter,
            s=18,
            alpha=0.45,
            color="#286b50",
            edgecolors="none",
        )
        limits = [min(YEARS) + 0.5, max(YEARS) + 0.5]
        ax.plot(limits, limits, color="#333333", linewidth=1.5, label="Exact timing")
        ax.plot(
            limits,
            [limits[0] + 1, limits[1] + 1],
            color="#999999",
            linestyle="--",
            linewidth=1,
        )
        ax.plot(
            limits,
            [limits[0] - 1, limits[1] - 1],
            color="#999999",
            linestyle="--",
            linewidth=1,
            label="±1 year",
        )
        ax.set_xlim(limits)
        ax.set_ylim(limits)
        ax.set_xticks(YEARS[1:])
        ax.set_yticks(YEARS[1:])
        ax.set_xlabel("DEA first-change year")
        ax.set_ylabel("Esri first-change year")
        ax.set_title(title)
        ax.grid(alpha=0.2)
        ax.legend(frameon=False)
    fig.tight_layout()
    save_figure(fig, output)


def write_report(
    output_path: Path,
    review: pd.DataFrame,
    table: pd.DataFrame,
    points: pd.DataFrame,
    summaries: dict[str, pd.DataFrame],
    diagnostics: pd.DataFrame,
) -> None:
    comparable = int(table["family_comparable"].sum())
    matches = int(table["family_match"].sum())
    relation_counts = table["semantic_relation"].value_counts()
    esri_valid = int(table["esri_footprint_valid"].sum())
    both_changed = int(points["change_status_comparison"].eq("both_changed").sum())
    both_stable = int(points["change_status_comparison"].eq("both_stable").sum())
    dea_only = int(points["change_status_comparison"].eq("dea_only_changed").sum())
    esri_only = int(points["change_status_comparison"].eq("esri_only_changed").sum())
    timing = points[points["first_change_year_difference"].notna()]
    timing_exact = int(timing["first_change_year_exact_match"].fillna(False).sum())
    timing_pm1 = int(timing["first_change_year_match_pm1"].fillna(False).sum())
    family_both_changed = int(
        points["family_change_status_comparison"].eq("both_changed").sum()
    )
    family_both_stable = int(
        points["family_change_status_comparison"].eq("both_stable").sum()
    )
    family_dea_only = int(
        points["family_change_status_comparison"].eq("dea_only_changed").sum()
    )
    family_esri_only = int(
        points["family_change_status_comparison"].eq("esri_only_changed").sum()
    )
    family_timing = points[
        points["family_first_change_year_difference"].notna()
    ]
    family_timing_exact = int(
        family_timing["family_first_change_year_exact_match"].fillna(False).sum()
    )
    family_timing_pm1 = int(
        family_timing["family_first_change_year_match_pm1"].fillna(False).sum()
    )
    annual = summaries["annual_agreement"]

    lines = [
        "# Bass Coast Phase 7: Esri–DEA Land Cover Cross-Check",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Scope",
        "",
        (
            f"The analysis cross-checks {len(review):,} Phase 2B review points over "
            f"{len(YEARS)} years ({len(table):,} point-year records). It compares "
            "DEA Level 3 classes with Esri classes aggregated over the corresponding "
            "30 m DEA footprint."
        ),
        "",
        "Agreement is contextual cross-dataset agreement, not classification accuracy or ground truth.",
        "",
        "## Coverage",
        "",
        f"- Esri footprint records with a usable class: {esri_valid:,}/{len(table):,} ({safe_share(esri_valid, len(table)):.1%})",
        f"- Comparable DEA–Esri point-year records: {comparable:,}/{len(table):,}",
        f"- Complete API/checkpoint batches: {int(diagnostics['complete'].sum())}/{len(diagnostics)}",
        "",
        "## Annual Broad-Family Agreement",
        "",
        f"- Overall broad-family matches: {matches:,}/{comparable:,} ({safe_share(matches, comparable):.1%})",
    ]
    for row in annual.itertuples(index=False):
        lines.append(
            f"- {int(row.year)}: {int(row.family_matches):,}/"
            f"{int(row.comparable_records):,} ({row.family_match_share:.1%})"
        )
    lines.extend(
        [
            "",
            "## Semantic Relationship",
            "",
            f"- Strong matches: {int(relation_counts.get('strong_match', 0)):,}",
            f"- Broad matches: {int(relation_counts.get('broad_match', 0)):,}",
            f"- Ambiguous terrestrial matches: {int(relation_counts.get('ambiguous', 0)):,}",
            f"- Mismatches: {int(relation_counts.get('mismatch', 0)):,}",
            f"- Unavailable: {int(relation_counts.get('unavailable', 0)):,}",
            (
                "- Strong or broad semantic matches: "
                f"{int(relation_counts.get('strong_match', 0) + relation_counts.get('broad_match', 0)):,}/"
                f"{len(table):,} "
                f"({safe_share(int(relation_counts.get('strong_match', 0) + relation_counts.get('broad_match', 0)), len(table)):.1%})"
            ),
            "",
            "## Native-Class Changed/Stable Status",
            "",
            f"- Both datasets changed: {both_changed:,} points",
            f"- Both datasets remained stable: {both_stable:,} points",
            f"- DEA only changed: {dea_only:,} points",
            f"- Esri only changed: {esri_only:,} points",
            (
                "- Native-class changed/stable status agreement: "
                f"{both_changed + both_stable:,}/{len(points):,} "
                f"({safe_share(both_changed + both_stable, len(points)):.1%})"
            ),
            (
                "- Changed-point overlap (Jaccard): "
                f"{both_changed:,}/{both_changed + dea_only + esri_only:,} "
                f"({safe_share(both_changed, both_changed + dea_only + esri_only):.1%})"
            ),
            "",
            "## Native-Class Timing",
            "",
            f"- Points changed in both datasets with comparable first-change years: {len(timing):,}",
            f"- Exact first-change-year matches: {timing_exact:,}/{len(timing):,} ({safe_share(timing_exact, len(timing)):.1%})",
            f"- First-change matches within ±1 year: {timing_pm1:,}/{len(timing):,} ({safe_share(timing_pm1, len(timing)):.1%})",
            "",
            "## Harmonized Common-Family Change Status",
            "",
            f"- Both datasets changed broad cover family: {family_both_changed:,} points",
            f"- Both datasets remained in the same broad family: {family_both_stable:,} points",
            f"- DEA only changed broad family: {family_dea_only:,} points",
            f"- Esri only changed broad family: {family_esri_only:,} points",
            (
                "- Broad-family changed/stable status agreement: "
                f"{family_both_changed + family_both_stable:,}/{len(points):,} "
                f"({safe_share(family_both_changed + family_both_stable, len(points)):.1%})"
            ),
            "",
            "## Harmonized Common-Family Timing",
            "",
            f"- Points with broad-family changes in both datasets: {len(family_timing):,}",
            f"- Exact broad-family first-change matches: {family_timing_exact:,}/{len(family_timing):,} ({safe_share(family_timing_exact, len(family_timing)):.1%})",
            f"- Broad-family first-change matches within ±1 year: {family_timing_pm1:,}/{len(family_timing):,} ({safe_share(family_timing_pm1, len(family_timing)):.1%})",
            "",
            "## Interpretation Boundary",
            "",
            (
                "Esri can add intuitive labels such as Trees, Crops, Built Area, "
                "Bare Ground, Water and Rangeland. It is not necessarily more "
                "thematically detailed than DEA Level 4. Rangeland is especially "
                "ambiguous because it can include pasture, natural grassland, lawns "
                "and sparse shrub cover."
            ),
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    review_path = Path(args.review_points)
    dea_path = Path(args.dea_long)
    output_dir = Path(args.output_dir)
    checkpoint_dir = output_dir / "checkpoints"
    figure_dir = output_dir / "figures"

    ensure_inputs(review_path, dea_path)
    if args.fresh and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    print("Loading review points and completed DEA histories...")
    review = load_review_points(review_path, args.max_points)
    dea = load_dea_records(dea_path, review)
    print(
        f"Matched {len(review):,} review points and {len(dea):,} DEA point-year records."
    )

    print("Constructing exact-coordinate and DEA-footprint sample locations...")
    locations = build_sample_locations(review, dea)
    locations.to_csv(output_dir / "basscoast_phase7_sample_locations.csv", index=False)
    print(f"Prepared {len(locations):,} Esri sample locations.")

    print("Retrieving Esri Annual Land Cover histories...")
    raw, diagnostics = acquire_esri_samples(
        locations,
        review,
        checkpoint_dir,
        max(1, args.batch_size),
        args.timeout,
        max(1, args.retries),
        max(1, args.workers),
    )
    raw_path = output_dir / "basscoast_phase7_esri_samples_raw_long.csv"
    raw.to_csv(raw_path, index=False)
    diagnostics.to_csv(
        output_dir / "basscoast_phase7_run_diagnostics.csv", index=False
    )

    expected_raw_rows = len(locations) * len(YEARS)
    if len(raw) != expected_raw_rows:
        print(
            f"WARNING: Esri returned {len(raw):,} position-year records; "
            f"expected {expected_raw_rows:,}."
        )

    print("Building point-year and temporal cross-check tables...")
    point_year = build_point_year_table(raw, review, dea)
    point_summary = build_point_summary(point_year)
    summaries = build_summaries(point_year, point_summary)
    disagreements = disagreement_review(point_year)

    point_year.to_csv(
        output_dir / "basscoast_phase7_esri_dea_history_long.csv", index=False
    )
    point_summary.to_csv(
        output_dir / "basscoast_phase7_enriched_review_points.csv", index=False
    )
    for name, frame in summaries.items():
        frame.to_csv(output_dir / f"basscoast_phase7_{name}.csv", index=False)
    disagreements.to_csv(
        output_dir / "basscoast_phase7_disagreement_review.csv", index=False
    )

    print("Creating diagnostic figures...")
    plot_crosswalk(
        point_year,
        figure_dir / "phase7_dea_esri_class_crosswalk.png",
    )
    plot_annual_agreement(
        summaries["annual_agreement"],
        figure_dir / "phase7_annual_agreement.png",
    )
    plot_category_agreement(
        summaries["agreement_by_category"],
        figure_dir / "phase7_agreement_by_category.png",
    )
    plot_change_status(
        point_summary,
        figure_dir / "phase7_changed_stable_comparison.png",
    )
    plot_timing(
        point_summary,
        figure_dir / "phase7_first_change_timing.png",
    )
    plot_change_status(
        point_summary,
        figure_dir / "phase7_common_family_changed_stable_comparison.png",
        status_column="family_change_status_comparison",
        title="DEA and Esri Common-Family Changed/Stable Status",
    )
    plot_timing(
        point_summary,
        figure_dir / "phase7_common_family_first_change_timing.png",
        difference_column="family_first_change_year_difference",
        dea_year_column="dea_family_first_change_year",
        esri_year_column="esri_family_first_change_year",
        title="First-Change Timing for Harmonized Cover Families",
    )

    report_path = output_dir / "basscoast_phase7_results_report.md"
    write_report(
        report_path,
        review,
        point_year,
        point_summary,
        summaries,
        diagnostics,
    )

    comparable = int(point_year["family_comparable"].sum())
    matches = int(point_year["family_match"].sum())
    print("")
    print("Phase 7 complete")
    print(f"- review points: {len(review):,}")
    print(f"- point-year records: {len(point_year):,}")
    print(
        f"- broad-family agreement: {matches:,}/{comparable:,} "
        f"({safe_share(matches, comparable):.1%})"
    )
    print(f"- output directory: {output_dir.resolve()}")
    print(f"- report: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
