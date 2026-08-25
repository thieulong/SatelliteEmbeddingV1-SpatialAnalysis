import copy
import json
import textwrap
from pathlib import Path


NOTEBOOK_PATH = Path("BassCoast_Phase2_Pixel_Sampling.ipynb")


def markdown_cell(text):
    text = textwrap.dedent(text).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code_cell(text):
    text = textwrap.dedent(text).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
original_cells = copy.deepcopy(nb["cells"])

phase2b_markdown = markdown_cell(
    """
    ## 13. Phase 2B: Review-Ready Sample Points

    This section creates a smaller balanced subset of Phase 2 sampled pixels for manual and spatial review in Phase 3. It uses the existing `sampled_pixels_df` if available. If not, it loads the Phase 2 sampled CSV from the output folder.

    The selected points remain temporal-behaviour candidates only. They should not yet be interpreted as urbanisation, deforestation, agriculture, or any other real-world change class.
    """
)

phase2b_code = code_cell(
    """
    import math
    from pathlib import Path
    from datetime import datetime

    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    REVIEW_RANDOM_SEED = 42
    TARGET_POINTS_PER_CATEGORY = 100
    REPRESENTATIVE_TARGET = 40
    HIGH_SIGNAL_TARGET = 40

    phase2b_warnings = []

    def phase2b_warn(message):
        phase2b_warnings.append(message)
        print(f"WARNING: {message}")

    try:
        OUTPUT_DIR
    except NameError:
        try:
            PROJECT_FOLDER
        except NameError:
            from google.colab import drive
            drive.mount("/content/drive")
            PROJECT_FOLDER = Path("/content/drive/MyDrive/GEE_BassCoast_SatelliteEmbedding")
        OUTPUT_DIR = PROJECT_FOLDER / "BassCoast_Phase2_Pixel_Sampling_outputs"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    phase2_sampled_path = OUTPUT_DIR / "basscoast_phase2_sampled_pixels.csv"
    phase2b_review_path = OUTPUT_DIR / "basscoast_phase2b_review_points.csv"
    phase2b_summary_path = OUTPUT_DIR / "basscoast_phase2b_review_summary.csv"
    phase2b_bar_plot_path = OUTPUT_DIR / "phase2b_review_points_by_category.png"
    phase2b_map_plot_path = OUTPUT_DIR / "map_phase2b_review_points.png"

    if "sampled_pixels_df" not in globals() or sampled_pixels_df is None or sampled_pixels_df.empty:
        if phase2_sampled_path.exists():
            sampled_pixels_df = pd.read_csv(phase2_sampled_path)
            print(f"Loaded Phase 2 sampled pixels from: {phase2_sampled_path}")
        else:
            phase2b_warn(f"Could not find sampled_pixels_df in memory or CSV at {phase2_sampled_path}")
            sampled_pixels_df = pd.DataFrame()
    else:
        print("Using sampled_pixels_df already available in memory.")

    if sampled_pixels_df.empty:
        phase2b_review_df = pd.DataFrame()
    else:
        if "pixel_key" not in sampled_pixels_df.columns:
            sampled_pixels_df["pixel_key"] = sampled_pixels_df["row"].astype(str) + "_" + sampled_pixels_df["col"].astype(str)
            phase2b_warn("pixel_key column was missing and has been reconstructed from row/col.")

        category_order_2b = (
            category_order
            if "category_order" in globals()
            else sorted(sampled_pixels_df["category"].dropna().unique().tolist())
        )

        key_metrics = [
            "endpoint_change",
            "persistence_count",
            "variance_annual_change",
            "slope_annual_change",
        ]

        for column in key_metrics:
            if column not in sampled_pixels_df.columns:
                phase2b_warn(f"Missing key metric column: {column}")

        review_parts = []
        used_pixel_keys = set()
        rng_2b = np.random.default_rng(REVIEW_RANDOM_SEED)

        def available_rows(df):
            return df[~df["pixel_key"].isin(used_pixel_keys)].copy()

        def add_selection(rows, category, method, remaining):
            if remaining <= 0 or rows.empty:
                return 0
            selected = rows.head(remaining).copy()
            selected["selection_method"] = method
            review_parts.append(selected)
            used_pixel_keys.update(selected["pixel_key"].astype(str).tolist())
            return len(selected)

        def representative_order(df):
            present = [c for c in key_metrics if c in df.columns]
            if not present:
                return df.copy()

            metrics = df[present].apply(pd.to_numeric, errors="coerce")
            medians = metrics.median(skipna=True)
            scales = metrics.std(skipna=True).replace(0, np.nan)
            scales = scales.fillna(1.0)
            distance = (((metrics - medians) / scales) ** 2).sum(axis=1) ** 0.5

            ordered = df.copy()
            ordered["_representative_distance"] = distance
            return ordered.sort_values(["_representative_distance", "sample_id"], na_position="last").drop(columns=["_representative_distance"])

        def high_signal_order(df, category):
            ordered = df.copy()
            for column in key_metrics:
                if column in ordered.columns:
                    ordered[column] = pd.to_numeric(ordered[column], errors="coerce")

            if category in ["endpoint_hotspot", "sudden_candidate"]:
                return ordered.sort_values(["endpoint_change", "sample_id"], ascending=[False, True], na_position="last")
            if category in ["persistent_ge2", "persistent_ge3"]:
                return ordered.sort_values(["persistence_count", "endpoint_change", "sample_id"], ascending=[False, False, True], na_position="last")
            if category in ["high_variance", "temporary_or_recovery_candidate"]:
                return ordered.sort_values(["variance_annual_change", "sample_id"], ascending=[False, True], na_position="last")
            if category == "positive_slope":
                return ordered.sort_values(["slope_annual_change", "sample_id"], ascending=[False, True], na_position="last")
            if category == "negative_slope":
                return ordered.sort_values(["slope_annual_change", "sample_id"], ascending=[True, True], na_position="last")
            if category == "stable_control":
                endpoint = pd.to_numeric(ordered.get("endpoint_change", np.nan), errors="coerce")
                variance = pd.to_numeric(ordered.get("variance_annual_change", np.nan), errors="coerce")
                slope_abs = pd.to_numeric(ordered.get("slope_annual_change", np.nan), errors="coerce").abs()
                ordered["_stable_score"] = (
                    endpoint.rank(method="first", na_option="bottom")
                    + variance.rank(method="first", na_option="bottom")
                    + slope_abs.rank(method="first", na_option="bottom")
                )
                return ordered.sort_values(["_stable_score", "sample_id"], na_position="last").drop(columns=["_stable_score"])
            return ordered.sort_values("sample_id")

        for category in category_order_2b:
            category_df = sampled_pixels_df[sampled_pixels_df["category"] == category].copy()
            if category_df.empty:
                phase2b_warn(f"No Phase 2 samples found for category: {category}")
                continue

            target_n = min(TARGET_POINTS_PER_CATEGORY, len(category_df))
            representative_n = min(REPRESENTATIVE_TARGET, math.ceil(target_n / 2))
            high_signal_n = min(HIGH_SIGNAL_TARGET, target_n - representative_n)

            added = 0
            added += add_selection(
                representative_order(available_rows(category_df)),
                category,
                "representative",
                representative_n,
            )
            added += add_selection(
                high_signal_order(available_rows(category_df), category),
                category,
                "high_signal",
                high_signal_n,
            )

            remaining = target_n - added
            if remaining > 0:
                random_pool = available_rows(category_df)
                if not random_pool.empty:
                    random_pool = random_pool.sample(
                        n=min(remaining, len(random_pool)),
                        random_state=REVIEW_RANDOM_SEED,
                        replace=False,
                    )
                    added += add_selection(random_pool, category, "random", remaining)

            if added < target_n:
                phase2b_warn(f"Category {category} requested {target_n} points but only {added} unique points were selected.")

        if review_parts:
            phase2b_review_df = pd.concat(review_parts, ignore_index=True)
        else:
            phase2b_review_df = pd.DataFrame()

    required_phase2b_columns = [
        "review_id",
        "sample_id",
        "row",
        "col",
        "lon",
        "lat",
        "pixel_key",
        "category",
        "selection_method",
        "endpoint_change",
        "endpoint_hotspot",
        "persistence_count",
        "variance_annual_change",
        "slope_annual_change",
        "first_hotspot_year",
        "max_change_year",
        "cumulative_change",
        "mean_annual_change",
        "max_annual_change",
        "annual_change_2017_2018",
        "annual_change_2018_2019",
        "annual_change_2019_2020",
        "annual_change_2020_2021",
        "annual_change_2021_2022",
        "annual_change_2022_2023",
        "annual_change_2023_2024",
        "annual_hotspot_2017_2018",
        "annual_hotspot_2018_2019",
        "annual_hotspot_2019_2020",
        "annual_hotspot_2020_2021",
        "annual_hotspot_2021_2022",
        "annual_hotspot_2022_2023",
        "annual_hotspot_2023_2024",
        "google_maps_link",
    ]

    if phase2b_review_df.empty:
        for column in required_phase2b_columns:
            phase2b_review_df[column] = pd.Series(dtype="object")
    else:
        phase2b_review_df = phase2b_review_df.reset_index(drop=True)
        phase2b_review_df.insert(0, "review_id", np.arange(1, len(phase2b_review_df) + 1))
        phase2b_review_df["google_maps_link"] = (
            "https://www.google.com/maps?q="
            + phase2b_review_df["lat"].astype(str)
            + ","
            + phase2b_review_df["lon"].astype(str)
        )

        for column in required_phase2b_columns:
            if column not in phase2b_review_df.columns:
                phase2b_review_df[column] = np.nan
                phase2b_warn(f"Required output column was missing and filled with NaN: {column}")

        phase2b_review_df = phase2b_review_df[required_phase2b_columns]

    phase2b_review_df.to_csv(phase2b_review_path, index=False)

    category_counts_2b = (
        phase2b_review_df["category"].value_counts().rename_axis("category").reset_index(name="review_point_count")
        if not phase2b_review_df.empty
        else pd.DataFrame(columns=["category", "review_point_count"])
    )
    method_counts_2b = (
        phase2b_review_df["selection_method"].value_counts().rename_axis("selection_method").reset_index(name="review_point_count")
        if not phase2b_review_df.empty
        else pd.DataFrame(columns=["selection_method", "review_point_count"])
    )

    summary_rows = [
        {"section": "metadata", "item": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
        {"section": "metadata", "item": "total_review_points", "value": len(phase2b_review_df)},
        {"section": "metadata", "item": "number_of_categories", "value": int(phase2b_review_df["category"].nunique()) if not phase2b_review_df.empty else 0},
        {"section": "metadata", "item": "target_points_per_category", "value": TARGET_POINTS_PER_CATEGORY},
        {"section": "metadata", "item": "output_path", "value": str(phase2b_review_path)},
    ]
    summary_rows.extend(
        {"section": "category_count", "item": row["category"], "value": int(row["review_point_count"])}
        for _, row in category_counts_2b.iterrows()
    )
    summary_rows.extend(
        {"section": "selection_method_count", "item": row["selection_method"], "value": int(row["review_point_count"])}
        for _, row in method_counts_2b.iterrows()
    )
    summary_rows.extend(
        {"section": "warning", "item": f"warning_{idx}", "value": message}
        for idx, message in enumerate(phase2b_warnings, start=1)
    )
    phase2b_summary_df = pd.DataFrame(summary_rows)
    phase2b_summary_df.to_csv(phase2b_summary_path, index=False)

    if phase2b_review_df.empty:
        phase2b_warn("Plots skipped because no review points were created.")
    else:
        plt.figure(figsize=(10, 4))
        category_counts_for_plot = phase2b_review_df["category"].value_counts().sort_index()
        category_counts_for_plot.plot(kind="bar", color="#3b6ea8")
        plt.title("Phase 2B Review Points by Category")
        plt.xlabel("Category")
        plt.ylabel("Review point count")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        plt.savefig(phase2b_bar_plot_path, dpi=180, bbox_inches="tight")
        plt.show()

        plt.figure(figsize=(8, 7))
        categories_for_plot = sorted(phase2b_review_df["category"].dropna().unique())
        cmap = plt.get_cmap("tab10")
        for idx, category in enumerate(categories_for_plot):
            subset = phase2b_review_df[phase2b_review_df["category"] == category]
            plt.scatter(subset["lon"], subset["lat"], s=12, alpha=0.65, label=category, color=cmap(idx % 10))
        plt.title("Phase 2B Review Points")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.legend(title="Category", bbox_to_anchor=(1.04, 1), loc="upper left")
        plt.tight_layout()
        plt.savefig(phase2b_map_plot_path, dpi=180, bbox_inches="tight")
        plt.show()

    print("PHASE 2B REVIEW POINT SUMMARY")
    print("=" * 36)
    print(f"Total review points created: {len(phase2b_review_df)}")
    print("\\nCount per category:")
    if category_counts_2b.empty:
        print("- none")
    else:
        for _, row in category_counts_2b.iterrows():
            print(f"- {row['category']}: {int(row['review_point_count'])}")
    print(f"\\nSaved review CSV: {phase2b_review_path}")
    print(f"Saved summary CSV: {phase2b_summary_path}")
    print(f"Saved plot: {phase2b_bar_plot_path}")
    print(f"Saved plot: {phase2b_map_plot_path}")

    if phase2b_warnings:
        print("\\nWarnings:")
        for message in phase2b_warnings:
            print(f"- {message}")
    else:
        print("\\nWarnings: none")
    """
)

nb["cells"].extend([phase2b_markdown, phase2b_code])
NOTEBOOK_PATH.write_text(json.dumps(nb, indent=2), encoding="utf-8")

print(f"Appended {len(nb['cells']) - len(original_cells)} cells to {NOTEBOOK_PATH}")
