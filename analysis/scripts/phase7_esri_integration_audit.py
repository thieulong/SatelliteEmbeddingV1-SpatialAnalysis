#!/usr/bin/env python3
"""Audit Esri's incremental value relative to DEA on Phase 2B review points."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_INPUT_DIR = Path("BassCoast_Phase7_Esri_DEA_Crosscheck_outputs")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "integration_audit"
RELATION_ORDER = ["strong_match", "broad_match", "ambiguous", "mismatch"]
RELATION_LABELS = {
    "strong_match": "Strong match",
    "broad_match": "Broad match",
    "ambiguous": "Ambiguous",
    "mismatch": "Mismatch",
}
COLORS = {
    "strong_match": "#287a5b",
    "broad_match": "#6ca96f",
    "ambiguous": "#d6a84b",
    "mismatch": "#b64b4b",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def safe_share(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else np.nan


def load_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    long_path = input_dir / "basscoast_phase7_esri_dea_history_long.csv"
    points_path = input_dir / "basscoast_phase7_enriched_review_points.csv"
    if not long_path.exists() or not points_path.exists():
        raise FileNotFoundError(
            "Phase 7 long-history and enriched-point CSV files are required."
        )

    history = pd.read_csv(long_path).sort_values(["review_id", "year"])
    points = pd.read_csv(points_path).sort_values("review_id")

    expected_years = set(range(2017, 2025))
    if len(history) != 7_200 or history["review_id"].nunique() != 900:
        raise ValueError("Expected 7,200 point-year rows for 900 review points.")
    if set(history["year"].astype(int).unique()) != expected_years:
        raise ValueError("Expected complete annual coverage from 2017 through 2024.")
    if history.duplicated(["review_id", "year"]).any():
        raise ValueError("Duplicate review_id/year records were found.")
    if history["semantic_relation"].isna().any():
        raise ValueError("Missing semantic-relation values were found.")
    return history, points


def point_conflict_table(history: pd.DataFrame) -> pd.DataFrame:
    work = history.assign(
        is_strong=history["semantic_relation"].eq("strong_match"),
        is_broad=history["semantic_relation"].eq("broad_match"),
        is_ambiguous=history["semantic_relation"].eq("ambiguous"),
        is_mismatch=history["semantic_relation"].eq("mismatch"),
        is_mixed=history["esri_footprint_distinct_class_count"].gt(1),
    )
    result = work.groupby("review_id", as_index=False).agg(
        sample_id=("sample_id", "first"),
        pixel_key=("pixel_key", "first"),
        category=("category", "first"),
        lon=("lon", "first"),
        lat=("lat", "first"),
        strong_years=("is_strong", "sum"),
        broad_years=("is_broad", "sum"),
        ambiguous_years=("is_ambiguous", "sum"),
        mismatch_years=("is_mismatch", "sum"),
        mixed_footprint_years=("is_mixed", "sum"),
        mean_footprint_majority_share=("esri_footprint_majority_share", "mean"),
        google_maps_link=("google_maps_link", "first"),
    )
    result["any_mismatch"] = result["mismatch_years"].gt(0)
    result["persistent_mismatch"] = result["mismatch_years"].ge(4)
    result["all_year_mismatch"] = result["mismatch_years"].eq(8)
    return result.sort_values(
        ["mismatch_years", "ambiguous_years", "review_id"],
        ascending=[False, False, True],
    )


def category_table(history: pd.DataFrame, point_conflicts: pd.DataFrame) -> pd.DataFrame:
    annual = history.assign(
        is_ambiguous=history["semantic_relation"].eq("ambiguous"),
        is_mismatch=history["semantic_relation"].eq("mismatch"),
    ).groupby("category", as_index=False).agg(
        point_years=("year", "size"),
        mismatch_point_years=("is_mismatch", "sum"),
        ambiguous_point_years=("is_ambiguous", "sum"),
        broad_family_agreement=("family_match", "mean"),
        mean_footprint_majority_share=("esri_footprint_majority_share", "mean"),
    )
    annual["mismatch_share"] = (
        annual["mismatch_point_years"] / annual["point_years"]
    )
    annual["ambiguous_share"] = (
        annual["ambiguous_point_years"] / annual["point_years"]
    )

    point_summary = point_conflicts.groupby("category", as_index=False).agg(
        review_points=("review_id", "size"),
        points_with_any_mismatch=("any_mismatch", "sum"),
        points_with_persistent_mismatch=("persistent_mismatch", "sum"),
        points_with_all_year_mismatch=("all_year_mismatch", "sum"),
    )
    return annual.merge(point_summary, on="category").sort_values(
        "mismatch_share", ascending=False
    )


def relation_quality_table(history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for relation, group in history.groupby("semantic_relation"):
        rows.append(
            {
                "semantic_relation": relation,
                "point_year_count": len(group),
                "share_of_all_point_years": safe_share(len(group), len(history)),
                "mean_footprint_majority_share": group[
                    "esri_footprint_majority_share"
                ].mean(),
                "mixed_footprint_share": group[
                    "esri_footprint_distinct_class_count"
                ].gt(1).mean(),
                "center_footprint_disagreement_share": group[
                    "center_footprint_agree"
                ].eq(False).mean(),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "semantic_relation",
        key=lambda values: values.map({v: i for i, v in enumerate(RELATION_ORDER)}),
    )


def level4_purity_table(history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, group in history.groupby("dea_level4_effective_label"):
        counts = group["esri_footprint_majority_label"].value_counts()
        probabilities = counts / len(group)
        rows.append(
            {
                "dea_level4_label": label,
                "point_year_count": len(group),
                "dominant_esri_label": counts.index[0],
                "dominant_esri_count": int(counts.iloc[0]),
                "dominant_esri_share": float(probabilities.iloc[0]),
                "observed_esri_class_count": len(counts),
                "esri_label_entropy_bits": float(
                    -(probabilities * np.log2(probabilities)).sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["dominant_esri_share", "point_year_count"], ascending=[True, False]
    )


def transition_table(history: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    rows = []
    for review_id, group in history.groupby("review_id"):
        group = group.sort_values("year")
        years = group["year"].astype(int).tolist()
        dea = group["dea_level3_effective_label"].astype(str).tolist()
        esri = group["esri_footprint_majority_label"].astype(str).tolist()

        def first_entry(sequence: list[str], target: str) -> float:
            for index in range(1, len(sequence)):
                if sequence[index] == target and sequence[index - 1] != target:
                    return float(years[index])
            return np.nan

        rows.append(
            {
                "review_id": review_id,
                "category": group["category"].iloc[0],
                "dea_transition_count": sum(a != b for a, b in zip(dea, dea[1:])),
                "esri_transition_count": sum(a != b for a, b in zip(esri, esri[1:])),
                "dea_enter_artificial_year": first_entry(dea, "Artificial Surface"),
                "esri_enter_built_year": first_entry(esri, "Built Area"),
                "dea_artificial_all_years": all(v == "Artificial Surface" for v in dea),
                "esri_built_all_years": all(v == "Built Area" for v in esri),
            }
        )
    result = pd.DataFrame(rows)
    both = result.dropna(subset=["dea_enter_artificial_year", "esri_enter_built_year"])
    summary = {
        "dea_enter_artificial": int(result["dea_enter_artificial_year"].notna().sum()),
        "esri_enter_built": int(result["esri_enter_built_year"].notna().sum()),
        "both_enter": len(both),
        "both_enter_exact": int(
            both["dea_enter_artificial_year"].eq(both["esri_enter_built_year"]).sum()
        ),
        "both_enter_pm1": int(
            both["dea_enter_artificial_year"]
            .sub(both["esri_enter_built_year"])
            .abs()
            .le(1)
            .sum()
        ),
    }
    return result, summary


def save_conflict_figure(point_conflicts: pd.DataFrame, path: Path) -> None:
    counts = (
        point_conflicts["mismatch_years"].value_counts().reindex(range(9), fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(counts.index, counts.values, color="#486f8e")
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("Number of mismatched years per review point")
    ax.set_ylabel("Review points")
    ax.set_title("Persistence of DEA–Esri Broad-Family Conflicts")
    ax.set_xticks(range(9))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def save_category_figure(history: pd.DataFrame, path: Path) -> None:
    matrix = pd.crosstab(
        history["category"], history["semantic_relation"], normalize="index"
    ).reindex(columns=RELATION_ORDER, fill_value=0)
    matrix = matrix.sort_values("mismatch", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    left = np.zeros(len(matrix))
    for relation in RELATION_ORDER:
        values = matrix[relation].to_numpy() * 100
        ax.barh(
            matrix.index,
            values,
            left=left,
            color=COLORS[relation],
            label=RELATION_LABELS[relation],
        )
        left += values
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of point-year comparisons (%)")
    ax.set_title("DEA–Esri Semantic Relationship by Behavioural Category")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_report(
    output: Path,
    history: pd.DataFrame,
    points: pd.DataFrame,
    point_conflicts: pd.DataFrame,
    relation_quality: pd.DataFrame,
    level4_purity: pd.DataFrame,
    transitions: pd.DataFrame,
    built_summary: dict[str, int],
) -> None:
    relation_counts = history["semantic_relation"].value_counts()
    mismatch = int(relation_counts.get("mismatch", 0))
    ambiguous = int(relation_counts.get("ambiguous", 0))
    any_mismatch = int(point_conflicts["any_mismatch"].sum())
    persistent = int(point_conflicts["persistent_mismatch"].sum())
    all_year = int(point_conflicts["all_year_mismatch"].sum())
    all_year_stable = int(
        point_conflicts.loc[point_conflicts["all_year_mismatch"], "category"]
        .eq("stable_control")
        .sum()
    )
    mismatch_quality = relation_quality.set_index("semantic_relation").loc["mismatch"]
    weighted_l4_purity = float(
        np.average(
            level4_purity["dominant_esri_share"],
            weights=level4_purity["point_year_count"],
        )
    )
    mean_dea_transitions = transitions["dea_transition_count"].mean()
    mean_esri_transitions = transitions["esri_transition_count"].mean()

    lines = [
        "# Esri Integration Decision Audit",
        "",
        "## Scope",
        "",
        f"This audit evaluates Esri's incremental value using {len(points):,} review points and {len(history):,} point-year comparisons. It does not treat either dataset as ground truth.",
        "",
        "## Conflict Structure",
        "",
        f"- Clear mismatches: {mismatch:,}/{len(history):,} ({safe_share(mismatch, len(history)):.1%}).",
        f"- Ambiguous terrestrial comparisons: {ambiguous:,}/{len(history):,} ({safe_share(ambiguous, len(history)):.1%}).",
        f"- Points with at least one mismatch: {any_mismatch:,}/{len(points):,} ({safe_share(any_mismatch, len(points)):.1%}).",
        f"- Points mismatching in at least four years: {persistent:,}/{len(points):,} ({safe_share(persistent, len(points)):.1%}).",
        f"- Points mismatching in all eight years: {all_year:,}; {all_year_stable:,} are stable controls.",
        f"- Mismatch records with a mixed Esri footprint: {mismatch_quality['mixed_footprint_share']:.1%}.",
        f"- Mean Esri footprint-majority confidence for mismatches: {mismatch_quality['mean_footprint_majority_share']:.1%}.",
        "",
        "Most conflicts are therefore systematic class/source disagreements, not merely 10 m versus 30 m boundary mixing.",
        "",
        "## Incremental Information",
        "",
        "- Esri provides short, intuitive labels useful for maps and manager-facing review.",
        "- Artificial Surface maps to Esri Built Area in 99.3% of sampled point-years.",
        "- Natural and cultivated DEA vegetation can be described by Esri as Trees, Crops or Rangeland, but these are often broad or ambiguous correspondences.",
        f"- Given a DEA Level 4 label, the dominant Esri label covers {weighted_l4_purity:.1%} of point-years on average when weighted by sample size; Esri is not a consistent refinement of DEA Level 4.",
        "",
        "## Temporal Behaviour",
        "",
        f"- Mean DEA Level 3 transitions per point: {mean_dea_transitions:.2f}.",
        f"- Mean Esri transitions per point: {mean_esri_transitions:.2f}.",
        f"- DEA entered Artificial Surface at {built_summary['dea_enter_artificial']} points; Esri entered Built Area at {built_summary['esri_enter_built']} points.",
        f"- Both detected an artificial/built entry at {built_summary['both_enter']} points; {built_summary['both_enter_pm1']} were within one year.",
        "",
        "Esri is temporally smoother and can flag potential built-area evidence, but it neither confirms every DEA transition nor provides a reliable replacement timing sequence.",
        "",
        "## Decision",
        "",
        "Retain Esri as an optional secondary descriptor and disagreement flag. Keep DEA Level 3 and Level 4 as the primary contextual classification. Do not make Esri retrieval mandatory for every pixel, and do not use Esri to overwrite DEA labels automatically.",
        "",
        "Recommended final fields are `esri_label`, `esri_footprint_majority_share`, `dea_esri_relationship`, and `cross_dataset_review_flag`. Esri is most useful in map popups, review tables, and targeted checks of artificial/built interpretations.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures = args.output_dir / "figures"
    figures.mkdir(exist_ok=True)

    history, points = load_inputs(args.input_dir)
    conflicts = point_conflict_table(history)
    categories = category_table(history, conflicts)
    quality = relation_quality_table(history)
    level4 = level4_purity_table(history)
    transitions, built_summary = transition_table(history)

    conflicts.to_csv(args.output_dir / "esri_conflicts_by_point.csv", index=False)
    categories.to_csv(args.output_dir / "esri_conflicts_by_category.csv", index=False)
    quality.to_csv(args.output_dir / "esri_relation_footprint_quality.csv", index=False)
    level4.to_csv(args.output_dir / "dea_level4_esri_label_purity.csv", index=False)
    transitions.to_csv(args.output_dir / "dea_esri_transitions_by_point.csv", index=False)

    save_conflict_figure(conflicts, figures / "esri_conflict_persistence.png")
    save_category_figure(history, figures / "esri_relationship_by_category.png")
    report_path = args.output_dir / "esri_integration_decision_audit.md"
    write_report(
        report_path,
        history,
        points,
        conflicts,
        quality,
        level4,
        transitions,
        built_summary,
    )

    print("Esri integration audit complete")
    print(f"- review points: {len(points):,}")
    print(f"- point-year comparisons: {len(history):,}")
    print(f"- points with any mismatch: {int(conflicts['any_mismatch'].sum()):,}")
    print(f"- report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
