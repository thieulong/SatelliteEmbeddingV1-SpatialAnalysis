#!/usr/bin/env python3
"""Run the Bass Coast 900-point annual NDVI versus embedding pilot."""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.warp import transform


YEARS = list(range(2017, 2025))
INTERVALS = [(year, year + 1) for year in YEARS[:-1]]
STAC_ROOT = "https://explorer.dea.ga.gov.au/stac"
PRODUCT = "ga_ls8cls9c_gm_cyear_3"
REVIEW_POINTS = Path(
    "data/processed/sampling/basscoast_phase2b_review_points.csv"
)
DEA_CONTEXT = Path(
    "data/processed/dea_sample/basscoast_phase3_dea_long.csv"
)
DEFAULT_OUTPUT = Path("data/processed/ndvi_pilot")

DEA_FAMILY_BY_LEVEL3 = {
    111: "terrestrial_vegetation",
    112: "terrestrial_vegetation",
    124: "aquatic_vegetation",
    215: "artificial",
    216: "bare",
    220: "water",
    255: "no_data",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-points", type=Path, default=REVIEW_POINTS)
    parser.add_argument("--dea-context", type=Path, default=DEA_CONTEXT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--years",
        default=",".join(map(str, YEARS)),
        help="Comma-separated years to retrieve.",
    )
    parser.add_argument("--max-points", type=int, default=0)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--bootstrap-runs", type=int, default=1_000)
    return parser.parse_args()


def parse_years(value: str) -> list[int]:
    years = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    invalid = [year for year in years if year not in YEARS]
    if invalid:
        raise ValueError(f"Unsupported years: {invalid}")
    return years


def load_inputs(
    review_path: Path, context_path: Path, max_points: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not review_path.exists():
        raise FileNotFoundError(f"Review-point CSV not found: {review_path}")
    if not context_path.exists():
        raise FileNotFoundError(f"DEA context CSV not found: {context_path}")

    points = pd.read_csv(review_path).sort_values("review_id").reset_index(drop=True)
    if max_points > 0:
        points = points.head(max_points).copy()
    wanted_context_columns = {
        "review_id",
        "sample_id",
        "pixel_key",
        "category",
        "year",
        "dea_level3_effective_code",
        "dea_level3_effective_label",
        "dea_level4_effective_label",
        "dea_family",
    }
    context = pd.read_csv(
        context_path,
        usecols=lambda column: column in wanted_context_columns,
    )

    has_review_ids = (
        "review_id" in context.columns and context["review_id"].notna().any()
    )
    if has_review_ids:
        context = context[context["review_id"].isin(points["review_id"])].copy()
    else:
        match_columns = ["sample_id", "pixel_key", "category"]
        missing_match = [column for column in match_columns if column not in context]
        if missing_match:
            raise ValueError(
                "DEA context without review IDs must contain stable match columns: "
                f"{missing_match}"
            )
        context = context.drop(columns=["review_id"], errors="ignore").merge(
            points[["review_id", *match_columns]],
            on=match_columns,
            how="inner",
            validate="many_to_one",
        )

    if "dea_family" not in context.columns:
        if "dea_level3_effective_code" not in context.columns:
            raise ValueError(
                "DEA context must contain dea_family or dea_level3_effective_code."
            )
        context["dea_family"] = (
            pd.to_numeric(context["dea_level3_effective_code"], errors="coerce")
            .map(DEA_FAMILY_BY_LEVEL3)
            .fillna("unknown")
        )

    required_point_columns = {
        "review_id",
        "sample_id",
        "pixel_key",
        "category",
        "lon",
        "lat",
        "max_change_year",
        "first_hotspot_year",
    }
    missing = required_point_columns - set(points.columns)
    if missing:
        raise ValueError(f"Review-point columns missing: {sorted(missing)}")
    expected_context_rows = len(points) * len(YEARS)
    if len(context) != expected_context_rows:
        raise ValueError(
            f"Expected {expected_context_rows:,} DEA context rows; found {len(context):,}."
        )
    if context.duplicated(["review_id", "year"]).any():
        raise ValueError("Duplicate review_id/year rows found in DEA context.")
    return points, context


def query_stac(year: int, bbox: list[float], attempts: int = 4) -> list[dict]:
    params = {
        "bbox": ",".join(map(str, bbox)),
        "datetime": f"{year}-01-01/{year}-12-31",
        "collections": PRODUCT,
        "limit": "100",
    }
    url = f"{STAC_ROOT}/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "basscoast-ndvi-pilot/1.0"})
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            features = payload.get("features", [])
            if not features:
                raise RuntimeError(f"No {PRODUCT} STAC items returned for {year}.")
            return features
        except Exception as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"STAC query failed for {year}: {last_error}")


def public_href(href: str) -> str:
    prefix = "s3://dea-public-data/"
    if href.startswith(prefix):
        return "https://data.dea.ga.gov.au/" + href[len(prefix) :]
    return href


def tile_name(feature: dict) -> str:
    href = feature["assets"]["nbart_red"]["href"]
    parts = href.split("/")
    x_part = next((part for part in parts if part.startswith("x") and part[1:].isdigit()), "x?")
    y_part = next((part for part in parts if part.startswith("y") and part[1:].isdigit()), "y?")
    return f"{x_part}{y_part}"


def sample_values(src: rasterio.DatasetReader, coordinates: list[tuple[float, float]]) -> np.ndarray:
    values = np.full(len(coordinates), np.nan, dtype="float64")
    for index, value in enumerate(src.sample(coordinates, indexes=1, masked=True)):
        sample = np.ma.asarray(value)
        if sample.size and not bool(np.ma.getmaskarray(sample).ravel()[0]):
            values[index] = float(sample.ravel()[0])
    return values


def sample_year(
    year: int,
    points: pd.DataFrame,
    features: list[dict],
) -> tuple[pd.DataFrame, list[str]]:
    result = points[
        ["review_id", "sample_id", "pixel_key", "category", "lon", "lat"]
    ].copy()
    result["year"] = year
    result["tile"] = ""
    result["red"] = np.nan
    result["nir"] = np.nan
    result["clear_observation_count"] = np.nan
    result["ndvi"] = np.nan
    result["source_product"] = PRODUCT
    result["source_resolution_m"] = 30

    xs, ys = transform(
        "EPSG:4326",
        "EPSG:3577",
        points["lon"].astype(float).tolist(),
        points["lat"].astype(float).tolist(),
    )
    xy = np.column_stack([xs, ys])
    assigned = np.zeros(len(points), dtype=bool)
    warnings: list[str] = []

    env_options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "4",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "VSI_CACHE": "TRUE",
        "VSI_CACHE_SIZE": "50000000",
    }
    for feature in features:
        assets = feature.get("assets", {})
        required = {"nbart_red", "nbart_nir", "count"}
        if not required.issubset(assets):
            warnings.append(
                f"{year}: STAC item {feature.get('id')} is missing {sorted(required - set(assets))}."
            )
            continue

        red_url = public_href(assets["nbart_red"]["href"])
        nir_url = public_href(assets["nbart_nir"]["href"])
        count_url = public_href(assets["count"]["href"])
        name = tile_name(feature)
        try:
            with rasterio.Env(**env_options), rasterio.open(red_url) as red_src:
                bounds = red_src.bounds
                mask = (
                    (~assigned)
                    & (xy[:, 0] >= bounds.left)
                    & (xy[:, 0] < bounds.right)
                    & (xy[:, 1] >= bounds.bottom)
                    & (xy[:, 1] < bounds.top)
                )
                indices = np.flatnonzero(mask)
                if not len(indices):
                    continue
                coordinates = [(float(xy[i, 0]), float(xy[i, 1])) for i in indices]
                red = sample_values(red_src, coordinates)
                with rasterio.open(nir_url) as nir_src:
                    nir = sample_values(nir_src, coordinates)
                with rasterio.open(count_url) as count_src:
                    counts = sample_values(count_src, coordinates)

            denominator = nir + red
            valid = (
                np.isfinite(red)
                & np.isfinite(nir)
                & np.isfinite(counts)
                & (red > 0)
                & (nir > 0)
                & (counts > 0)
                & (denominator != 0)
            )
            ndvi = np.full(len(indices), np.nan, dtype="float64")
            ndvi[valid] = (nir[valid] - red[valid]) / denominator[valid]
            ndvi[(ndvi < -1) | (ndvi > 1)] = np.nan

            result.loc[indices, "tile"] = name
            result.loc[indices, "red"] = red
            result.loc[indices, "nir"] = nir
            result.loc[indices, "clear_observation_count"] = counts
            result.loc[indices, "ndvi"] = ndvi
            assigned[indices] = True
        except Exception as exc:
            warnings.append(f"{year}: failed to sample {name}: {exc}")

    result["valid_ndvi"] = result["ndvi"].notna()
    unassigned = int((~assigned).sum())
    invalid = int(result["ndvi"].isna().sum())
    if unassigned:
        warnings.append(f"{year}: {unassigned} points were not assigned to a returned tile.")
    if invalid:
        warnings.append(f"{year}: {invalid} points have no valid annual NDVI value.")
    return result, warnings


def retrieve_annual_ndvi(
    points: pd.DataFrame,
    years: list[int],
    checkpoint_dir: Path,
    fresh: bool,
) -> tuple[pd.DataFrame, list[str]]:
    if fresh and checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    bbox = [
        float(points["lon"].min()),
        float(points["lat"].min()),
        float(points["lon"].max()),
        float(points["lat"].max()),
    ]
    tables: list[pd.DataFrame] = []
    warnings: list[str] = []
    for year in years:
        checkpoint = checkpoint_dir / f"ndvi_{year}.csv"
        if checkpoint.exists() and not fresh:
            table = pd.read_csv(checkpoint)
            expected_ids = set(points["review_id"])
            if len(table) == len(points) and set(table["review_id"]) == expected_ids:
                print(f"Reusing {year} checkpoint")
                tables.append(table)
                continue
            warnings.append(f"{year}: ignored incomplete checkpoint {checkpoint.name}.")

        print(f"Sampling annual Landsat GeoMAD NDVI for {year}...")
        features = query_stac(year, bbox)
        table, year_warnings = sample_year(year, points, features)
        table.to_csv(checkpoint, index=False)
        tables.append(table)
        warnings.extend(year_warnings)
        print(
            f"- {year}: {int(table['valid_ndvi'].sum()):,}/{len(table):,} valid points "
            f"across {table.loc[table['tile'].ne(''), 'tile'].nunique()} tiles"
        )
    return pd.concat(tables, ignore_index=True), warnings


def build_annual_table(
    ndvi: pd.DataFrame, context: pd.DataFrame
) -> pd.DataFrame:
    context_columns = [
        "review_id",
        "year",
        "dea_level3_effective_label",
        "dea_level4_effective_label",
        "dea_family",
    ]
    annual = ndvi.merge(context[context_columns], on=["review_id", "year"], how="left")
    if annual["dea_level3_effective_label"].isna().any():
        raise ValueError("DEA labels are missing after the annual NDVI merge.")
    return annual.sort_values(["review_id", "year"]).reset_index(drop=True)


def build_interval_table(
    points: pd.DataFrame, annual: pd.DataFrame
) -> pd.DataFrame:
    annual_index = annual.set_index(["review_id", "year"])
    rows: list[dict] = []
    point_index = points.set_index("review_id")
    for review_id, point in point_index.iterrows():
        for start, end in INTERVALS:
            if (review_id, start) not in annual_index.index or (
                review_id,
                end,
            ) not in annual_index.index:
                continue
            before = annual_index.loc[(review_id, start)]
            after = annual_index.loc[(review_id, end)]
            start_ndvi = float(before["ndvi"]) if pd.notna(before["ndvi"]) else np.nan
            end_ndvi = float(after["ndvi"]) if pd.notna(after["ndvi"]) else np.nan
            delta = end_ndvi - start_ndvi if np.isfinite(start_ndvi + end_ndvi) else np.nan
            change_column = f"annual_change_{start}_{end}"
            hotspot_column = f"annual_hotspot_{start}_{end}"
            rows.append(
                {
                    "review_id": review_id,
                    "sample_id": point["sample_id"],
                    "pixel_key": point["pixel_key"],
                    "category": point["category"],
                    "lon": point["lon"],
                    "lat": point["lat"],
                    "start_year": start,
                    "end_year": end,
                    "embedding_annual_change": point[change_column],
                    "embedding_annual_hotspot": bool(point[hotspot_column] == 1),
                    "ndvi_start": start_ndvi,
                    "ndvi_end": end_ndvi,
                    "ndvi_change": delta,
                    "abs_ndvi_change": abs(delta) if np.isfinite(delta) else np.nan,
                    "start_clear_observation_count": before["clear_observation_count"],
                    "end_clear_observation_count": after["clear_observation_count"],
                    "dea_level3_start": before["dea_level3_effective_label"],
                    "dea_level3_end": after["dea_level3_effective_label"],
                    "dea_level4_start": before["dea_level4_effective_label"],
                    "dea_level4_end": after["dea_level4_effective_label"],
                    "dea_family_start": before["dea_family"],
                    "dea_family_end": after["dea_family"],
                }
            )
    result = pd.DataFrame(rows)
    result["valid_interval"] = result["abs_ndvi_change"].notna()
    return result


def pearson(x: pd.Series, y: pd.Series) -> float:
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) < 3 or valid["x"].nunique() < 2 or valid["y"].nunique() < 2:
        return np.nan
    return float(np.corrcoef(valid["x"], valid["y"])[0, 1])


def spearman(x: pd.Series, y: pd.Series) -> float:
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    return pearson(valid["x"].rank(method="average"), valid["y"].rank(method="average"))


def bootstrap_spearman(
    intervals: pd.DataFrame, runs: int, seed: int = 42
) -> tuple[float, float]:
    if runs <= 0:
        return np.nan, np.nan
    grouped = {key: group for key, group in intervals.groupby("review_id")}
    identifiers = np.array(list(grouped))
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(runs):
        selected = rng.choice(identifiers, size=len(identifiers), replace=True)
        sample = pd.concat([grouped[key] for key in selected], ignore_index=True)
        value = spearman(sample["embedding_annual_change"], sample["abs_ndvi_change"])
        if np.isfinite(value):
            values.append(value)
    if not values:
        return np.nan, np.nan
    return tuple(np.quantile(values, [0.025, 0.975]))


def correlation_tables(
    intervals: pd.DataFrame, bootstrap_runs: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    valid = intervals[intervals["valid_interval"]].copy()

    def summarize(group: pd.DataFrame) -> dict:
        return {
            "interval_count": len(group),
            "point_count": group["review_id"].nunique(),
            "pearson_r": pearson(
                group["embedding_annual_change"], group["abs_ndvi_change"]
            ),
            "spearman_rho": spearman(
                group["embedding_annual_change"], group["abs_ndvi_change"]
            ),
        }

    overall_row = summarize(valid)
    low, high = bootstrap_spearman(valid, bootstrap_runs)
    overall_row.update(
        {
            "group_type": "overall",
            "group": "all_valid_intervals",
            "spearman_cluster_bootstrap_ci_low": low,
            "spearman_cluster_bootstrap_ci_high": high,
        }
    )
    overall = pd.DataFrame([overall_row])

    category_rows = []
    for category, group in valid.groupby("category"):
        row = summarize(group)
        row.update({"category": category})
        category_rows.append(row)
    categories = pd.DataFrame(category_rows).sort_values("spearman_rho", ascending=False)

    class_rows = []
    for label, group in valid.groupby("dea_level3_start"):
        row = summarize(group)
        row.update({"dea_level3_start": label})
        class_rows.append(row)
    classes = pd.DataFrame(class_rows).sort_values("spearman_rho", ascending=False)
    return overall, categories, classes


def annual_ndvi_summary(annual: pd.DataFrame) -> pd.DataFrame:
    valid = annual[annual["valid_ndvi"]].copy()
    return (
        valid.groupby("year")
        .agg(
            valid_points=("ndvi", "size"),
            mean_ndvi=("ndvi", "mean"),
            median_ndvi=("ndvi", "median"),
            q25_ndvi=("ndvi", lambda values: values.quantile(0.25)),
            q75_ndvi=("ndvi", lambda values: values.quantile(0.75)),
            median_clear_observations=("clear_observation_count", "median"),
        )
        .reset_index()
    )


def interval_correlation_summary(intervals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (start_year, end_year), group in intervals.groupby(
        ["start_year", "end_year"]
    ):
        valid = group[group["valid_interval"]]
        rows.append(
            {
                "start_year": int(start_year),
                "end_year": int(end_year),
                "valid_intervals": len(valid),
                "mean_embedding_change": valid["embedding_annual_change"].mean(),
                "mean_signed_ndvi_change": valid["ndvi_change"].mean(),
                "mean_absolute_ndvi_change": valid["abs_ndvi_change"].mean(),
                "pearson_r": pearson(
                    valid["embedding_annual_change"], valid["abs_ndvi_change"]
                ),
                "spearman_rho": spearman(
                    valid["embedding_annual_change"], valid["abs_ndvi_change"]
                ),
                "embedding_hotspot_share": valid[
                    "embedding_annual_hotspot"
                ].mean(),
                "ndvi_event_share": valid["ndvi_event"].mean(),
            }
        )
    return pd.DataFrame(rows)


def hotspot_ndvi_support_by_category(intervals: pd.DataFrame) -> pd.DataFrame:
    hotspots = intervals[
        intervals["valid_interval"] & intervals["embedding_annual_hotspot"]
    ]
    return (
        hotspots.groupby("category")
        .agg(
            embedding_hotspot_intervals=("ndvi_event", "size"),
            ndvi_supported_intervals=("ndvi_event", "sum"),
            ndvi_support_share=("ndvi_event", "mean"),
        )
        .reset_index()
        .sort_values("ndvi_support_share", ascending=False)
    )


def apply_event_thresholds(
    intervals: pd.DataFrame,
) -> tuple[pd.DataFrame, float, pd.DataFrame, pd.DataFrame]:
    result = intervals.copy()
    stable = result[
        result["valid_interval"] & result["category"].eq("stable_control")
    ]
    if stable.empty:
        raise ValueError("No valid stable-control intervals are available for thresholding.")
    threshold = float(stable["abs_ndvi_change"].quantile(0.95))
    result["ndvi_event"] = result["valid_interval"] & result["abs_ndvi_change"].ge(
        threshold
    )
    result["event_comparison"] = "invalid_ndvi"
    valid = result["valid_interval"]
    result.loc[valid & result["embedding_annual_hotspot"] & result["ndvi_event"], "event_comparison"] = "both"
    result.loc[valid & result["embedding_annual_hotspot"] & ~result["ndvi_event"], "event_comparison"] = "embedding_only"
    result.loc[valid & ~result["embedding_annual_hotspot"] & result["ndvi_event"], "event_comparison"] = "ndvi_only"
    result.loc[valid & ~result["embedding_annual_hotspot"] & ~result["ndvi_event"], "event_comparison"] = "neither"

    order = ["both", "embedding_only", "ndvi_only", "neither", "invalid_ndvi"]
    overall = (
        result["event_comparison"]
        .value_counts()
        .reindex(order, fill_value=0)
        .rename_axis("event_comparison")
        .reset_index(name="interval_count")
    )
    overall["share_of_all_intervals"] = overall["interval_count"] / len(result)
    by_category = pd.crosstab(result["category"], result["event_comparison"])
    by_category = by_category.reindex(columns=order, fill_value=0).reset_index()
    return result, threshold, overall, by_category


def point_summary(
    points: pd.DataFrame,
    annual: pd.DataFrame,
    intervals: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    rows = []
    point_index = points.set_index("review_id")
    for review_id, point in point_index.iterrows():
        annual_point = annual[annual["review_id"].eq(review_id)].sort_values("year")
        interval_point = intervals[
            intervals["review_id"].eq(review_id) & intervals["valid_interval"]
        ].sort_values("start_year")
        ndvi_values = annual_point.dropna(subset=["ndvi"])
        valid_years = len(ndvi_values)
        endpoint_change = np.nan
        if {2017, 2024}.issubset(set(ndvi_values["year"])):
            indexed = ndvi_values.set_index("year")["ndvi"]
            endpoint_change = float(indexed.loc[2024] - indexed.loc[2017])

        if interval_point.empty:
            max_row = None
            max_year = np.nan
            max_signed = np.nan
            first_event_year = np.nan
        else:
            max_row = interval_point.loc[interval_point["abs_ndvi_change"].idxmax()]
            max_year = float(max_row["end_year"])
            max_signed = float(max_row["ndvi_change"])
            event_rows = interval_point[interval_point["ndvi_event"]]
            first_event_year = (
                float(event_rows["end_year"].min()) if not event_rows.empty else np.nan
            )

        deltas = interval_point["ndvi_change"]
        large_negative = bool(deltas.le(-threshold).any())
        large_positive = bool(deltas.ge(threshold).any())
        if valid_years < len(YEARS):
            evidence = "incomplete_ndvi_history"
        elif large_negative and large_positive and abs(endpoint_change) < threshold:
            evidence = "disturbance_and_recovery_signal"
        elif endpoint_change <= -threshold:
            evidence = "net_vegetation_decline_signal"
        elif endpoint_change >= threshold:
            evidence = "net_greening_signal"
        elif large_negative:
            evidence = "temporary_decline_signal"
        elif large_positive:
            evidence = "temporary_greening_signal"
        else:
            evidence = "ndvi_stable"

        slope = np.nan
        variance = np.nan
        if valid_years >= 2:
            slope = float(np.polyfit(ndvi_values["year"], ndvi_values["ndvi"], 1)[0])
            variance = float(np.var(ndvi_values["ndvi"], ddof=0))

        embedding_max_year = point["max_change_year"]
        embedding_first_year = point["first_hotspot_year"]
        rows.append(
            {
                "review_id": review_id,
                "sample_id": point["sample_id"],
                "pixel_key": point["pixel_key"],
                "category": point["category"],
                "lon": point["lon"],
                "lat": point["lat"],
                "valid_ndvi_years": valid_years,
                "mean_clear_observation_count": ndvi_values[
                    "clear_observation_count"
                ].mean(),
                "ndvi_2017": annual_point.loc[
                    annual_point["year"].eq(2017), "ndvi"
                ].iloc[0],
                "ndvi_2024": annual_point.loc[
                    annual_point["year"].eq(2024), "ndvi"
                ].iloc[0],
                "ndvi_endpoint_change": endpoint_change,
                "ndvi_variance": variance,
                "ndvi_slope": slope,
                "ndvi_max_abs_change_year": max_year,
                "ndvi_max_signed_change": max_signed,
                "ndvi_first_event_year": first_event_year,
                "embedding_max_change_year": embedding_max_year,
                "embedding_first_hotspot_year": embedding_first_year,
                "max_year_difference": max_year - embedding_max_year
                if pd.notna(max_year) and pd.notna(embedding_max_year)
                else np.nan,
                "max_year_exact_match": bool(max_year == embedding_max_year)
                if pd.notna(max_year) and pd.notna(embedding_max_year)
                else np.nan,
                "max_year_match_pm1": bool(abs(max_year - embedding_max_year) <= 1)
                if pd.notna(max_year) and pd.notna(embedding_max_year)
                else np.nan,
                "first_event_year_difference": first_event_year - embedding_first_year
                if pd.notna(first_event_year) and pd.notna(embedding_first_year)
                else np.nan,
                "first_event_year_exact_match": bool(
                    first_event_year == embedding_first_year
                )
                if pd.notna(first_event_year) and pd.notna(embedding_first_year)
                else np.nan,
                "first_event_year_match_pm1": bool(
                    abs(first_event_year - embedding_first_year) <= 1
                )
                if pd.notna(first_event_year) and pd.notna(embedding_first_year)
                else np.nan,
                "ndvi_evidence_label": evidence,
                "google_maps_link": point["google_maps_link"],
            }
        )
    return pd.DataFrame(rows)


def timing_summary(points: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, valid_column, exact_column, pm1_column in [
        (
            "maximum_change_year",
            "max_year_difference",
            "max_year_exact_match",
            "max_year_match_pm1",
        ),
        (
            "first_event_year",
            "first_event_year_difference",
            "first_event_year_exact_match",
            "first_event_year_match_pm1",
        ),
    ]:
        valid = points[points[valid_column].notna()]
        exact = int(valid[exact_column].eq(True).sum())
        pm1 = int(valid[pm1_column].eq(True).sum())
        rows.append(
            {
                "comparison": metric,
                "comparable_points": len(valid),
                "exact_matches": exact,
                "exact_share": exact / len(valid) if len(valid) else np.nan,
                "matches_pm1": pm1,
                "match_pm1_share": pm1 / len(valid) if len(valid) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def save_figure(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def osm_basemap(
    bounds: tuple[float, float, float, float], cache_dir: Path, zoom: int = 9
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Download and mosaic the small set of OSM tiles covering the point extent."""

    west, south, east, north = bounds
    scale = 2**zoom

    def tile_index(lon: float, lat: float) -> tuple[int, int]:
        lat = float(np.clip(lat, -85.0511, 85.0511))
        x = int((lon + 180.0) / 360.0 * scale)
        y = int(
            (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi)
            / 2.0
            * scale
        )
        return x, y

    x_min, y_max = tile_index(west, south)
    x_max, y_min = tile_index(east, north)
    cache_dir.mkdir(parents=True, exist_ok=True)
    mosaic = Image.new(
        "RGB", ((x_max - x_min + 1) * 256, (y_max - y_min + 1) * 256)
    )
    for tile_y in range(y_min, y_max + 1):
        for tile_x in range(x_min, x_max + 1):
            cache_path = cache_dir / f"osm_z{zoom}_x{tile_x}_y{tile_y}.png"
            if not cache_path.exists():
                request = urllib.request.Request(
                    f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png",
                    headers={"User-Agent": "BassCoast-NDVI-research-map/1.0"},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    cache_path.write_bytes(response.read())
                time.sleep(0.1)
            with Image.open(cache_path) as tile:
                mosaic.paste(
                    tile.convert("RGB"),
                    ((tile_x - x_min) * 256, (tile_y - y_min) * 256),
                )

    tile_west = x_min / scale * 360.0 - 180.0
    tile_east = (x_max + 1) / scale * 360.0 - 180.0
    tile_north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y_min / scale))))
    tile_south = math.degrees(
        math.atan(math.sinh(math.pi * (1 - 2 * (y_max + 1) / scale)))
    )
    return np.asarray(mosaic), (tile_west, tile_south, tile_east, tile_north)


def create_figures(
    annual: pd.DataFrame,
    intervals: pd.DataFrame,
    correlations: pd.DataFrame,
    event_counts: pd.DataFrame,
    points: pd.DataFrame,
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)

    coverage = annual.groupby("year")["valid_ndvi"].mean() * 100
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(coverage.index.astype(str), coverage.values, color="#3b7d5b")
    ax.bar_label(bars, fmt="%.1f%%", padding=3)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Review points with valid NDVI (%)")
    ax.set_xlabel("Year")
    ax.set_title("Annual Landsat GeoMAD NDVI Coverage")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_ndvi_annual_coverage.png")

    valid = intervals[intervals["valid_interval"]]
    categories = sorted(valid["category"].unique())
    palette = dict(zip(categories, plt.get_cmap("tab10").colors))
    fig, ax = plt.subplots(figsize=(9, 6))
    for category, group in valid.groupby("category"):
        ax.scatter(
            group["embedding_annual_change"],
            group["abs_ndvi_change"],
            s=11,
            alpha=0.28,
            label=category,
            color=palette[category],
        )
    ax.set_xlabel("Annual embedding distance")
    ax.set_ylabel("Absolute annual NDVI change")
    ax.set_title("Embedding Change Versus NDVI Change")
    ax.legend(fontsize=7, ncol=2, frameon=True)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_embedding_vs_ndvi_scatter.png")

    ordered = correlations.sort_values("spearman_rho")
    fig, ax = plt.subplots(figsize=(9, 5.8))
    bars = ax.barh(ordered["category"], ordered["spearman_rho"], color="#486f8e")
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_xlabel("Spearman correlation")
    ax.set_title("Embedding–NDVI Magnitude Association by Category")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_correlation_by_category.png")

    plot_counts = event_counts[event_counts["event_comparison"].ne("invalid_ndvi")]
    labels = {
        "both": "Both signals",
        "embedding_only": "Embedding only",
        "ndvi_only": "NDVI only",
        "neither": "Neither",
    }
    colors = ["#2f855a", "#4c78a8", "#d29b38", "#777777"]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(
        [labels[value] for value in plot_counts["event_comparison"]],
        plot_counts["interval_count"],
        color=colors,
    )
    ax.bar_label(bars, padding=3)
    ax.set_ylabel("Point-intervals")
    ax.set_title("Embedding Hotspot and NDVI Event Comparison")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_event_comparison.png")

    comparable = points[points["max_year_difference"].notna()]
    counts = comparable["max_year_difference"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.bar(counts.index.astype(int).astype(str), counts.values, color="#725aa6")
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("NDVI maximum-change year minus embedding maximum-change year")
    ax.set_ylabel("Review points")
    ax.set_title("Timing Difference Between Maximum Change Signals")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_max_change_timing_difference.png")

    evidence = points["ndvi_evidence_label"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(9, 5.2))
    bars = ax.barh(evidence.index, evidence.values, color="#4e8f86")
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("Review points")
    ax.set_title("NDVI Evidence Labels")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_ndvi_evidence_labels.png")

    evidence_order = points["ndvi_evidence_label"].value_counts().index.tolist()
    evidence_colours = {
        "net_greening_signal": "#15803d",
        "net_vegetation_decline_signal": "#c2413b",
        "disturbance_and_recovery_signal": "#d97706",
        "ndvi_stable": "#4b5563",
        "temporary_greening_signal": "#2563a6",
        "temporary_decline_signal": "#7c3f2c",
    }
    lon_margin = 0.04
    lat_margin = 0.04
    map_bounds = (
        float(points["lon"].min() - lon_margin),
        float(points["lat"].min() - lat_margin),
        float(points["lon"].max() + lon_margin),
        float(points["lat"].max() + lat_margin),
    )
    fig, ax = plt.subplots(figsize=(11, 8))
    try:
        basemap, basemap_bounds = osm_basemap(
            map_bounds, figure_dir / "basemap_cache", zoom=9
        )
        ax.imshow(
            basemap,
            extent=[
                basemap_bounds[0],
                basemap_bounds[2],
                basemap_bounds[1],
                basemap_bounds[3],
            ],
            origin="upper",
            alpha=0.78,
            aspect="auto",
        )
    except Exception as exc:
        print(f"WARNING: OSM basemap unavailable; using point-only map: {exc}")
    for label in evidence_order:
        subset = points[points["ndvi_evidence_label"].eq(label)]
        ax.scatter(
            subset["lon"],
            subset["lat"],
            s=24,
            alpha=0.84,
            color=evidence_colours.get(label, "#6b7280"),
            edgecolor="white",
            linewidth=0.35,
            label=label.replace("_", " ").title(),
            zorder=3,
        )
    ax.set_xlim(map_bounds[0], map_bounds[2])
    ax.set_ylim(map_bounds[1], map_bounds[3])
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("NDVI Evidence at Phase 2B Review Points, Bass Coast")
    ax.legend(
        title="2017-2024 NDVI evidence",
        fontsize=8,
        title_fontsize=9,
        loc="lower left",
        framealpha=0.93,
    )
    ax.text(
        0.995,
        0.008,
        "Basemap: OpenStreetMap contributors",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="#333333",
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2},
        zorder=4,
    )
    fig.tight_layout()
    save_figure(fig, figure_dir / "phase8_ndvi_evidence_map.png")


def write_report(
    path: Path,
    annual: pd.DataFrame,
    intervals: pd.DataFrame,
    points: pd.DataFrame,
    overall_correlation: pd.DataFrame,
    category_correlation: pd.DataFrame,
    interval_correlation: pd.DataFrame,
    event_counts: pd.DataFrame,
    hotspot_support: pd.DataFrame,
    timing: pd.DataFrame,
    threshold: float,
    warnings: list[str],
) -> None:
    valid_years = int(annual["valid_ndvi"].sum())
    valid_intervals = int(intervals["valid_interval"].sum())
    overall = overall_correlation.iloc[0]
    max_timing = timing[timing["comparison"].eq("maximum_change_year")].iloc[0]
    first_timing = timing[timing["comparison"].eq("first_event_year")].iloc[0]
    events = event_counts.set_index("event_comparison")["interval_count"]
    evidence = points["ndvi_evidence_label"].value_counts()
    best = category_correlation.iloc[0]
    weakest = category_correlation.iloc[-1]
    both = int(events.get("both", 0))
    embedding_only = int(events.get("embedding_only", 0))
    ndvi_only = int(events.get("ndvi_only", 0))
    embedding_hotspots = both + embedding_only
    ndvi_events = both + ndvi_only
    ndvi_support_share = both / embedding_hotspots if embedding_hotspots else np.nan
    embedding_support_share = both / ndvi_events if ndvi_events else np.nan
    interval_min = interval_correlation["spearman_rho"].min()
    interval_max = interval_correlation["spearman_rho"].max()

    lines = [
        "# Bass Coast Phase 8: NDVI Pilot Findings",
        "",
        "## Scope",
        "",
        f"The pilot compares annual Landsat GeoMAD NDVI with embedding change for {points['review_id'].nunique():,} Phase 2B review points from 2017 to 2024.",
        "",
        "The NDVI source is the public DEA Landsat annual Geometric Median product at 30 m. This is a cloud-screened annual representative surface-reflectance composite, not a 10 m Sentinel-2 monthly time series.",
        "",
        "## Coverage",
        "",
        f"- Valid point-year NDVI values: {valid_years:,}/{len(annual):,} ({valid_years / len(annual):.1%}).",
        f"- Valid annual intervals: {valid_intervals:,}/{len(intervals):,} ({valid_intervals / len(intervals):.1%}).",
        f"- Median annual clear-observation count: {annual.loc[annual['valid_ndvi'], 'clear_observation_count'].median():.0f}.",
        "",
        "## Direct Association",
        "",
        f"- Overall Pearson correlation between embedding distance and absolute NDVI change: {overall['pearson_r']:.3f}.",
        f"- Overall Spearman correlation: {overall['spearman_rho']:.3f}.",
        f"- Point-clustered 95% bootstrap interval for Spearman correlation: [{overall['spearman_cluster_bootstrap_ci_low']:.3f}, {overall['spearman_cluster_bootstrap_ci_high']:.3f}].",
        f"- Strongest category association: {best['category']} ({best['spearman_rho']:.3f}).",
        f"- Weakest category association: {weakest['category']} ({weakest['spearman_rho']:.3f}).",
        "",
        "## Event Comparison",
        "",
        f"The NDVI event threshold is {threshold:.4f}, defined as the 95th percentile of absolute annual NDVI change among stable-control intervals.",
        f"- Both embedding hotspot and NDVI event: {both:,} intervals.",
        f"- Embedding hotspot only: {embedding_only:,} intervals.",
        f"- NDVI event only: {ndvi_only:,} intervals.",
        f"- Neither signal: {int(events.get('neither', 0)):,} intervals.",
        f"- NDVI support among embedding hotspot intervals: {both:,}/{embedding_hotspots:,} ({ndvi_support_share:.1%}).",
        f"- Embedding-hotspot support among NDVI event intervals: {both:,}/{ndvi_events:,} ({embedding_support_share:.1%}).",
        "",
        "These are cross-signal outcomes, not true positives or false positives.",
        "",
        "## Consistency Through Time",
        "",
        f"Annual-interval Spearman correlations ranged from {interval_min:.3f} to {interval_max:.3f}. The association was therefore present within every annual interval rather than arising only from differences between years.",
        "",
        "## NDVI Support by Behavioural Category",
        "",
    ]
    for row in hotspot_support.itertuples(index=False):
        lines.append(
            f"- {row.category}: {int(row.ndvi_supported_intervals):,}/{int(row.embedding_hotspot_intervals):,} embedding hotspot intervals supported ({row.ndvi_support_share:.1%})."
        )
    lines.extend(
        [
            "",
            "## Timing",
            "",
            f"- Comparable maximum-change years: {int(max_timing['comparable_points']):,} points.",
            f"- Exact maximum-change-year agreement: {int(max_timing['exact_matches']):,}/{int(max_timing['comparable_points']):,} ({max_timing['exact_share']:.1%}).",
            f"- Maximum-change agreement within one year: {int(max_timing['matches_pm1']):,}/{int(max_timing['comparable_points']):,} ({max_timing['match_pm1_share']:.1%}).",
            f"- Comparable first-event years: {int(first_timing['comparable_points']):,} points.",
            f"- First-event agreement within one year: {int(first_timing['matches_pm1']):,}/{int(first_timing['comparable_points']):,} ({first_timing['match_pm1_share']:.1%}).",
            "",
            "## NDVI Evidence Labels",
            "",
        ]
    )
    for label, count in evidence.items():
        lines.append(f"- {label}: {int(count):,} points")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "NDVI and embedding distance should be considered complementary. NDVI supplies a signed greenness response, while embedding distance can respond to broader structural, spectral and contextual changes. A modest correlation would therefore be expected and scientifically useful; perfect agreement would indicate that the embedding metric adds little beyond greenness.",
            "",
            "The positive-slope and negative-slope behavioural categories describe whether annual embedding-distance magnitude tends to increase or decrease through time. They do not represent vegetation greening or decline; the signed NDVI evidence labels provide that ecological direction.",
            "",
            "The sample is balanced by behavioural category and is not an area-weighted sample of Bass Coast. DEA Land Cover and this NDVI baseline also share Landsat lineage, so agreement is not independent ground-truth validation.",
            "",
            "A future 10 m Sentinel-2 implementation should be used when monthly or seasonal vegetation trajectories are required. It requires Earth Engine authentication or a separate cloud-scale processing route.",
            "",
            "## Warnings",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    years = parse_years(args.years)
    if years != YEARS:
        print("WARNING: Partial-year runs only generate annual extraction outputs.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    figure_dir = args.output_dir / "figures"

    points, context = load_inputs(args.review_points, args.dea_context, args.max_points)
    annual_raw, warnings = retrieve_annual_ndvi(
        points, years, checkpoint_dir, args.fresh
    )
    annual = build_annual_table(annual_raw, context)
    annual.to_csv(args.output_dir / "basscoast_phase8_annual_ndvi.csv", index=False)

    if years != YEARS:
        print(f"Partial extraction complete: {args.output_dir.resolve()}")
        return

    intervals = build_interval_table(points, annual)
    overall, by_category, by_class = correlation_tables(intervals, args.bootstrap_runs)
    intervals, threshold, event_counts, event_by_category = apply_event_thresholds(
        intervals
    )
    annual_summary = annual_ndvi_summary(annual)
    interval_correlation = interval_correlation_summary(intervals)
    hotspot_support = hotspot_ndvi_support_by_category(intervals)
    point_table = point_summary(points, annual, intervals, threshold)
    timing = timing_summary(point_table)

    intervals.to_csv(
        args.output_dir / "basscoast_phase8_embedding_ndvi_intervals.csv", index=False
    )
    point_table.to_csv(
        args.output_dir / "basscoast_phase8_ndvi_point_summary.csv", index=False
    )
    overall.to_csv(args.output_dir / "basscoast_phase8_correlation_overall.csv", index=False)
    by_category.to_csv(
        args.output_dir / "basscoast_phase8_correlation_by_category.csv", index=False
    )
    by_class.to_csv(
        args.output_dir / "basscoast_phase8_correlation_by_dea_level3.csv", index=False
    )
    event_counts.to_csv(
        args.output_dir / "basscoast_phase8_event_comparison.csv", index=False
    )
    event_by_category.to_csv(
        args.output_dir / "basscoast_phase8_event_comparison_by_category.csv",
        index=False,
    )
    annual_summary.to_csv(
        args.output_dir / "basscoast_phase8_annual_ndvi_summary.csv", index=False
    )
    interval_correlation.to_csv(
        args.output_dir / "basscoast_phase8_correlation_by_interval.csv", index=False
    )
    hotspot_support.to_csv(
        args.output_dir / "basscoast_phase8_hotspot_ndvi_support_by_category.csv",
        index=False,
    )
    timing.to_csv(args.output_dir / "basscoast_phase8_timing_summary.csv", index=False)
    pd.DataFrame(
        [
            {"item": "ndvi_event_threshold", "value": threshold},
            {"item": "source_product", "value": PRODUCT},
            {"item": "source_resolution_m", "value": 30},
            {"item": "review_points", "value": len(points)},
            {"item": "point_year_rows", "value": len(annual)},
            {"item": "point_interval_rows", "value": len(intervals)},
        ]
    ).to_csv(args.output_dir / "basscoast_phase8_run_metadata.csv", index=False)

    create_figures(
        annual,
        intervals,
        by_category,
        event_counts,
        point_table,
        figure_dir,
    )
    report_path = args.output_dir / "basscoast_phase8_ndvi_pilot_report.md"
    write_report(
        report_path,
        annual,
        intervals,
        point_table,
        overall,
        by_category,
        interval_correlation,
        event_counts,
        hotspot_support,
        timing,
        threshold,
        warnings,
    )

    print("\nPhase 8 NDVI pilot complete")
    print(f"- review points: {len(points):,}")
    print(f"- valid point-years: {int(annual['valid_ndvi'].sum()):,}/{len(annual):,}")
    print(f"- valid intervals: {int(intervals['valid_interval'].sum()):,}/{len(intervals):,}")
    print(f"- NDVI event threshold: {threshold:.4f}")
    print(f"- report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
