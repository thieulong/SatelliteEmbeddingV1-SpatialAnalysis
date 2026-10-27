"""Reconcile and summarise the completed 1,400-point national evidence pilot.

This tool records the accepted recovery lineage, applies the numerical and
point-identity gates, and produces design-area-weighted sensitivity estimates.
It does not select a national hot-spot threshold or estimate model accuracy.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


STRATA = ("NW", "NE", "CW", "CE", "SW", "SE", "TAS")
YEARS = tuple(range(2017, 2025))
ANNUAL = tuple(f"d{year}" for year in range(2017, 2024))
DISTANCES = ("endpoint", *ANNUAL)
VALID = tuple(f"v{year}" for year in YEARS)
THRESHOLDS = (0.35, 0.40, 0.45, 0.50, 0.55)
BOOTSTRAP_SEED = 20261007
BOOTSTRAP_REPLICATES = 10_000
IDENTITY_TOLERANCE = 1e-10
FROZEN_COORDINATE_TOLERANCE_DEGREES = 1e-12
HISTORICAL_COORDINATE_TOLERANCE_DEGREES = 1e-6

REQUIRED = {
    "stratum", "point_id", "frame_km2", "n_requested", "original_lon",
    "original_lat", "norm2017", "norm2024", "dot_endpoint",
    "worldcover2021", "longitude", "latitude", *DISTANCES, *VALID,
}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def input_paths(root: Path) -> list[Path]:
    raw = root / "data/raw/national_pilot"
    paths = sorted((raw / "2026-09-30").glob("sample_*.csv"))
    paths += [
        raw / "2026-10-04-recovery/recovery_SE_03.csv",
        raw / "2026-10-04-recovery/recovery_TAS_03.csv",
    ]
    paths += sorted((raw / "2026-10-05-benchmark").glob("benchmark_*.csv"))
    paths += sorted((raw / "2026-10-05-recovery").glob("recovery_*.csv"))
    paths += sorted(
        (raw / "2026-10-07-frozen-recovery").glob("frozen_recovery_*.csv")
    )
    paths += sorted(
        (raw / "2026-10-07-frozen-remaining").glob("frozen_remaining_*.csv")
    )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")
    if len(paths) != 39:
        raise ValueError(f"Expected 39 input files, found {len(paths)}")
    return paths


def canonical_manifest(root: Path) -> pd.DataFrame:
    raw = root / "data/raw/national_pilot"
    frames = [
        pd.read_csv(path)[["point_id", "original_lon", "original_lat"]]
        for path in sorted((raw / "2026-09-30").glob("sample_*.csv"))
    ]
    frames += [
        pd.read_csv(
            raw / "2026-10-07-point-stability/se_point_stability_20261007_A.csv"
        )[["point_id", "original_lon", "original_lat"]],
        pd.read_csv(
            raw / "2026-10-07-point-stability/tas_point_stability_20261007_B.csv"
        )[["point_id", "original_lon", "original_lat"]],
    ]
    manifest = pd.concat(frames, ignore_index=True)
    if len(manifest) != 1400 or not manifest.point_id.is_unique:
        raise ValueError("Canonical manifest is not 1,400 unique point IDs")
    return manifest


def reconcile(root: Path) -> tuple[pd.DataFrame, dict]:
    files = input_paths(root)
    accepted = []
    file_records = []
    excluded = []
    for path in files:
        data = pd.read_csv(path)
        missing = sorted(REQUIRED - set(data.columns))
        if missing:
            raise ValueError(f"{path.name}: missing columns {missing}")
        original_rows = len(data)
        if path.name == "recovery_TAS_FINE_03_01.csv":
            bad = data.loc[data.point_id == "TAS_46"]
            if len(bad) != 1:
                raise ValueError("Expected one non-canonical TAS_46 recovery row")
            excluded.append({
                "file": str(path.relative_to(root)),
                "point_id": "TAS_46",
                "reason": "non-canonical duplicate from randomPoints realisation A",
                "original_lon": float(bad.iloc[0].original_lon),
                "original_lat": float(bad.iloc[0].original_lat),
            })
            data = data.loc[data.point_id != "TAS_46"].copy()
        data["source_file"] = str(path.relative_to(root))
        accepted.append(data)
        file_records.append({
            "file": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "source_rows": original_rows,
            "accepted_rows": len(data),
        })

    sample = pd.concat(accepted, ignore_index=True)
    values = sample[list(DISTANCES)].to_numpy(float)
    flags = sample[list(VALID)].to_numpy(float)
    identity_error = np.abs(
        sample.endpoint.to_numpy(float) ** 2
        - (
            sample.norm2017.to_numpy(float) ** 2
            + sample.norm2024.to_numpy(float) ** 2
            - 2 * sample.dot_endpoint.to_numpy(float)
        )
    )

    manifest = canonical_manifest(root)
    compared = sample.merge(
        manifest,
        on="point_id",
        how="outer",
        suffixes=("", "_canonical"),
        indicator=True,
        validate="one_to_one",
    )
    compared["original_coordinate_max_abs_difference_degrees"] = np.maximum(
        np.abs(compared.original_lon - compared.original_lon_canonical),
        np.abs(compared.original_lat - compared.original_lat_canonical),
    )
    coordinate_exceptions = compared.loc[
        compared.original_coordinate_max_abs_difference_degrees > 1e-8,
        [
            "point_id", "source_file", "original_lon", "original_lat",
            "original_lon_canonical", "original_lat_canonical",
            "original_coordinate_max_abs_difference_degrees",
        ],
    ].to_dict("records")

    frozen = compared.source_file.str.contains("2026-10-07-frozen-", na=False)
    checks = {
        "accepted_rows_1400": len(sample) == 1400,
        "point_ids_unique": bool(sample.point_id.is_unique),
        "sampled_cells_unique": not sample.duplicated(["longitude", "latitude"]).any(),
        "canonical_id_set_exact": bool((compared._merge == "both").all()),
        "seven_strata_of_200": sample.groupby("stratum").size().to_dict()
        == {stratum: 200 for stratum in STRATA},
        "distances_finite": bool(np.isfinite(values).all()),
        "validity_flags_binary": bool(np.isin(flags, [0, 1]).all()),
        "endpoint_identity_within_tolerance": bool(
            identity_error.max() < IDENTITY_TOLERANCE
        ),
        "historical_coordinates_within_documented_tolerance": bool(
            compared.original_coordinate_max_abs_difference_degrees.max()
            < HISTORICAL_COORDINATE_TOLERANCE_DEGREES
        ),
        "frozen_coordinates_exact_within_tolerance": bool(
            compared.loc[
                frozen, "original_coordinate_max_abs_difference_degrees"
            ].max() < FROZEN_COORDINATE_TOLERANCE_DEGREES
        ),
    }
    qa = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": (
            "Completed bounded 1,400-point stratified evidence pilot; not a "
            "wall-to-wall national analysis"
        ),
        "input_files": file_records,
        "excluded_rows": excluded,
        "accepted_rows": len(sample),
        "unique_point_ids": int(sample.point_id.nunique()),
        "unique_sampled_cells": int(
            sample[["longitude", "latitude"]].drop_duplicates().shape[0]
        ),
        "rows_by_stratum": sample.groupby("stratum").size().to_dict(),
        "maximum_endpoint_identity_absolute_error": float(identity_error.max()),
        "maximum_original_coordinate_difference_degrees": float(
            compared.original_coordinate_max_abs_difference_degrees.max()
        ),
        "coordinate_exceptions_above_1e-8_degrees": coordinate_exceptions,
        "checks": checks,
    }
    if qa["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError(f"Completion QA failed: {failed}")
    return sample, qa


def weighted_proportion(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / np.sum(weights))


def weighted_quantiles(
    values: np.ndarray,
    weights: np.ndarray,
    probabilities: tuple[float, ...],
) -> dict[str, float]:
    order = np.argsort(values)
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order]) - 0.5 * weights[order]
    cumulative /= weights.sum()
    return {
        f"p{int(probability * 100):02d}": float(
            np.interp(probability, cumulative, sorted_values)
        )
        for probability in probabilities
    }


def bootstrap_interval(
    sample: pd.DataFrame,
    event: np.ndarray,
    eligible: np.ndarray,
) -> tuple[float, float]:
    """Stratified percentile interval for a weighted ratio estimate."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    numerator = np.zeros(BOOTSTRAP_REPLICATES)
    denominator = np.zeros(BOOTSTRAP_REPLICATES)
    for stratum in STRATA:
        take = np.flatnonzero(sample.stratum.to_numpy() == stratum)
        draw = rng.integers(0, len(take), size=(BOOTSTRAP_REPLICATES, len(take)))
        weight = float(sample.iloc[take[0]].frame_km2) / len(take)
        numerator += weight * (event[take][draw] & eligible[take][draw]).sum(axis=1)
        denominator += weight * eligible[take][draw].sum(axis=1)
    estimates = numerator / denominator
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def metric_record(
    sample: pd.DataFrame,
    metric: str,
    threshold: float,
    event: np.ndarray,
    eligible: np.ndarray,
    context: str,
) -> dict:
    weights = (sample.frame_km2 / sample.n_requested).to_numpy(float)
    estimate = weighted_proportion(event & eligible, weights) / weighted_proportion(
        eligible, weights
    )
    low, high = bootstrap_interval(sample, event, eligible)
    return {
        "metric": metric,
        "threshold_strictly_greater_than": threshold,
        "context": context,
        "eligible_sample_points": int(eligible.sum()),
        "unweighted_event_points": int((event & eligible).sum()),
        "area_weighted_proportion": estimate,
        "stratified_bootstrap_95_percent_low": low,
        "stratified_bootstrap_95_percent_high": high,
    }


def summarise(sample: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    flags = sample[list(VALID)].to_numpy(int)
    common_valid = np.all(flags == 1, axis=1)
    known_non_water = common_valid & ~sample.worldcover2021.isin([0, 80]).to_numpy()
    contexts = {
        "all_boundary_sample_points": common_valid,
        "worldcover_known_non_water_context": known_non_water,
    }
    annual_values = sample[list(ANNUAL)].to_numpy(float)
    records = []
    for threshold in THRESHOLDS:
        for context, eligible in contexts.items():
            records.append(metric_record(
                sample,
                "endpoint_2017_to_2024",
                threshold,
                sample.endpoint.to_numpy(float) > threshold,
                eligible,
                context,
            ))
            records.append(metric_record(
                sample,
                "any_annual_interval_2017_to_2024",
                threshold,
                np.any(annual_values > threshold, axis=1),
                eligible,
                context,
            ))
            for column in ANNUAL:
                records.append(metric_record(
                    sample,
                    f"annual_interval_{column[1:]}_to_{int(column[1:]) + 1}",
                    threshold,
                    sample[column].to_numpy(float) > threshold,
                    eligible,
                    context,
                ))
    sensitivity = pd.DataFrame(records)
    weights = (sample.frame_km2 / sample.n_requested).to_numpy(float)
    frame_areas = sample.groupby("stratum").frame_km2.mean().to_dict()
    comparison_threshold = 0.45
    threshold_diagnostics = {}
    for stratum in STRATA:
        group = sample.loc[sample.stratum == stratum]
        threshold_diagnostics[stratum] = {
            column: {
                "event_points": int((group[column] > comparison_threshold).sum()),
                "sample_proportion": float(
                    (group[column] > comparison_threshold).mean()
                ),
            }
            for column in DISTANCES
        }
    summary = {
        "interpretation_boundary": (
            "Threshold exceedance is an embedding-change detection signal. It is "
            "not a confirmed causal event, model-accuracy label, or validated "
            "national hot-spot threshold. WorldCover is contextual evidence only."
        ),
        "estimator": (
            "Seven-stratum design-area-weighted proportion; 200 sampled points "
            "per stratum. Intervals are 10,000-replicate stratified nonparametric "
            "percentile bootstrap intervals with seed 20261007."
        ),
        "threshold_rule": "strict distance > threshold",
        "thresholds_compared": list(THRESHOLDS),
        "total_frame_area_km2": float(sum(frame_areas.values())),
        "frame_area_km2_by_stratum": frame_areas,
        "common_eight_year_valid_points": int(common_valid.sum()),
        "weighted_common_eight_year_valid_support": weighted_proportion(
            common_valid, weights
        ),
        "worldcover_known_non_water_points": int(known_non_water.sum()),
        "weighted_worldcover_known_non_water_support": weighted_proportion(
            known_non_water, weights
        ),
        "worldcover_counts": {
            str(int(key)): int(value)
            for key, value in sample.worldcover2021.value_counts().sort_index().items()
        },
        "area_weighted_distance_quantiles": {
            column: weighted_quantiles(
                sample[column].to_numpy(float),
                weights,
                (0.50, 0.75, 0.90, 0.95, 0.99),
            )
            for column in DISTANCES
        },
        "unweighted_stratum_diagnostics_at_strict_0_45": threshold_diagnostics,
        "sensitivity_rows": len(sensitivity),
    }
    return sensitivity, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/national_pilot/2026-10-07"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir

    sample, qa = reconcile(root)
    sensitivity, summary = summarise(sample)
    out.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out / "accepted_sample_1400.csv", index=False)
    sensitivity.to_csv(out / "threshold_sensitivity.csv", index=False)
    (out / "frozen_manifest_completion_qa.json").write_text(
        json.dumps(qa, indent=2) + "\n"
    )
    (out / "weighted_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        "qa_status": qa["status"],
        "accepted_rows": qa["accepted_rows"],
        "unique_point_ids": qa["unique_point_ids"],
        "unique_sampled_cells": qa["unique_sampled_cells"],
        **summary,
        "outputs": [
            str(path.relative_to(root))
            for path in [
                out / "accepted_sample_1400.csv",
                out / "frozen_manifest_completion_qa.json",
                out / "threshold_sensitivity.csv",
                out / "weighted_summary.json",
            ]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
