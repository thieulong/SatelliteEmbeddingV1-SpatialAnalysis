#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import math
import os
from pathlib import Path
import sys
import textwrap

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib_cache").resolve()))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

PIPELINE_DIR = Path(__file__).resolve().parents[1] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from stage03_dea_enrichment import DEA_RASTER_ENV_OPTIONS, LEVEL3_LABELS, YEARS
from stage04_dea_wall_to_wall import dea_cog_url


CATEGORY_ORDER = [
    "positive_slope",
    "persistent_ge3",
    "persistent_ge2",
    "high_variance",
    "temporary_or_recovery_candidate",
    "negative_slope",
    "endpoint_hotspot",
    "sudden_candidate",
    "stable_control",
]

CATEGORY_LABELS = {
    "positive_slope": "Positive slope",
    "persistent_ge3": "Persistent >=3",
    "persistent_ge2": "Persistent >=2",
    "high_variance": "High variance",
    "temporary_or_recovery_candidate": "Temporary/recovery candidate",
    "negative_slope": "Negative slope",
    "endpoint_hotspot": "Endpoint hotspot",
    "sudden_candidate": "Sudden candidate",
    "stable_control": "Stable control",
}

LEVEL3_COLORS = {
    111: "#D6B656",
    112: "#3F7D4A",
    124: "#67B7A6",
    215: "#7A7D85",
    216: "#C7B299",
    220: "#4C78A8",
    255: "#F2F2F2",
}

SEQUENCE_LABELS = {
    0: "No data",
    1: "Stable natural",
    2: "Stable cultivated",
    3: "Stable artificial",
    4: "Natural -> cultivated",
    5: "Cultivated -> natural",
    6: "Transition to artificial",
    7: "Transition from artificial",
    8: "Water/bare/aquatic involved",
    9: "Temporary/return to start",
    10: "Other Level 3 change",
    11: "Stable other",
    12: "Stable water/bare/aquatic",
}

SEQUENCE_COLORS = {
    0: "#F2F2F2",
    1: "#3F7D4A",
    2: "#D6B656",
    3: "#6B6F76",
    4: "#C99700",
    5: "#6AA84F",
    6: "#A94442",
    7: "#8F6B55",
    8: "#4C78A8",
    9: "#8E63A9",
    10: "#D9822B",
    11: "#9AA0A6",
    12: "#86BBD8",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path)


def category_display(series: pd.Series) -> pd.Series:
    return series.map(lambda x: CATEGORY_LABELS.get(x, x))


def format_percent_axis(ax):
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(lambda x, _pos: f"{x:.0%}")


def clean_axes(ax, grid_axis="y"):
    ax.grid(axis=grid_axis, color="#D8DEE4", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)


def save_category_change_share(category_df: pd.DataFrame, path: Path):
    df = category_df.set_index("category").reindex(CATEGORY_ORDER).dropna(subset=["pixel_count"]).reset_index()
    labels = category_display(df["category"])
    x = np.arange(len(df))
    width = 0.38
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    ax.bar(x - width / 2, df["level3_changed_share"], width, label="DEA Level 3", color="#2F6F9F")
    ax.bar(x + width / 2, df["level4_changed_share"], width, label="DEA Level 4", color="#B86B2B")
    ax.set_title("DEA-Observed Land-Cover Change by Embedding Category", loc="left", fontsize=15, weight="bold")
    ax.set_ylabel("Share of category pixels with at least one DEA class change")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    format_percent_axis(ax)
    clean_axes(ax)
    ax.legend(frameon=False)
    for i, value in enumerate(df["level3_changed_share"]):
        ax.text(i - width / 2, value + 0.02, f"{value:.0%}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_phase3_vs_phase5(phase3_path: Path, category_df: pd.DataFrame, path: Path):
    if not phase3_path.exists():
        return False
    phase3 = pd.read_csv(phase3_path)
    p3 = phase3[["category", "level3_changed_share"]].rename(columns={"level3_changed_share": "phase3_sample"})
    p5 = category_df[["category", "level3_changed_share"]].rename(columns={"level3_changed_share": "phase5_wall_to_wall"})
    df = p5.merge(p3, on="category", how="inner").set_index("category").reindex(CATEGORY_ORDER).dropna().reset_index()
    labels = category_display(df["category"])
    x = np.arange(len(df))
    width = 0.38
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    ax.bar(x - width / 2, df["phase3_sample"], width, label="Phase 3 sample", color="#59656F")
    ax.bar(x + width / 2, df["phase5_wall_to_wall"], width, label="Phase 5 wall-to-wall", color="#3F7D4A")
    ax.set_title("Sampled Results Match the Wall-To-Wall Pattern", loc="left", fontsize=15, weight="bold")
    ax.set_ylabel("DEA Level 3 changed share")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    format_percent_axis(ax)
    clean_axes(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return True


def save_category_pixel_counts(category_df: pd.DataFrame, path: Path):
    df = category_df.set_index("category").reindex(CATEGORY_ORDER).dropna(subset=["pixel_count"]).reset_index()
    df = df.sort_values("pixel_count", ascending=True)
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.barh(category_display(df["category"]), df["pixel_count"], color="#2F6F9F")
    ax.set_title("Wall-To-Wall Pixel Counts by Embedding Category", loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Embedding-grid pixels")
    clean_axes(ax, grid_axis="x")
    for i, value in enumerate(df["pixel_count"]):
        ax.text(value, i, f" {int(value):,}", va="center", fontsize=8)
    ax.set_xlim(0, df["pixel_count"].max() * 1.16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_top_transitions(level3_df: pd.DataFrame, path: Path, top_n: int = 14):
    overall = level3_df.groupby("transition", as_index=False)["pixel_count"].sum()
    overall = overall.sort_values("pixel_count", ascending=False).head(top_n).sort_values("pixel_count")
    fig, ax = plt.subplots(figsize=(11, 7.4))
    ax.barh(overall["transition"], overall["pixel_count"], color="#B86B2B")
    ax.set_title("Dominant DEA Level 3 Endpoint Transitions Across Embedding Categories", loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Pixels counted across categories")
    clean_axes(ax, grid_axis="x")
    for i, value in enumerate(overall["pixel_count"]):
        ax.text(value, i, f" {int(value):,}", va="center", fontsize=8)
    ax.set_xlim(0, overall["pixel_count"].max() * 1.16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_sequence_types(sequence_df: pd.DataFrame, path: Path, top_n: int = 12):
    overall = sequence_df.groupby("level3_sequence_type", as_index=False)["pixel_count"].sum()
    overall = overall.sort_values("pixel_count", ascending=False).head(top_n).sort_values("pixel_count")
    fig, ax = plt.subplots(figsize=(10.5, 6.8))
    ax.barh(overall["level3_sequence_type"].str.replace("_", " "), overall["pixel_count"], color="#6B5B95")
    ax.set_title("DEA Level 3 Sequence Types Across Embedding Categories", loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Pixels counted across categories")
    clean_axes(ax, grid_axis="x")
    for i, value in enumerate(overall["pixel_count"]):
        ax.text(value, i, f" {int(value):,}", va="center", fontsize=8)
    ax.set_xlim(0, overall["pixel_count"].max() * 1.16)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_timing_alignment(timing_df: pd.DataFrame, path: Path):
    df = timing_df.set_index("category").reindex(CATEGORY_ORDER).dropna(subset=["level3_changed_pixels"]).reset_index()
    labels = category_display(df["category"])
    x = np.arange(len(df))
    width = 0.38
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    ax.bar(
        x - width / 2,
        df["match_max_change_year_pm1_share_of_l3_changed"],
        width,
        label="DEA first-change matches embedding max-change year (+/-1)",
        color="#3F7D4A",
    )
    ax.bar(
        x + width / 2,
        df["match_first_hotspot_year_pm1_share_of_l3_changed"],
        width,
        label="DEA first-change matches first-hotspot year (+/-1)",
        color="#6B5B95",
    )
    ax.set_title("Timing Alignment Between DEA and Embedding Signals", loc="left", fontsize=15, weight="bold")
    ax.set_ylabel("Share of DEA Level 3 changed pixels")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    format_percent_axis(ax)
    clean_axes(ax)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def downsample_shape(width: int, height: int, max_dim: int) -> tuple[int, int]:
    scale = min(max_dim / width, max_dim / height, 1.0)
    return max(1, int(round(height * scale))), max(1, int(round(width * scale)))


def read_downsampled(path: Path, max_dim: int, resampling: Resampling, fill_value=np.nan):
    with rasterio.open(path) as src:
        out_h, out_w = downsample_shape(src.width, src.height, max_dim)
        arr = src.read(1, out_shape=(out_h, out_w), masked=True, resampling=resampling)
        data = arr.filled(fill_value)
        bounds = src.bounds
        transform = src.transform
    return data, bounds, transform


def raster_extent(bounds):
    return [bounds.left, bounds.right, bounds.bottom, bounds.top]


def save_continuous_map(path: Path, title: str, output_path: Path, max_dim: int, cmap: str, percentile=(2, 98), diverging=False):
    data, bounds, _transform = read_downsampled(path, max_dim, Resampling.average, np.nan)
    data = np.asarray(data, dtype="float64")
    finite = np.isfinite(data)
    if not finite.any():
        return False
    vmin, vmax = np.nanpercentile(data[finite], percentile)
    if diverging:
        absmax = max(abs(vmin), abs(vmax))
        norm = TwoSlopeNorm(vcenter=0, vmin=-absmax, vmax=absmax)
    else:
        norm = None
    fig, ax = plt.subplots(figsize=(10, 7.5))
    image = ax.imshow(
        np.ma.masked_invalid(data),
        extent=raster_extent(bounds),
        origin="upper",
        cmap=cmap,
        vmin=None if diverging else vmin,
        vmax=None if diverging else vmax,
        norm=norm,
    )
    ax.set_title(title, loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return True


def save_discrete_raster_map(path: Path, title: str, output_path: Path, max_dim: int, classes: dict[int, str], colors: dict[int, str], mask_zero=False):
    data, bounds, _transform = read_downsampled(path, max_dim, Resampling.nearest, 0)
    data = np.asarray(data)
    if mask_zero:
        data = np.ma.masked_where(data == 0, data)
    codes = [code for code in classes if np.any(np.asarray(data) == code)]
    if not codes:
        return False
    codes = sorted(codes)
    cmap = ListedColormap([colors.get(code, "#D0D0D0") for code in codes])
    boundaries = [code - 0.5 for code in codes] + [codes[-1] + 0.5]
    norm = BoundaryNorm(boundaries, cmap.N)
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.imshow(data, extent=raster_extent(bounds), origin="upper", cmap=cmap, norm=norm)
    ax.set_title(title, loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    handles = [plt.Line2D([0], [0], marker="s", linestyle="", color=colors.get(code, "#D0D0D0"), label=classes[code]) for code in codes]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return True


def read_dea_level3_stack_downsampled(reference_path: Path, max_dim: int):
    with rasterio.open(reference_path) as reference:
        out_h, out_w = downsample_shape(reference.width, reference.height, max_dim)
        bounds = reference.bounds
        stack = []
        with rasterio.Env(**DEA_RASTER_ENV_OPTIONS):
            sources = []
            vrts = []
            try:
                for year in YEARS:
                    src = rasterio.open(dea_cog_url(year, "level3"))
                    sources.append(src)
                    vrt = WarpedVRT(
                        src,
                        crs=reference.crs,
                        transform=reference.transform,
                        width=reference.width,
                        height=reference.height,
                        resampling=Resampling.nearest,
                        src_nodata=255,
                        nodata=255,
                    )
                    vrts.append(vrt)
                    arr = vrt.read(1, out_shape=(out_h, out_w), masked=True, resampling=Resampling.nearest, out_dtype="uint16")
                    stack.append(arr.filled(255).astype("uint16", copy=False))
            finally:
                for vrt in vrts:
                    vrt.close()
                for src in sources:
                    src.close()
    return np.stack(stack, axis=0), bounds


def sequence_code_from_level3_stack(stack: np.ndarray) -> np.ndarray:
    complete = np.all(stack != 255, axis=0)
    start = stack[0]
    end = stack[-1]
    stable = complete & np.all(stack == start[None, :, :], axis=0)
    changed = complete & ~stable
    water_or_bare = np.any(np.isin(stack, [124, 216, 220]), axis=0)
    out = np.zeros(stack.shape[1:], dtype="uint8")
    out[stable & (start == 112)] = 1
    out[stable & (start == 111)] = 2
    out[stable & (start == 215)] = 3
    out[stable & np.isin(start, [124, 216, 220])] = 12
    out[stable & ~np.isin(start, [111, 112, 124, 215, 216, 220])] = 11
    out[changed & (start == end)] = 9
    out[changed & (start != 215) & (end == 215)] = 6
    out[changed & (start == 215) & (end != 215)] = 7
    out[changed & (start == 112) & (end == 111)] = 4
    out[changed & (start == 111) & (end == 112)] = 5
    remaining = changed & (out == 0)
    out[remaining & water_or_bare] = 8
    out[remaining & ~water_or_bare] = 10
    return out


def save_dea_level3_pair_map(stack: np.ndarray, bounds, output_path: Path):
    codes = [111, 112, 124, 215, 216, 220, 255]
    labels = {code: LEVEL3_LABELS[code] for code in codes}
    cmap = ListedColormap([LEVEL3_COLORS[code] for code in codes])
    norm = BoundaryNorm([code - 0.5 for code in codes] + [codes[-1] + 0.5], cmap.N)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), sharex=True, sharey=True)
    for ax, arr, year in zip(axes, [stack[0], stack[-1]], [YEARS[0], YEARS[-1]]):
        ax.imshow(arr, extent=raster_extent(bounds), origin="upper", cmap=cmap, norm=norm)
        ax.set_title(f"DEA Level 3 {year}", loc="left", fontsize=14, weight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
    handles = [plt.Line2D([0], [0], marker="s", linestyle="", color=LEVEL3_COLORS[code], label=labels[code]) for code in codes[:-1]]
    axes[-1].legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_sequence_map(sequence_codes: np.ndarray, bounds, output_path: Path, title: str):
    codes = [code for code in SEQUENCE_LABELS if np.any(sequence_codes == code)]
    codes = sorted(codes)
    cmap = ListedColormap([SEQUENCE_COLORS[code] for code in codes])
    norm = BoundaryNorm([code - 0.5 for code in codes] + [codes[-1] + 0.5], cmap.N)
    fig, ax = plt.subplots(figsize=(10.5, 7.8))
    ax.imshow(sequence_codes, extent=raster_extent(bounds), origin="upper", cmap=cmap, norm=norm)
    ax.set_title(title, loc="left", fontsize=15, weight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    handles = [plt.Line2D([0], [0], marker="s", linestyle="", color=SEQUENCE_COLORS[code], label=SEQUENCE_LABELS[code]) for code in codes if code != 0]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_hotspot_sequence_overlay(sequence_codes: np.ndarray, hotspot_path: Path, bounds, output_path: Path, max_dim: int):
    hotspot, _hotspot_bounds, _transform = read_downsampled(hotspot_path, max_dim, Resampling.nearest, 0)
    hotspot = np.asarray(hotspot) == 1
    overlay = np.where(hotspot, sequence_codes, 0).astype("uint8")
    save_sequence_map(overlay, bounds, output_path, "Endpoint Hotspots Coloured by DEA Level 3 Sequence Type")


def write_report(output_dir: Path, figure_paths: dict[str, Path], category_df: pd.DataFrame, level3_df: pd.DataFrame, sequence_df: pd.DataFrame):
    cat = category_df.set_index("category").reindex(CATEGORY_ORDER).reset_index()
    top_transitions = level3_df.groupby("transition", as_index=False)["pixel_count"].sum().sort_values("pixel_count", ascending=False).head(10)
    top_sequences = sequence_df.groupby("level3_sequence_type", as_index=False)["pixel_count"].sum().sort_values("pixel_count", ascending=False).head(10)

    def md_table(df: pd.DataFrame) -> str:
        out = df.copy()
        for col in out.columns:
            if pd.api.types.is_float_dtype(out[col]):
                out[col] = out[col].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
            elif pd.api.types.is_integer_dtype(out[col]):
                out[col] = out[col].map(lambda v: f"{int(v):,}" if pd.notna(v) else "")
            else:
                out[col] = out[col].map(lambda v: "" if pd.isna(v) else str(v))
        header = "| " + " | ".join(out.columns) + " |"
        divider = "| " + " | ".join(["---"] * len(out.columns)) + " |"
        rows = ["| " + " | ".join(map(str, row)) + " |" for row in out.to_numpy()]
        return "\n".join([header, divider, *rows])

    report = f"""# Bass Coast Phase 6 Visualization Report Draft

Generated at: {datetime.now().isoformat(timespec="seconds")}

## Purpose

This report package turns the Phase 5 wall-to-wall DEA summary into figures that can be used in a project update. The charts explain the evidence numerically, while the maps show where the embedding changes and DEA land-cover histories occur spatially.

## Key Message

The embedding-derived change categories are strongly enriched for DEA-observed land-cover change compared with the stable-control category. This supports the use of the embedding maps as a change-detection layer, while DEA Land Cover provides broad historical context for interpretation.

## Important Boundary

DEA Land Cover provides broad land-cover labels and transitions. It helps describe land-cover history, but it does not by itself prove the real-world cause of a change event.

## Figures

"""
    for title, path in figure_paths.items():
        report += f"### {title}\n\n![{title}](figures/{path.name})\n\n"

    report += f"""## Wall-To-Wall Category Summary

{md_table(cat[["category", "pixel_count", "level3_changed_share", "level4_changed_share", "level3_complete_share"]])}

## Top DEA Level 3 Transitions

{md_table(top_transitions)}

## Top DEA Level 3 Sequence Types

{md_table(top_sequences)}

## Why These Visualizations Matter

- Category charts show whether embedding-derived groups behave differently from stable controls.
- Phase 3 versus Phase 5 comparison checks whether the sampled analysis was representative of the full raster.
- Transition and sequence charts describe what broad DEA land-cover histories dominate the embedding-change categories.
- Raster maps show where the signals occur spatially, which is essential for stakeholder reporting and later manual review.
- Hotspot-overlay maps connect the AI-derived hotspot layer with DEA land-cover history in a visually interpretable way.

## Suggested Reporting Language

We have incorporated DEA Land Cover as an independent historical context layer for the embedding-derived change maps. The wall-to-wall summary shows that embedding-change categories have substantially higher DEA Level 3 land-cover change rates than stable controls, and the spatial maps show where those broad land-cover histories occur across Bass Coast.
"""
    report_path = output_dir / "basscoast_phase6_visual_report_draft.md"
    report_path.write_text(textwrap.dedent(report).strip() + "\n", encoding="utf-8")
    return report_path


def run(args) -> int:
    phase5_dir = Path(args.phase5_dir)
    phase3_dir = Path(args.phase3_dir)
    raster_dir = Path(args.raster_dir)
    output_dir = ensure_dir(Path(args.output_dir))
    figure_dir = ensure_dir(output_dir / "figures")

    category_df = read_csv(phase5_dir / "basscoast_phase5_wall_to_wall_category_summary.csv")
    level3_df = read_csv(phase5_dir / "basscoast_phase5_wall_to_wall_level3_transition_counts.csv")
    sequence_df = read_csv(phase5_dir / "basscoast_phase5_wall_to_wall_sequence_type_counts.csv")
    timing_df = read_csv(phase5_dir / "basscoast_phase5_wall_to_wall_timing_alignment.csv")

    figure_paths: dict[str, Path] = {}
    chart_specs = [
        ("DEA change share by embedding category", "phase6_dea_change_share_by_category.png"),
        ("Phase 3 sample versus Phase 5 wall-to-wall", "phase6_phase3_vs_phase5_comparison.png"),
        ("Wall-to-wall category pixel counts", "phase6_category_pixel_counts.png"),
        ("Top DEA Level 3 transitions", "phase6_top_level3_transitions.png"),
        ("DEA Level 3 sequence types", "phase6_level3_sequence_types.png"),
        ("Timing alignment", "phase6_timing_alignment.png"),
    ]
    chart_paths = {title: figure_dir / filename for title, filename in chart_specs}

    save_category_change_share(category_df, chart_paths["DEA change share by embedding category"])
    figure_paths["DEA change share by embedding category"] = chart_paths["DEA change share by embedding category"]
    phase3_summary = phase3_dir / "basscoast_phase3_category_validation_summary.csv"
    if save_phase3_vs_phase5(phase3_summary, category_df, chart_paths["Phase 3 sample versus Phase 5 wall-to-wall"]):
        figure_paths["Phase 3 sample versus Phase 5 wall-to-wall"] = chart_paths["Phase 3 sample versus Phase 5 wall-to-wall"]
    save_category_pixel_counts(category_df, chart_paths["Wall-to-wall category pixel counts"])
    figure_paths["Wall-to-wall category pixel counts"] = chart_paths["Wall-to-wall category pixel counts"]
    save_top_transitions(level3_df, chart_paths["Top DEA Level 3 transitions"])
    figure_paths["Top DEA Level 3 transitions"] = chart_paths["Top DEA Level 3 transitions"]
    save_sequence_types(sequence_df, chart_paths["DEA Level 3 sequence types"])
    figure_paths["DEA Level 3 sequence types"] = chart_paths["DEA Level 3 sequence types"]
    save_timing_alignment(timing_df, chart_paths["Timing alignment"])
    figure_paths["Timing alignment"] = chart_paths["Timing alignment"]

    map_specs = [
        (
            "Endpoint change intensity map",
            raster_dir / "basscoast_endpoint_change_2017_2024.tif",
            "Endpoint Change Intensity, 2017-2024",
            "phase6_map_endpoint_change.png",
            "viridis",
            False,
        ),
        (
            "Persistence count map",
            raster_dir / "basscoast_persistence_count.tif",
            "Embedding Hotspot Persistence Count",
            "phase6_map_persistence_count.png",
            "magma",
            False,
        ),
        (
            "Slope annual change map",
            raster_dir / "basscoast_slope_annual_change.tif",
            "Annual Change Slope",
            "phase6_map_slope_annual_change.png",
            "RdBu_r",
            True,
        ),
    ]
    for title, path, map_title, filename, cmap, diverging in map_specs:
        out = figure_dir / filename
        if save_continuous_map(path, map_title, out, args.map_max_dim, cmap, diverging=diverging):
            figure_paths[title] = out

    save_discrete_raster_map(
        raster_dir / "basscoast_endpoint_hotspots_2017_2024.tif",
        "Endpoint Hotspots, 2017-2024",
        figure_dir / "phase6_map_endpoint_hotspots.png",
        args.map_max_dim,
        {1: "Endpoint hotspot"},
        {1: "#A94442"},
        mask_zero=True,
    )
    figure_paths["Endpoint hotspot map"] = figure_dir / "phase6_map_endpoint_hotspots.png"

    year_classes = {year: str(year) for year in range(2018, 2025)}
    year_colors = {
        2018: "#F0E442",
        2019: "#E69F00",
        2020: "#56B4E9",
        2021: "#009E73",
        2022: "#0072B2",
        2023: "#D55E00",
        2024: "#CC79A7",
    }
    if save_discrete_raster_map(
        raster_dir / "basscoast_max_change_year.tif",
        "Year of Maximum Embedding Change",
        figure_dir / "phase6_map_max_change_year.png",
        args.map_max_dim,
        year_classes,
        year_colors,
        mask_zero=True,
    ):
        figure_paths["Max change year map"] = figure_dir / "phase6_map_max_change_year.png"

    print("Reading downsampled DEA Level 3 stack for map figures...")
    stack, bounds = read_dea_level3_stack_downsampled(raster_dir / "basscoast_endpoint_change_2017_2024.tif", args.dea_map_max_dim)
    save_dea_level3_pair_map(stack, bounds, figure_dir / "phase6_map_dea_level3_2017_2024.png")
    figure_paths["DEA Level 3 2017 and 2024 maps"] = figure_dir / "phase6_map_dea_level3_2017_2024.png"
    sequence_codes = sequence_code_from_level3_stack(stack)
    save_sequence_map(sequence_codes, bounds, figure_dir / "phase6_map_dea_level3_sequence_type.png", "DEA Level 3 Sequence Type, 2017-2024")
    figure_paths["DEA Level 3 sequence map"] = figure_dir / "phase6_map_dea_level3_sequence_type.png"
    save_hotspot_sequence_overlay(
        sequence_codes,
        raster_dir / "basscoast_endpoint_hotspots_2017_2024.tif",
        bounds,
        figure_dir / "phase6_map_hotspot_dea_sequence_overlay.png",
        args.dea_map_max_dim,
    )
    figure_paths["Endpoint hotspots with DEA sequence overlay"] = figure_dir / "phase6_map_hotspot_dea_sequence_overlay.png"

    report_path = write_report(output_dir, figure_paths, category_df, level3_df, sequence_df)

    inventory = pd.DataFrame(
        [{"title": title, "path": str(path), "size_kb": path.stat().st_size / 1024} for title, path in figure_paths.items() if path.exists()]
    )
    inventory.to_csv(output_dir / "basscoast_phase6_figure_inventory.csv", index=False)

    print(f"Saved figures to: {figure_dir}")
    print(f"Saved report draft to: {report_path}")
    print("\nGenerated figures:")
    for title, path in figure_paths.items():
        print(f"- {title}: {path}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Create Phase 6 report-ready visualizations for Bass Coast Phase 5 outputs.")
    parser.add_argument("--phase5-dir", default="data/processed/dea_wall_to_wall")
    parser.add_argument("--phase3-dir", default="data/processed/dea_sample")
    parser.add_argument("--raster-dir", default="data/raw/embedding_metrics")
    parser.add_argument("--output-dir", default="deliverables/generated/wall_to_wall")
    parser.add_argument("--map-max-dim", type=int, default=2200, help="Maximum pixel dimension for local raster map PNGs.")
    parser.add_argument("--dea-map-max-dim", type=int, default=1800, help="Maximum pixel dimension for downsampled DEA map PNGs.")
    return parser.parse_args()


def main():
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
