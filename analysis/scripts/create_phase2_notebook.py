import json
import textwrap
from pathlib import Path


NOTEBOOK_NAME = "BassCoast_Phase2_Pixel_Sampling.ipynb"


def md(text):
    text = textwrap.dedent(text).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text):
    text = textwrap.dedent(text).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = [
    md(
        """
        # Bass Coast Phase 2 Pixel Sampling

        Phase 1 confirmed that the exported Earth Engine rasters load correctly, align spatially, and are healthy enough for analysis.

        Phase 2 creates a manageable sampled pixel-level table from temporal behaviour candidate categories. This is not real-world interpretation yet. Categories such as `sudden_candidate`, `persistent_ge2`, and `high_variance` describe temporal raster behaviour only; later phases can compare these samples with DEA Land Cover, HIF/EII, NearMap, or field validation evidence.
        """
    ),
    md("## 1. Project Context"),
    code(
        """
        PROJECT_NAME = "Bass Coast Satellite Embedding V1 - Phase 2 Pixel Sampling"
        print(PROJECT_NAME)
        print("Goal: sampled pixel-level characterization table from aligned Phase 1 raster stack.")
        print("Important: this notebook does not flatten all pixels and does not classify real-world change types.")
        """
    ),
    md("## 2. Setup and Imports"),
    code(
        """
        import importlib.util
        import subprocess
        import sys

        def ensure_package(import_name, pip_name=None):
            if importlib.util.find_spec(import_name) is None:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pip_name or import_name])

        ensure_package("rasterio")

        import fnmatch
        import json
        import math
        import shutil
        from pathlib import Path
        from datetime import datetime
        import warnings

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import xy
        from rasterio.warp import transform as transform_coords
        from rasterio.windows import Window

        warnings.filterwarnings("ignore", category=RuntimeWarning)
        pd.set_option("display.max_columns", 120)
        pd.set_option("display.max_rows", 120)

        RANDOM_SEED = 42
        MAX_SAMPLES_PER_CATEGORY = 10_000
        WINDOW_SIZE = 1024
        THRESHOLD_SAMPLE_STRIDE = 8

        rng = np.random.default_rng(RANDOM_SEED)
        warning_messages = []

        from google.colab import drive
        drive.mount("/content/drive")

        PROJECT_FOLDER = Path("/content/drive/MyDrive/GEE_BassCoast_SatelliteEmbedding")
        OUTPUT_DIR = PROJECT_FOLDER / "BassCoast_Phase2_Pixel_Sampling_outputs"
        FIGURE_DIR = OUTPUT_DIR / "figures"
        TABLE_DIR = OUTPUT_DIR / "tables"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        FIGURE_DIR.mkdir(parents=True, exist_ok=True)
        TABLE_DIR.mkdir(parents=True, exist_ok=True)

        print(f"Project folder: {PROJECT_FOLDER}")
        print(f"Output folder: {OUTPUT_DIR}")
        print(f"Random seed: {RANDOM_SEED}")
        """
    ),
    md("## 3. File Discovery"),
    code(
        """
        def warn(message):
            warning_messages.append(message)
            print(f"WARNING: {message}")

        def discover_files(folder, suffixes=(".tif", ".tiff", ".csv")):
            if not folder.exists():
                warn(f"Project folder not found: {folder}")
                return []
            suffixes = tuple(s.lower() for s in suffixes)
            return sorted(
                [p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith(suffixes)],
                key=lambda p: p.name.lower(),
            )

        def matches_any(path, patterns):
            name = path.name.lower()
            return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in patterns)

        def find_one(label, patterns, files):
            matches = [p for p in files if matches_any(p, patterns)]
            if not matches:
                warn(f"Missing expected file for '{label}'. Patterns: {patterns}")
                return None
            if len(matches) > 1:
                matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)
                warn(f"Multiple matches for '{label}'. Using most recently modified: {matches[0].name}")
            return matches[0]

        tif_files = discover_files(PROJECT_FOLDER, suffixes=(".tif", ".tiff"))
        print(f"GeoTIFF files discovered: {len(tif_files)}")

        core_patterns = {
            "endpoint_change_2017_2024": ["*endpoint*change*2017*2024*.tif*"],
            "endpoint_hotspots_2017_2024": ["*endpoint*hotspot*2017*2024*.tif*"],
            "persistence_count": ["*persistence*count*.tif*"],
            "variance_annual_change": ["*variance*annual*change*.tif*"],
            "slope_annual_change": ["*slope*annual*change*.tif*"],
            "first_hotspot_year": ["*first*hotspot*year*.tif*"],
            "max_change_year": ["*max*change*year*.tif*"],
            "cumulative_change": ["*cumulative*change*.tif*"],
            "mean_annual_change": ["*mean*annual*change*.tif*"],
            "max_annual_change": ["*max*annual*change*.tif*"],
        }

        core_raster_paths = {
            label: find_one(label, patterns, tif_files)
            for label, patterns in core_patterns.items()
        }

        year_pairs = [(year, year + 1) for year in range(2017, 2024)]
        annual_change_paths = {}
        annual_hotspot_paths = {}

        for start_year, end_year in year_pairs:
            key = f"{start_year}_{end_year}"
            annual_change_paths[key] = find_one(
                f"annual_change_{key}",
                [
                    f"*annual*change*{start_year}*{end_year}*.tif*",
                    f"*change*{start_year}*{end_year}*.tif*",
                ],
                tif_files,
            )
            annual_hotspot_paths[key] = find_one(
                f"annual_hotspot_{key}",
                [
                    f"*annual*hotspot*{start_year}*{end_year}*.tif*",
                    f"*hotspot*{start_year}*{end_year}*.tif*",
                ],
                tif_files,
            )

        print("\\nCore raster discovery:")
        for label, path in core_raster_paths.items():
            print(f"- {label}: {path.name if path else 'MISSING'}")

        print("\\nAnnual change raster discovery:")
        for key, path in annual_change_paths.items():
            print(f"- {key}: {path.name if path else 'MISSING'}")

        print("\\nAnnual hotspot raster discovery:")
        for key, path in annual_hotspot_paths.items():
            print(f"- {key}: {path.name if path else 'MISSING'}")
        """
    ),
    md("## 4. Raster Loading"),
    code(
        """
        def raster_meta(path):
            if path is None:
                return None
            with rasterio.open(path) as src:
                return {
                    "path": path,
                    "name": path.name,
                    "crs": src.crs,
                    "transform": src.transform,
                    "width": src.width,
                    "height": src.height,
                    "shape": (src.height, src.width),
                    "nodata": src.nodata,
                    "dtype": src.dtypes[0],
                    "bounds": src.bounds,
                    "count": src.count,
                }

        raster_stack_paths = {
            "endpoint_change": core_raster_paths["endpoint_change_2017_2024"],
            "endpoint_hotspot": core_raster_paths["endpoint_hotspots_2017_2024"],
            "persistence_count": core_raster_paths["persistence_count"],
            "variance_annual_change": core_raster_paths["variance_annual_change"],
            "slope_annual_change": core_raster_paths["slope_annual_change"],
            "first_hotspot_year": core_raster_paths["first_hotspot_year"],
            "max_change_year": core_raster_paths["max_change_year"],
            "cumulative_change": core_raster_paths["cumulative_change"],
            "mean_annual_change": core_raster_paths["mean_annual_change"],
            "max_annual_change": core_raster_paths["max_annual_change"],
        }

        for key, path in annual_change_paths.items():
            raster_stack_paths[f"annual_change_{key}"] = path
        for key, path in annual_hotspot_paths.items():
            raster_stack_paths[f"annual_hotspot_{key}"] = path

        raster_stack_meta = {}
        for label, path in raster_stack_paths.items():
            try:
                raster_stack_meta[label] = raster_meta(path)
                if raster_stack_meta[label] is not None:
                    print(f"Loaded metadata: {label} -> {path.name}")
            except Exception as exc:
                raster_stack_meta[label] = None
                warn(f"Could not read metadata for {label}: {exc}")

        loaded_raster_count = sum(meta is not None for meta in raster_stack_meta.values())
        print(f"Raster metadata loaded: {loaded_raster_count} / {len(raster_stack_meta)}")
        """
    ),
    md("## 5. Alignment Verification"),
    code(
        """
        available_meta = {label: meta for label, meta in raster_stack_meta.items() if meta is not None}

        if not available_meta:
            alignment_passed = False
            reference_label = None
            reference_meta = None
            warn("No raster metadata available. Cannot verify alignment.")
        else:
            reference_label = "endpoint_change" if "endpoint_change" in available_meta else next(iter(available_meta))
            reference_meta = available_meta[reference_label]
            print(f"Reference raster: {reference_label} ({reference_meta['name']})")

            alignment_rows = []
            for label, meta in available_meta.items():
                checks = {
                    "crs": reference_meta["crs"] == meta["crs"],
                    "transform": reference_meta["transform"] == meta["transform"],
                    "width": reference_meta["width"] == meta["width"],
                    "height": reference_meta["height"] == meta["height"],
                    "shape": reference_meta["shape"] == meta["shape"],
                }
                checks["all_match"] = all(checks.values())
                alignment_rows.append({"label": label, "file": meta["name"], **checks})

            alignment_df = pd.DataFrame(alignment_rows)
            display(alignment_df)
            alignment_df.to_csv(TABLE_DIR / "phase2_alignment_report.csv", index=False)
            alignment_passed = bool(alignment_df["all_match"].all())
            print(f"Alignment passed: {alignment_passed}")
        """
    ),
    md("## 6. Threshold Calculation"),
    code(
        """
        def read_sampled_values(path, stride=THRESHOLD_SAMPLE_STRIDE):
            if path is None:
                return np.array([], dtype="float32")
            with rasterio.open(path) as src:
                out_height = max(1, src.height // stride)
                out_width = max(1, src.width // stride)
                data = src.read(
                    1,
                    out_shape=(out_height, out_width),
                    masked=True,
                    resampling=Resampling.nearest,
                )
            values = data.compressed() if np.ma.isMaskedArray(data) else data[np.isfinite(data)]
            return values.astype("float32", copy=False)

        endpoint_values = read_sampled_values(raster_stack_paths["endpoint_change"])
        variance_values = read_sampled_values(raster_stack_paths["variance_annual_change"])
        slope_values = read_sampled_values(raster_stack_paths["slope_annual_change"])

        thresholds = {
            "endpoint_p95": float(np.nanpercentile(endpoint_values, 95)) if endpoint_values.size else np.nan,
            "endpoint_p25": float(np.nanpercentile(endpoint_values, 25)) if endpoint_values.size else np.nan,
            "variance_p95": float(np.nanpercentile(variance_values, 95)) if variance_values.size else np.nan,
            "variance_p25": float(np.nanpercentile(variance_values, 25)) if variance_values.size else np.nan,
            "slope_p95": float(np.nanpercentile(slope_values, 95)) if slope_values.size else np.nan,
            "slope_p05": float(np.nanpercentile(slope_values, 5)) if slope_values.size else np.nan,
            "abs_slope_p25": float(np.nanpercentile(np.abs(slope_values), 25)) if slope_values.size else np.nan,
            "threshold_sample_stride": THRESHOLD_SAMPLE_STRIDE,
        }

        threshold_df = pd.DataFrame([thresholds])
        display(threshold_df)
        threshold_df.to_csv(TABLE_DIR / "phase2_thresholds.csv", index=False)

        print("Thresholds are estimated from a downsampled raster read to avoid loading all pixels into RAM.")
        """
    ),
    md("## 7. Category Mask Creation"),
    code(
        """
        category_order = [
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

        def iter_windows(width, height, window_size=WINDOW_SIZE):
            for row_off in range(0, height, window_size):
                win_height = min(window_size, height - row_off)
                for col_off in range(0, width, window_size):
                    win_width = min(window_size, width - col_off)
                    yield Window(col_off, row_off, win_width, win_height)

        def read_window(path, window):
            with rasterio.open(path) as src:
                return src.read(1, window=window, masked=True)

        def valid_mask_for(*arrays):
            mask = np.ones(arrays[0].shape, dtype=bool)
            for arr in arrays:
                if np.ma.isMaskedArray(arr):
                    mask &= ~np.ma.getmaskarray(arr)
                else:
                    mask &= np.isfinite(arr)
            return mask

        def build_category_masks(endpoint, hotspot, persistence, variance, slope):
            valid = valid_mask_for(endpoint, hotspot, persistence, variance, slope)
            endpoint_data = np.asarray(endpoint)
            hotspot_data = np.asarray(hotspot)
            persistence_data = np.asarray(persistence)
            variance_data = np.asarray(variance)
            slope_data = np.asarray(slope)

            endpoint_p95 = thresholds["endpoint_p95"]
            endpoint_p25 = thresholds["endpoint_p25"]
            variance_p95 = thresholds["variance_p95"]
            variance_p25 = thresholds["variance_p25"]
            slope_p95 = thresholds["slope_p95"]
            slope_p05 = thresholds["slope_p05"]
            abs_slope_p25 = thresholds["abs_slope_p25"]

            masks = {
                "endpoint_hotspot": valid & (hotspot_data == 1),
                "persistent_ge2": valid & (persistence_data >= 2),
                "persistent_ge3": valid & (persistence_data >= 3),
                "high_variance": valid & (variance_data >= variance_p95),
                "positive_slope": valid & (slope_data >= slope_p95),
                "negative_slope": valid & (slope_data <= slope_p05),
                "sudden_candidate": valid & (endpoint_data >= endpoint_p95) & (persistence_data <= 1),
                "temporary_or_recovery_candidate": valid & (endpoint_data < endpoint_p95) & (variance_data >= variance_p95),
                "stable_control": (
                    valid
                    & (endpoint_data <= endpoint_p25)
                    & (persistence_data == 0)
                    & (variance_data <= variance_p25)
                    & (np.abs(slope_data) <= abs_slope_p25)
                ),
            }
            return masks

        print("Category mask functions are ready. Masks are created per window during sampling, not stored for the full raster.")
        """
    ),
    md("## 8. Pixel Sampling"),
    code(
        """
        def update_reservoir(reservoir, category, rows, cols):
            if rows.size == 0:
                return
            priorities = rng.random(rows.size)
            current = reservoir.get(category)

            if current is None:
                combined_rows = rows.astype("int64", copy=False)
                combined_cols = cols.astype("int64", copy=False)
                combined_priorities = priorities
            else:
                combined_rows = np.concatenate([current["row"], rows.astype("int64", copy=False)])
                combined_cols = np.concatenate([current["col"], cols.astype("int64", copy=False)])
                combined_priorities = np.concatenate([current["priority"], priorities])

            if combined_rows.size > MAX_SAMPLES_PER_CATEGORY:
                keep = np.argpartition(combined_priorities, MAX_SAMPLES_PER_CATEGORY - 1)[:MAX_SAMPLES_PER_CATEGORY]
                combined_rows = combined_rows[keep]
                combined_cols = combined_cols[keep]
                combined_priorities = combined_priorities[keep]

            reservoir[category] = {
                "row": combined_rows,
                "col": combined_cols,
                "priority": combined_priorities,
            }

        required_for_sampling = [
            "endpoint_change",
            "endpoint_hotspot",
            "persistence_count",
            "variance_annual_change",
            "slope_annual_change",
        ]
        missing_sampling_inputs = [label for label in required_for_sampling if raster_stack_paths.get(label) is None]

        reservoir = {category: None for category in category_order}
        category_candidate_counts = {category: 0 for category in category_order}

        if missing_sampling_inputs:
            warn(f"Sampling skipped because required rasters are missing: {missing_sampling_inputs}")
        elif reference_meta is None:
            warn("Sampling skipped because there is no reference raster metadata.")
        else:
            windows = list(iter_windows(reference_meta["width"], reference_meta["height"]))
            print(f"Scanning {len(windows)} windows of up to {WINDOW_SIZE}x{WINDOW_SIZE} pixels.")

            for idx, window in enumerate(windows, start=1):
                endpoint = read_window(raster_stack_paths["endpoint_change"], window)
                hotspot = read_window(raster_stack_paths["endpoint_hotspot"], window)
                persistence = read_window(raster_stack_paths["persistence_count"], window)
                variance = read_window(raster_stack_paths["variance_annual_change"], window)
                slope = read_window(raster_stack_paths["slope_annual_change"], window)

                masks = build_category_masks(endpoint, hotspot, persistence, variance, slope)
                row_base = int(window.row_off)
                col_base = int(window.col_off)

                for category in category_order:
                    local_rows, local_cols = np.where(masks[category])
                    category_candidate_counts[category] += int(local_rows.size)
                    if local_rows.size:
                        update_reservoir(
                            reservoir,
                            category,
                            local_rows + row_base,
                            local_cols + col_base,
                        )

                if idx % 25 == 0 or idx == len(windows):
                    print(f"Processed {idx}/{len(windows)} windows.")

                del endpoint, hotspot, persistence, variance, slope, masks

        sampled_rows = []
        used_pixel_keys = set()

        for category in category_order:
            current = reservoir.get(category)
            if current is None:
                continue
            order = np.argsort(current["priority"])
            added = 0
            for pos in order:
                row = int(current["row"][pos])
                col = int(current["col"][pos])
                pixel_key = f"{row}_{col}"
                if pixel_key in used_pixel_keys:
                    continue
                used_pixel_keys.add(pixel_key)
                sampled_rows.append({
                    "row": row,
                    "col": col,
                    "pixel_key": pixel_key,
                    "category": category,
                    "sampling_priority": float(current["priority"][pos]),
                })
                added += 1
                if added >= MAX_SAMPLES_PER_CATEGORY:
                    break

        sample_locations_df = pd.DataFrame(sampled_rows)
        if sample_locations_df.empty:
            warn("No sampled pixels were selected.")
        else:
            sample_locations_df = sample_locations_df.sort_values(["category", "sampling_priority"]).reset_index(drop=True)
            sample_locations_df.insert(0, "sample_id", np.arange(1, len(sample_locations_df) + 1))

        category_counts_df = pd.DataFrame({
            "category": category_order,
            "candidate_pixel_count": [category_candidate_counts[c] for c in category_order],
            "sampled_pixel_count": [
                int((sample_locations_df["category"] == c).sum()) if not sample_locations_df.empty else 0
                for c in category_order
            ],
            "max_samples_per_category": MAX_SAMPLES_PER_CATEGORY,
        })

        display(category_counts_df)
        print(f"Total sampled unique pixels: {len(sample_locations_df)}")
        """
    ),
    md("## 9. Table Construction"),
    code(
        """
        def rows_cols_to_lon_lat(rows, cols, meta):
            xs, ys = xy(meta["transform"], rows, cols, offset="center")
            xs = np.asarray(xs)
            ys = np.asarray(ys)
            if meta["crs"] is not None and str(meta["crs"]).upper() not in ("EPSG:4326", "OGC:CRS84"):
                lon, lat = transform_coords(meta["crs"], "EPSG:4326", xs.tolist(), ys.tolist())
                return np.asarray(lon), np.asarray(lat), xs, ys
            return xs, ys, xs, ys

        def sample_raster_at_xy(path, xs, ys):
            if path is None:
                return np.full(xs.shape, np.nan, dtype="float32")
            coords = list(zip(xs, ys))
            values = []
            with rasterio.open(path) as src:
                for sample in src.sample(coords, masked=True):
                    value = sample[0]
                    if np.ma.is_masked(value):
                        values.append(np.nan)
                    else:
                        values.append(float(value))
            return np.asarray(values, dtype="float32")

        if sample_locations_df.empty:
            sampled_pixels_df = pd.DataFrame()
        else:
            rows = sample_locations_df["row"].to_numpy()
            cols = sample_locations_df["col"].to_numpy()
            lon, lat, xs, ys = rows_cols_to_lon_lat(rows, cols, reference_meta)

            sampled_pixels_df = sample_locations_df.copy()
            sampled_pixels_df.insert(3, "lon", lon)
            sampled_pixels_df.insert(4, "lat", lat)

            value_columns = [
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
            ]
            value_columns += [f"annual_change_{start}_{end}" for start, end in year_pairs]
            value_columns += [f"annual_hotspot_{start}_{end}" for start, end in year_pairs]

            for column in value_columns:
                print(f"Sampling raster values: {column}")
                sampled_pixels_df[column] = sample_raster_at_xy(raster_stack_paths.get(column), xs, ys)

            output_columns = [
                "sample_id",
                "row",
                "col",
                "lon",
                "lat",
                "pixel_key",
                "category",
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
            ]
            sampled_pixels_df = sampled_pixels_df[output_columns]

        display(sampled_pixels_df.head())
        print(f"Sampled table rows: {len(sampled_pixels_df)}")
        """
    ),
    md("## 10. Save Outputs"),
    code(
        """
        sampled_pixels_path = OUTPUT_DIR / "basscoast_phase2_sampled_pixels.csv"
        sampling_summary_path = OUTPUT_DIR / "basscoast_phase2_sampling_summary.csv"
        category_counts_path = OUTPUT_DIR / "basscoast_phase2_category_counts.csv"

        sampled_pixels_df.to_csv(sampled_pixels_path, index=False)
        category_counts_df.to_csv(category_counts_path, index=False)

        summary_rows = [
            {"item": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
            {"item": "project_folder", "value": str(PROJECT_FOLDER)},
            {"item": "output_folder", "value": str(OUTPUT_DIR)},
            {"item": "random_seed", "value": RANDOM_SEED},
            {"item": "max_samples_per_category", "value": MAX_SAMPLES_PER_CATEGORY},
            {"item": "window_size", "value": WINDOW_SIZE},
            {"item": "threshold_sample_stride", "value": THRESHOLD_SAMPLE_STRIDE},
            {"item": "loaded_raster_count", "value": loaded_raster_count},
            {"item": "expected_raster_count", "value": len(raster_stack_paths)},
            {"item": "alignment_passed", "value": alignment_passed},
            {"item": "total_sampled_rows", "value": len(sampled_pixels_df)},
        ]
        for key, value in thresholds.items():
            summary_rows.append({"item": key, "value": value})
        if warning_messages:
            for idx, message in enumerate(warning_messages, start=1):
                summary_rows.append({"item": f"warning_{idx}", "value": message})

        sampling_summary_df = pd.DataFrame(summary_rows)
        sampling_summary_df.to_csv(sampling_summary_path, index=False)

        print(f"Saved sampled pixels: {sampled_pixels_path}")
        print(f"Saved sampling summary: {sampling_summary_path}")
        print(f"Saved category counts: {category_counts_path}")
        """
    ),
    md("## 11. Diagnostic Plots"),
    code(
        """
        saved_plot_paths = []

        def save_current_plot(filename):
            path = FIGURE_DIR / filename
            plt.savefig(path, dpi=180, bbox_inches="tight")
            saved_plot_paths.append(path)
            plt.show()
            print(f"Saved plot: {path}")

        if sampled_pixels_df.empty:
            warn("Diagnostic plots skipped because sampled_pixels_df is empty.")
        else:
            plt.figure(figsize=(10, 4))
            plot_counts = sampled_pixels_df["category"].value_counts().reindex(category_order, fill_value=0)
            plot_counts.plot(kind="bar", color="#3b6ea8")
            plt.title("Sample Count by Category")
            plt.xlabel("Category")
            plt.ylabel("Sample count")
            plt.xticks(rotation=35, ha="right")
            plt.tight_layout()
            save_current_plot("sample_count_by_category.png")

            boxplot_specs = [
                ("endpoint_change", "Endpoint Change by Category", "boxplot_endpoint_change_by_category.png"),
                ("persistence_count", "Persistence Count by Category", "boxplot_persistence_count_by_category.png"),
                ("variance_annual_change", "Variance Annual Change by Category", "boxplot_variance_annual_change_by_category.png"),
                ("slope_annual_change", "Slope Annual Change by Category", "boxplot_slope_annual_change_by_category.png"),
            ]

            for column, title, filename in boxplot_specs:
                plt.figure(figsize=(11, 5))
                sampled_pixels_df.boxplot(column=column, by="category", rot=35)
                plt.title(title)
                plt.suptitle("")
                plt.xlabel("Category")
                plt.ylabel(column)
                plt.tight_layout()
                save_current_plot(filename)

            color_codes = pd.Categorical(sampled_pixels_df["category"], categories=category_order).codes
            cmap = plt.get_cmap("tab10")

            scatter_specs = [
                ("endpoint_change", "persistence_count", "Endpoint Change vs Persistence Count", "scatter_endpoint_change_vs_persistence_count.png"),
                ("endpoint_change", "variance_annual_change", "Endpoint Change vs Variance Annual Change", "scatter_endpoint_change_vs_variance_annual_change.png"),
                ("slope_annual_change", "variance_annual_change", "Slope Annual Change vs Variance Annual Change", "scatter_slope_annual_change_vs_variance_annual_change.png"),
            ]

            for x_col, y_col, title, filename in scatter_specs:
                plt.figure(figsize=(8, 6))
                scatter = plt.scatter(
                    sampled_pixels_df[x_col],
                    sampled_pixels_df[y_col],
                    c=color_codes,
                    cmap=cmap,
                    s=8,
                    alpha=0.45,
                )
                plt.title(title)
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                handles = [
                    plt.Line2D([0], [0], marker="o", color="w", label=cat, markerfacecolor=cmap(i % 10), markersize=7)
                    for i, cat in enumerate(category_order)
                    if (sampled_pixels_df["category"] == cat).any()
                ]
                plt.legend(handles=handles, title="Category", bbox_to_anchor=(1.04, 1), loc="upper left")
                plt.tight_layout()
                save_current_plot(filename)

        zip_path = shutil.make_archive(str(OUTPUT_DIR), "zip", root_dir=OUTPUT_DIR)
        print(f"Created ZIP package: {zip_path}")
        """
    ),
    md("## 12. Summary and Next Steps"),
    code(
        """
        print("PHASE 2 PIXEL SAMPLING SUMMARY")
        print("=" * 38)
        print(f"Rasters loaded: {loaded_raster_count} / {len(raster_stack_paths)}")
        print(f"Alignment passed: {alignment_passed}")
        print("\\nSample count per category:")
        if not category_counts_df.empty:
            for _, row in category_counts_df.iterrows():
                print(f"- {row['category']}: {int(row['sampled_pixel_count'])} sampled from {int(row['candidate_pixel_count'])} candidates")
        print(f"\\nTotal sampled rows: {len(sampled_pixels_df)}")
        print(f"Output folder: {OUTPUT_DIR}")

        if warning_messages:
            print("\\nWarnings:")
            for message in warning_messages:
                print(f"- {message}")
        else:
            print("\\nWarnings: none")

        print("\\nNext steps:")
        print("- Review category counts and diagnostic plots.")
        print("- Check whether sampled categories are spatially and statistically sensible.")
        print("- Later phases can compare these candidate samples against DEA Land Cover, HIF/EII, NearMap, or field evidence.")
        """
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

Path(NOTEBOOK_NAME).write_text(json.dumps(notebook, indent=2), encoding="utf-8")
print(Path(NOTEBOOK_NAME).resolve())
