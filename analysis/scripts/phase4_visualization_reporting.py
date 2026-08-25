#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import textwrap

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


COLORS = {
    "blue": "#2F6F9F",
    "green": "#3F7D4A",
    "orange": "#B86B2B",
    "purple": "#6B5B95",
    "red": "#A94442",
    "gray": "#59656F",
    "light": "#E9EEF2",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_required_csv(base_dir: Path, name: str) -> pd.DataFrame:
    path = base_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path)


def save_barh(df, value_col, label_col, title, xlabel, output_path, color=COLORS["blue"], percent=False):
    plot_df = df[[label_col, value_col]].copy().sort_values(value_col, ascending=True)
    fig_height = max(4.5, 0.42 * len(plot_df) + 1.3)
    fig, ax = plt.subplots(figsize=(10.5, fig_height))
    ax.barh(plot_df[label_col], plot_df[value_col], color=color)
    ax.set_title(title, loc="left", fontsize=14, weight="bold")
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", color="#D8DEE4", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    for idx, value in enumerate(plot_df[value_col]):
        label = f"{value:.1%}" if percent else f"{int(value):,}"
        ax.text(value, idx, f" {label}", va="center", fontsize=9)
    if percent:
        ax.set_xlim(0, max(1.0, plot_df[value_col].max() * 1.12))
    else:
        ax.set_xlim(0, plot_df[value_col].max() * 1.12)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_category_change_share(category_summary, output_path):
    plot_df = category_summary.sort_values("level3_changed_share", ascending=False)
    x = range(len(plot_df))
    width = 0.38
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.bar([i - width / 2 for i in x], plot_df["level3_changed_share"], width=width, label="DEA Level 3", color=COLORS["blue"])
    ax.bar([i + width / 2 for i in x], plot_df["level4_changed_share"], width=width, label="DEA Level 4", color=COLORS["orange"])
    ax.set_title("DEA Change Share by Embedding Category", loc="left", fontsize=14, weight="bold")
    ax.set_ylabel("Share of sampled points with at least one DEA class change")
    ax.set_xticks(list(x))
    ax.set_xticklabels(plot_df["category"], rotation=35, ha="right")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", color="#D8DEE4", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_timing_alignment(alignment, output_path):
    plot_df = alignment.copy()
    plot_df["max_year_share"] = plot_df["match_max_year_pm1_share_of_changed"].fillna(0)
    plot_df["hotspot_year_share"] = plot_df["match_first_hotspot_year_pm1_share_of_changed"].fillna(0)
    plot_df = plot_df.sort_values("max_year_share", ascending=False)
    x = range(len(plot_df))
    width = 0.38
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.bar([i - width / 2 for i in x], plot_df["max_year_share"], width=width, label="Matches max_change_year (+/-1)", color=COLORS["green"])
    ax.bar([i + width / 2 for i in x], plot_df["hotspot_year_share"], width=width, label="Matches first_hotspot_year (+/-1)", color=COLORS["purple"])
    ax.set_title("DEA First-Change Timing Alignment", loc="left", fontsize=14, weight="bold")
    ax.set_ylabel("Share of DEA-changed points")
    ax.set_xticks(list(x))
    ax.set_xticklabels(plot_df["category"], rotation=35, ha="right")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", color="#D8DEE4", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_transition_matrix(transition_counts, output_path):
    matrix = transition_counts.pivot_table(
        index="level3_2017",
        columns="level3_2024",
        values="points",
        aggfunc="sum",
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(9, 7.5))
    image = ax.imshow(matrix.values, cmap="YlGnBu")
    ax.set_title("DEA Level 3 Transition Matrix: 2017 to 2024", loc="left", fontsize=14, weight="bold")
    ax.set_xlabel("DEA Level 3 in 2024")
    ax.set_ylabel("DEA Level 3 in 2017")
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_yticks(range(len(matrix.index)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix.values[i, j])
            if value:
                ax.text(j, i, f"{value:,}", ha="center", va="center", fontsize=8, color="#14213D")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Points")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_high_confidence_map(candidates, output_path):
    if candidates.empty:
        return
    top = candidates.head(250).copy()
    categories = list(top["category"].dropna().unique())
    palette = plt.get_cmap("tab10")
    color_map = {cat: palette(i % 10) for i, cat in enumerate(categories)}
    fig, ax = plt.subplots(figsize=(8.5, 7))
    for category, group in top.groupby("category"):
        ax.scatter(group["lon"], group["lat"], s=28, alpha=0.78, label=category, color=color_map[category])
    ax.set_title("High-Confidence Review Candidates", loc="left", fontsize=14, weight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(color="#D8DEE4", linewidth=0.7)
    ax.legend(frameon=False, fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def markdown_table(df, max_rows=12):
    table = df.head(max_rows).copy()
    for col in table.columns:
        if pd.api.types.is_float_dtype(table[col]):
            table[col] = table[col].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
        else:
            table[col] = table[col].map(lambda v: "" if pd.isna(v) else str(v))
    header = "| " + " | ".join(table.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(table.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in table.to_numpy(dtype=str)]
    return "\n".join([header, divider, *rows])


def write_report(output_dir, phase3_dir, summary, category_summary, transition_counts, sequence_types, alignment, chart_paths):
    summary_map = dict(zip(summary["item"], summary["value"]))
    points = int(float(summary_map.get("total_points", 0)))
    total_records = int(float(summary_map.get("total_point_year_records", 0)))
    level3_changed = int(float(summary_map.get("level3_changed_points", 0)))
    level4_changed = int(float(summary_map.get("level4_changed_points", 0)))
    complete_l3 = int(float(summary_map.get("level3_complete_effective_sequences", 0)))
    warnings = int(float(summary_map.get("warnings", 0)))

    report = f"""# Bass Coast Phase 4 Visualization and Reporting

Generated at: {datetime.now().isoformat(timespec="seconds")}

## Input

Source folder: `{phase3_dir}`

This report visualizes the merged local Phase 3 DEA Land Cover pipeline outputs.

## Coverage Summary

- Sampled points processed: {points:,}
- Point-year DEA records: {total_records:,}
- Complete DEA Level 3 sequences: {complete_l3:,}/{points:,}
- DEA Level 3 changed points: {level3_changed:,}/{points:,} ({level3_changed / points:.1%})
- DEA Level 4 changed points: {level4_changed:,}/{points:,} ({level4_changed / points:.1%})
- Warnings: {warnings:,}

## Important Interpretation Boundary

DEA assigned usable Level 3 and Level 4 labels for every sampled point-year in this run. That means coverage is complete for the sampled dataset.

This does not mean DEA can classify every possible real-world land-change process. DEA provides broad categorical land-cover labels. It supports statements like `Natural Terrestrial Vegetation -> Cultivated Terrestrial Vegetation`, but it does not by itself prove specific causes such as construction, clearing, restoration, plantation activity, crop rotation, or management intervention.

## Charts

![DEA change share by category]({chart_paths['category_change'].name})

![Timing alignment]({chart_paths['timing_alignment'].name})

![Top transitions]({chart_paths['top_transitions'].name})

![Sequence types]({chart_paths['sequence_types'].name})

![Transition matrix]({chart_paths['transition_matrix'].name})

![High confidence candidates]({chart_paths['candidate_map'].name})

## Category Summary

{markdown_table(category_summary[['category', 'points', 'level3_changed_points', 'level3_changed_share', 'level4_changed_points', 'level4_changed_share']], max_rows=20)}

## Top DEA Level 3 Transitions

{markdown_table(transition_counts, max_rows=15)}

## Sequence Types

{markdown_table(sequence_types, max_rows=15)}

## Timing Alignment

{markdown_table(alignment, max_rows=20)}

## Practical Conclusion

The sampled embedding-change categories are clearly enriched for DEA Level 3 land-cover change compared with stable controls. The dominant full-sample signal is vegetation class change, especially natural/cultivated switching. Artificial-surface transitions are present but smaller.

## Recommended Next Step

Use these outputs for a concise project report section, then create a spatial review package for the highest-confidence examples if manual validation is needed.
"""
    report_path = output_dir / "basscoast_phase4_visual_report.md"
    report_path.write_text(textwrap.dedent(report).strip() + "\n", encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase3-dir", default="BassCoast_Phase3_DEA_LandCover_Pipeline_outputs_full_sample")
    parser.add_argument("--output-dir", default="BassCoast_Phase4_Visualization_Report_outputs")
    args = parser.parse_args()

    phase3_dir = Path(args.phase3_dir)
    output_dir = ensure_dir(Path(args.output_dir))

    summary = read_required_csv(phase3_dir, "basscoast_phase3_pipeline_summary.csv")
    category_summary = read_required_csv(phase3_dir, "basscoast_phase3_category_validation_summary.csv")
    transition_counts = read_required_csv(phase3_dir, "basscoast_phase3_level3_transition_counts.csv")
    sequence_types = read_required_csv(phase3_dir, "basscoast_phase3_sequence_type_counts.csv")
    alignment = read_required_csv(phase3_dir, "basscoast_phase3_first_change_alignment.csv")
    candidates = read_required_csv(phase3_dir, "basscoast_phase3_high_confidence_review_candidates.csv")

    chart_paths = {
        "category_change": output_dir / "phase4_dea_change_share_by_category.png",
        "timing_alignment": output_dir / "phase4_timing_alignment_by_category.png",
        "top_transitions": output_dir / "phase4_top_level3_transitions.png",
        "sequence_types": output_dir / "phase4_sequence_type_counts.png",
        "transition_matrix": output_dir / "phase4_level3_transition_matrix.png",
        "candidate_map": output_dir / "phase4_high_confidence_candidate_map.png",
    }

    plot_category_change_share(category_summary, chart_paths["category_change"])
    plot_timing_alignment(alignment, chart_paths["timing_alignment"])
    save_barh(
        transition_counts.head(15),
        "points",
        "level3_transition_2017_2024",
        "Most Common DEA Level 3 Transitions: 2017 to 2024",
        "Sampled points",
        chart_paths["top_transitions"],
        color=COLORS["green"],
    )
    save_barh(
        sequence_types,
        "points",
        "level3_sequence_type",
        "DEA Level 3 Sequence Types",
        "Sampled points",
        chart_paths["sequence_types"],
        color=COLORS["purple"],
    )
    plot_transition_matrix(transition_counts, chart_paths["transition_matrix"])
    plot_high_confidence_map(candidates, chart_paths["candidate_map"])

    report_path = write_report(output_dir, phase3_dir, summary, category_summary, transition_counts, sequence_types, alignment, chart_paths)

    print(f"Saved Phase 4 outputs to: {output_dir}")
    print(f"Report: {report_path}")
    for key, path in chart_paths.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()
