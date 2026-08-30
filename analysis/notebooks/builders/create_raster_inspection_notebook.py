import json
import textwrap
from pathlib import Path


NOTEBOOK_NAME = "BassCoast_Phase1_Raster_Inspection.ipynb"


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
        # Bass Coast Phase 1 Raster Inspection

        This notebook performs data health checks for the Phase 1 Google Satellite Embedding V1 change-detection exports for Bass Coast Landcare Network.

        Scope:
        - Mount Google Drive.
        - Locate and list exported GeoTIFF and CSV files.
        - Load core raster outputs and annual rasters.
        - Check raster alignment.
        - Print basic raster statistics.
        - Display CSV summary tables.
        - Create initial maps and distribution charts.

        This notebook intentionally does not classify change trajectories or integrate DEA, HIF/EII, NearMap, or other interpretation layers.
        """
    ),
    md("## 1. Install and Import Dependencies"),
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
        import os
        import shutil
        from pathlib import Path
        import warnings
        from datetime import datetime

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import rasterio

        warnings.filterwarnings("ignore", category=RuntimeWarning)
        pd.set_option("display.max_columns", 100)
        pd.set_option("display.max_rows", 100)

        print("Dependencies ready.")
        """
    ),
    md("## 2. Mount Google Drive and Set Project Folder"),
    code(
        """
        from google.colab import drive
        drive.mount("/content/drive")

        PROJECT_FOLDER = Path("/content/drive/MyDrive/GEE_BassCoast_SatelliteEmbedding")

        if not PROJECT_FOLDER.exists():
            print(f"WARNING: Project folder not found: {PROJECT_FOLDER}")
            print("Update PROJECT_FOLDER to the folder containing the exported GeoTIFF and CSV files.")
            OUTPUT_DIR = Path.cwd() / "BassCoast_Phase1_Raster_Inspection_outputs"
        else:
            print(f"Project folder found: {PROJECT_FOLDER}")
            OUTPUT_DIR = PROJECT_FOLDER / "BassCoast_Phase1_Raster_Inspection_outputs"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        FIGURE_DIR = OUTPUT_DIR / "figures"
        TABLE_DIR = OUTPUT_DIR / "tables"
        FIGURE_DIR.mkdir(parents=True, exist_ok=True)
        TABLE_DIR.mkdir(parents=True, exist_ok=True)

        print(f"Output folder: {OUTPUT_DIR}")
        """
    ),
    md("## 3. List Files in the Project Folder"),
    code(
        """
        def list_project_files(folder):
            if not folder.exists():
                inventory_df = pd.DataFrame(columns=["name", "suffix", "size_mb", "modified_time", "path"])
                inventory_df.to_csv(TABLE_DIR / "project_file_inventory.csv", index=False)
                return [], inventory_df
            files = sorted([p for p in folder.iterdir() if p.is_file()], key=lambda p: p.name.lower())
            print(f"Found {len(files)} files in {folder}")
            rows = []
            for p in files:
                size_mb = p.stat().st_size / (1024 ** 2)
                print(f"- {p.name} ({size_mb:.2f} MB)")
                rows.append({
                    "name": p.name,
                    "suffix": p.suffix,
                    "size_mb": size_mb,
                    "modified_time": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                    "path": str(p),
                })
            inventory_df = pd.DataFrame(rows)
            inventory_df.to_csv(TABLE_DIR / "project_file_inventory.csv", index=False)
            return files, inventory_df

        project_files, project_file_inventory_df = list_project_files(PROJECT_FOLDER)
        """
    ),
    md("## 4. File Discovery Helpers"),
    code(
        """
        def discover_files(folder, suffixes=(".tif", ".tiff", ".csv")):
            if not folder.exists():
                return []
            suffixes = tuple(s.lower() for s in suffixes)
            return sorted(
                [p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith(suffixes)],
                key=lambda p: p.name.lower(),
            )

        def matches_any(path, patterns):
            name = path.name.lower()
            return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in patterns)

        def find_one(label, patterns, files=None, warn=True):
            files = files or discover_files(PROJECT_FOLDER)
            matches = [p for p in files if matches_any(p, patterns)]
            if not matches:
                if warn:
                    print(f"WARNING: Missing expected file for '{label}'. Patterns: {patterns}")
                return None
            if len(matches) > 1:
                print(f"WARNING: Multiple matches for '{label}'. Using most recently modified file:")
                for p in sorted(matches, key=lambda x: x.stat().st_mtime, reverse=True):
                    print(f"  - {p.name}")
                return sorted(matches, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            return matches[0]

        all_data_files = discover_files(PROJECT_FOLDER)
        tif_files = discover_files(PROJECT_FOLDER, suffixes=(".tif", ".tiff"))
        csv_files = discover_files(PROJECT_FOLDER, suffixes=(".csv",))

        print(f"GeoTIFF files discovered: {len(tif_files)}")
        print(f"CSV files discovered: {len(csv_files)}")
        """
    ),
    md("## 5. Locate Core Phase 1 Rasters"),
    code(
        """
        core_patterns = {
            "endpoint_change_2017_2024": ["*endpoint*change*2017*2024*.tif*"],
            "endpoint_hotspots_2017_2024": ["*endpoint*hotspot*2017*2024*.tif*"],
            "cumulative_change": ["*cumulative*change*.tif*"],
            "mean_annual_change": ["*mean*annual*change*.tif*"],
            "max_annual_change": ["*max*annual*change*.tif*"],
            "persistence_count": ["*persistence*count*.tif*"],
            "persistent_hotspots_ge2": ["*persistent*hotspot*ge2*.tif*", "*persistent*hotspot*2*.tif*"],
            "persistent_hotspots_ge3": ["*persistent*hotspot*ge3*.tif*", "*persistent*hotspot*3*.tif*"],
            "variance_annual_change": ["*variance*annual*change*.tif*"],
            "slope_annual_change": ["*slope*annual*change*.tif*"],
            "first_hotspot_year": ["*first*hotspot*year*.tif*"],
            "max_change_year": ["*max*change*year*.tif*"],
        }

        core_raster_paths = {
            label: find_one(label, patterns, tif_files)
            for label, patterns in core_patterns.items()
        }

        print("Core raster discovery report:")
        for label, path in core_raster_paths.items():
            status = path.name if path else "MISSING"
            print(f"- {label}: {status}")
        """
    ),
    md("## 6. Locate Annual Change and Annual Hotspot Rasters"),
    code(
        """
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

        print("Annual change rasters:")
        for key, path in annual_change_paths.items():
            print(f"- {key}: {path.name if path else 'MISSING'}")

        print("\\nAnnual hotspot rasters:")
        for key, path in annual_hotspot_paths.items():
            print(f"- {key}: {path.name if path else 'MISSING'}")
        """
    ),
    md("## 7. Memory-Safe Raster Metadata Helpers"),
    code(
        """
        def read_raster_meta(path):
            if path is None:
                return None
            with rasterio.open(path) as src:
                meta = {
                    "path": path,
                    "name": path.name,
                    "crs": src.crs,
                    "transform": src.transform,
                    "width": src.width,
                    "height": src.height,
                    "shape": (src.height, src.width),
                    "nodata": src.nodata,
                    "bounds": src.bounds,
                    "dtype": src.dtypes[0],
                    "count": src.count,
                }
            return meta

        def load_raster_meta_group(path_dict):
            metas = {}
            for label, path in path_dict.items():
                if path is None:
                    metas[label] = None
                    continue
                try:
                    metas[label] = read_raster_meta(path)
                    print(f"Read metadata for {label}: {path.name}")
                except Exception as exc:
                    metas[label] = None
                    print(f"WARNING: Failed to read metadata for {label} ({path.name}): {exc}")
            return metas

        core_raster_meta = load_raster_meta_group(core_raster_paths)
        annual_change_meta = load_raster_meta_group(annual_change_paths)
        annual_hotspot_meta = load_raster_meta_group(annual_hotspot_paths)

        # Backward-compatible aliases used by later summary cells. These hold metadata only, not arrays.
        core_rasters = core_raster_meta
        annual_change_rasters = annual_change_meta
        annual_hotspot_rasters = annual_hotspot_meta
        """
    ),
    md("## 8. Raster Alignment Check"),
    code(
        """
        def flatten_meta_groups(*groups):
            out = {}
            for group in groups:
                for label, meta in group.items():
                    if meta is not None:
                        out[label] = meta
            return out

        all_raster_meta = flatten_meta_groups(core_raster_meta, annual_change_meta, annual_hotspot_meta)

        def compare_alignment(reference, candidate):
            checks = {
                "crs": reference["crs"] == candidate["crs"],
                "transform": reference["transform"] == candidate["transform"],
                "width": reference["width"] == candidate["width"],
                "height": reference["height"] == candidate["height"],
                "shape": reference["shape"] == candidate["shape"],
            }
            checks["all_match"] = all(checks.values())
            return checks

        alignment_rows = []

        if not all_raster_meta:
            print("WARNING: No rasters loaded. Alignment cannot be checked.")
            alignment_passed = False
        else:
            reference_label = "endpoint_change_2017_2024" if "endpoint_change_2017_2024" in all_raster_meta else next(iter(all_raster_meta))
            reference = all_raster_meta[reference_label]
            print(f"Reference raster: {reference_label} ({reference['name']})")

            for label, meta in all_raster_meta.items():
                checks = compare_alignment(reference, meta)
                row = {"label": label, "file": meta["name"], **checks}
                alignment_rows.append(row)

            alignment_df = pd.DataFrame(alignment_rows)
            display(alignment_df)
            alignment_df.to_csv(TABLE_DIR / "raster_alignment_report.csv", index=False)
            alignment_passed = bool(alignment_df["all_match"].all())
            print(f"Alignment passed: {alignment_passed}")
            print(f"Saved alignment report: {TABLE_DIR / 'raster_alignment_report.csv'}")
        """
    ),
    md("## 9. Basic Raster Statistics"),
    code(
        """
        WINDOW_SIZE = 1024
        MEDIAN_SAMPLE_STRIDE = 8

        def iter_windows(width, height, window_size=WINDOW_SIZE):
            for row_off in range(0, height, window_size):
                win_height = min(window_size, height - row_off)
                for col_off in range(0, width, window_size):
                    win_width = min(window_size, width - col_off)
                    yield rasterio.windows.Window(col_off, row_off, win_width, win_height)

        def read_sampled_array(path, stride=MEDIAN_SAMPLE_STRIDE):
            with rasterio.open(path) as src:
                out_height = max(1, src.height // stride)
                out_width = max(1, src.width // stride)
                data = src.read(
                    1,
                    out_shape=(out_height, out_width),
                    masked=True,
                    resampling=rasterio.enums.Resampling.nearest,
                )
            return data

        def raster_stats_windowed(label, meta):
            if meta is None:
                return {
                    "label": label,
                    "file": None,
                    "min": np.nan,
                    "max": np.nan,
                    "mean": np.nan,
                    "median": np.nan,
                    "std": np.nan,
                    "valid_pixel_count": 0,
                    "nodata_pixel_count": np.nan,
                    "dtype": None,
                    "nodata": None,
                }

            valid_count = 0
            total_count = 0
            value_sum = 0.0
            value_sumsq = 0.0
            min_value = np.inf
            max_value = -np.inf

            with rasterio.open(meta["path"]) as src:
                for window in iter_windows(src.width, src.height):
                    data = src.read(1, window=window, masked=True)
                    total_count += int(data.size)
                    values = data.compressed() if np.ma.isMaskedArray(data) else data[np.isfinite(data)]
                    if values.size == 0:
                        continue
                    values = values.astype("float64", copy=False)
                    valid_count += int(values.size)
                    value_sum += float(values.sum())
                    value_sumsq += float(np.square(values).sum())
                    min_value = min(min_value, float(values.min()))
                    max_value = max(max_value, float(values.max()))
                    del data, values

            nodata_count = total_count - valid_count

            if valid_count == 0:
                mean_value = np.nan
                std_value = np.nan
                min_value = np.nan
                max_value = np.nan
            else:
                mean_value = value_sum / valid_count
                variance = max((value_sumsq / valid_count) - (mean_value ** 2), 0.0)
                std_value = variance ** 0.5

            sample = read_sampled_array(meta["path"], stride=MEDIAN_SAMPLE_STRIDE)
            sample_values = sample.compressed() if np.ma.isMaskedArray(sample) else sample[np.isfinite(sample)]
            median_value = float(np.nanmedian(sample_values)) if sample_values.size else np.nan
            del sample, sample_values

            return {
                "label": label,
                "file": meta["name"],
                "min": min_value,
                "max": max_value,
                "mean": mean_value,
                "median": median_value,
                "std": std_value,
                "valid_pixel_count": valid_count,
                "nodata_pixel_count": nodata_count,
                "dtype": meta["dtype"],
                "nodata": meta["nodata"],
                "median_sample_stride": MEDIAN_SAMPLE_STRIDE,
                "note": "min/max/mean/std/counts are exact windowed calculations; median is sampled to avoid RAM exhaustion",
            }

        stats_rows = []
        for label, meta in all_raster_meta.items():
            try:
                stats_rows.append(raster_stats_windowed(label, meta))
                print(f"Computed windowed stats for {label}")
            except Exception as exc:
                print(f"WARNING: Failed to compute stats for {label}: {exc}")

        raster_stats_df = pd.DataFrame(stats_rows)
        display(raster_stats_df)
        raster_stats_df.to_csv(TABLE_DIR / "raster_basic_statistics.csv", index=False)
        print(f"Stats use {WINDOW_SIZE}x{WINDOW_SIZE} windows. Median sample stride: every {MEDIAN_SAMPLE_STRIDE}th pixel in each dimension.")
        print(f"Saved raster statistics: {TABLE_DIR / 'raster_basic_statistics.csv'}")
        """
    ),
    md("## 10. Load and Display CSV Files"),
    code(
        """
        def load_csv_matches(label, patterns):
            matches = [p for p in csv_files if matches_any(p, patterns)]
            if not matches:
                print(f"WARNING: Missing CSV for '{label}'. Patterns: {patterns}")
                return []
            if len(matches) > 1:
                print(f"WARNING: Multiple CSV matches for '{label}'. Displaying all matches:")
            outputs = []
            for path in sorted(matches, key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    df = pd.read_csv(path)
                    outputs.append((path, df))
                    print(f"Loaded {label}: {path.name} ({len(df)} rows, {len(df.columns)} columns)")
                    display(df)
                    output_name = f"{label}__{path.stem}.csv"
                    df.to_csv(TABLE_DIR / output_name, index=False)
                    print(f"Saved table copy: {TABLE_DIR / output_name}")
                except Exception as exc:
                    print(f"WARNING: Failed to load CSV {path.name}: {exc}")
            return outputs

        annual_stats_tables = load_csv_matches("annual_change_stats", ["*annual*change*stats*.csv"])
        tile_count_tables = load_csv_matches("tile_counts", ["*tile*count*.csv", "*tile*counts*.csv"])
        """
    ),
    md("## 11. Initial Simple Maps"),
    code(
        """
        PLOT_MAX_DIM = 1200
        saved_figure_paths = []

        def read_for_plot(path, max_dim=PLOT_MAX_DIM):
            with rasterio.open(path) as src:
                scale = max(src.width / max_dim, src.height / max_dim, 1)
                out_width = max(1, int(src.width / scale))
                out_height = max(1, int(src.height / scale))
                data = src.read(
                    1,
                    out_shape=(out_height, out_width),
                    masked=True,
                    resampling=rasterio.enums.Resampling.nearest,
                )
            return data

        def safe_filename(text):
            keep = []
            for char in text.lower().replace(" ", "_"):
                keep.append(char if char.isalnum() or char in ("_", "-") else "_")
            return "".join(keep).strip("_")

        def plot_raster(label, meta, cmap="viridis"):
            if meta is None:
                print(f"WARNING: Cannot plot missing raster: {label}")
                return
            data = read_for_plot(meta["path"])
            plt.figure(figsize=(8, 6))
            im = plt.imshow(data, cmap=cmap)
            plt.title(label)
            plt.axis("off")
            plt.colorbar(im, shrink=0.8)
            output_path = FIGURE_DIR / f"map_{safe_filename(label)}.png"
            plt.savefig(output_path, dpi=180, bbox_inches="tight")
            saved_figure_paths.append(output_path)
            plt.show()
            print(f"Saved figure: {output_path}")
            del data

        map_specs = [
            ("endpoint_change_2017_2024", "magma"),
            ("persistence_count", "viridis"),
            ("variance_annual_change", "plasma"),
            ("slope_annual_change", "coolwarm"),
            ("first_hotspot_year", "tab10"),
            ("max_change_year", "tab10"),
        ]

        for label, cmap in map_specs:
            plot_raster(label, core_rasters.get(label), cmap=cmap)
        """
    ),
    md("## 12. Basic Distribution Charts"),
    code(
        """
        HIST_SAMPLE_STRIDE = 4

        def valid_values_sample(meta, stride=HIST_SAMPLE_STRIDE):
            if meta is None:
                return np.array([])
            data = read_sampled_array(meta["path"], stride=stride)
            if np.ma.isMaskedArray(data):
                values = data.compressed()
            else:
                values = data[np.isfinite(data)]
            return values

        def plot_hist(label, meta, bins=50):
            values = valid_values_sample(meta)
            if values.size == 0:
                print(f"WARNING: No valid values for histogram: {label}")
                return
            plt.figure(figsize=(8, 4))
            plt.hist(values, bins=bins, color="#3b6ea8", edgecolor="white")
            plt.title(label)
            plt.xlabel("Value")
            plt.ylabel("Pixel count")
            plt.grid(alpha=0.25)
            output_path = FIGURE_DIR / f"hist_{safe_filename(label)}.png"
            plt.savefig(output_path, dpi=180, bbox_inches="tight")
            saved_figure_paths.append(output_path)
            plt.show()
            print(f"Saved figure: {output_path}")
            del values

        plot_hist("Endpoint change values", core_rasters.get("endpoint_change_2017_2024"), bins=60)
        plot_hist("Persistence count", core_rasters.get("persistence_count"), bins=range(0, 10))
        plot_hist("Slope annual change", core_rasters.get("slope_annual_change"), bins=60)
        print(f"Histogram sample stride: every {HIST_SAMPLE_STRIDE}th pixel in each dimension.")
        """
    ),
    md("## 13. Annual Change Summary Charts"),
    code(
        """
        def choose_annual_stats_table(tables):
            if not tables:
                return None, None
            # Prefer the most recently modified matching CSV.
            return tables[0]

        annual_stats_path, annual_stats_df = choose_annual_stats_table(annual_stats_tables)

        def plot_annual_metric(df, metric, title):
            if df is None:
                print(f"WARNING: Cannot plot {metric}; annual stats CSV was not loaded.")
                return
            if metric not in df.columns:
                print(f"WARNING: Cannot plot {metric}; column not found in annual stats CSV.")
                return

            x_col = "label" if "label" in df.columns else "end_year" if "end_year" in df.columns else None
            if x_col is None:
                x = np.arange(len(df))
                x_label = "row"
            else:
                x = df[x_col].astype(str)
                x_label = x_col

            plt.figure(figsize=(9, 4))
            plt.plot(x, df[metric], marker="o", linewidth=2)
            plt.title(title)
            plt.xlabel(x_label)
            plt.ylabel(metric)
            plt.xticks(rotation=35, ha="right")
            plt.grid(alpha=0.3)
            plt.tight_layout()
            output_path = FIGURE_DIR / f"line_{safe_filename(title)}.png"
            plt.savefig(output_path, dpi=180, bbox_inches="tight")
            saved_figure_paths.append(output_path)
            plt.show()
            print(f"Saved figure: {output_path}")

        if annual_stats_path is not None:
            print(f"Using annual stats table for charts: {annual_stats_path.name}")

        plot_annual_metric(annual_stats_df, "mean", "Annual Mean Change")
        plot_annual_metric(annual_stats_df, "p95", "Annual P95 Change")
        """
    ),
    md("## 14. Final Health Check Summary"),
    code(
        """
        expected_core = set(core_patterns.keys())
        loaded_core = {label for label, meta in core_rasters.items() if meta is not None}
        missing_core = sorted(expected_core - loaded_core)

        loaded_annual_change = [label for label, meta in annual_change_rasters.items() if meta is not None]
        missing_annual_change = [label for label, meta in annual_change_rasters.items() if meta is None]

        loaded_annual_hotspot = [label for label, meta in annual_hotspot_rasters.items() if meta is not None]
        missing_annual_hotspot = [label for label, meta in annual_hotspot_rasters.items() if meta is None]

        loaded_csv_count = len(annual_stats_tables) + len(tile_count_tables)

        print("PHASE 1 RASTER INSPECTION SUMMARY")
        print("=" * 42)
        print(f"Project folder: {PROJECT_FOLDER}")
        print(f"Core rasters loaded: {len(loaded_core)} / {len(expected_core)}")
        print(f"Annual change rasters loaded: {len(loaded_annual_change)} / {len(year_pairs)}")
        print(f"Annual hotspot rasters loaded: {len(loaded_annual_hotspot)} / {len(year_pairs)}")
        print(f"CSV tables loaded: {loaded_csv_count}")
        print(f"Alignment passed: {alignment_passed if 'alignment_passed' in globals() else 'NOT CHECKED'}")

        issues = []
        if missing_core:
            issues.append(f"Missing core rasters: {missing_core}")
        if missing_annual_change:
            issues.append(f"Missing annual change rasters: {missing_annual_change}")
        if missing_annual_hotspot:
            issues.append(f"Missing annual hotspot rasters: {missing_annual_hotspot}")
        if not annual_stats_tables:
            issues.append("Annual change stats CSV was not loaded.")
        if not tile_count_tables:
            issues.append("Tile counts CSV was not loaded.")
        if "alignment_passed" in globals() and not alignment_passed:
            issues.append("At least one raster does not match the reference CRS, transform, dimensions, or shape.")

        if issues:
            print("\\nIssues needing attention:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("\\nNo immediate file loading or alignment issues detected.")

        summary_lines = [
            "PHASE 1 RASTER INSPECTION SUMMARY",
            "=" * 42,
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
            f"Project folder: {PROJECT_FOLDER}",
            f"Output folder: {OUTPUT_DIR}",
            f"Core rasters loaded: {len(loaded_core)} / {len(expected_core)}",
            f"Annual change rasters loaded: {len(loaded_annual_change)} / {len(year_pairs)}",
            f"Annual hotspot rasters loaded: {len(loaded_annual_hotspot)} / {len(year_pairs)}",
            f"CSV tables loaded: {loaded_csv_count}",
            f"Alignment passed: {alignment_passed if 'alignment_passed' in globals() else 'NOT CHECKED'}",
            "",
            "Issues needing attention:",
        ]
        if issues:
            summary_lines.extend([f"- {issue}" for issue in issues])
        else:
            summary_lines.append("- None")

        summary_path = OUTPUT_DIR / "phase1_raster_inspection_summary.txt"
        summary_path.write_text("\\n".join(summary_lines), encoding="utf-8")
        print(f"\\nSaved summary: {summary_path}")
        """
    ),
    md("## 15. Package Results for Download"),
    code(
        """
        zip_base = OUTPUT_DIR.parent / OUTPUT_DIR.name
        zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=OUTPUT_DIR)
        print(f"Created results package: {zip_path}")

        try:
            from google.colab import files
            files.download(zip_path)
        except Exception as exc:
            print("Automatic browser download was not available.")
            print(f"ZIP file remains saved here: {zip_path}")
            print(f"Reason: {exc}")
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
