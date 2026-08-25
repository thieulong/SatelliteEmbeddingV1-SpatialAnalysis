# Data and Reproduction

## GitHub versus local data

GitHub contains the deployed browser package, documentation, core source scripts,
notebooks and small reference outputs. It does not contain the authoritative
multi-gigabyte rasters or all generated tables.

Approximate local directory sizes at handover:

| Directory | Approximate size | Transfer priority |
| --- | ---: | --- |
| `GEE_BassCoast_Data/` | 4.1 GB | Essential |
| `BassCoast_Phase2_Pixel_Sampling_outputs/` | 26 MB | Essential for sampled reruns |
| `BassCoast_Phase3_DEA_LandCover_Pipeline_outputs_full_sample/` | 2.4 GB | Preserve completed run |
| `BassCoast_Phase5_WallToWall_DEA_Summary_outputs/` | 69 MB | Preserve summary run |
| `BassCoast_Phase8_NDVI_Pilot_outputs/` | 7.7 MB | Preserve pilot |
| `BassCoast_Phase9_Map_Data_Preparation_outputs/` | 554 MB | Essential for app rebuild |
| `BassCoast_Phase10_WallToWall_Context_outputs/` | 747 MB | Essential for app rebuild |
| `AusHabitat_Sentinel2_Annual/` | 4.8 GB | Optional visual imagery |

The essential and completed-run data is roughly 13 GB before backups and
temporary files. Use an external drive or managed object storage; do not push
these folders directly to normal Git.

## Authoritative input raster inventory

`GEE_BassCoast_Data/` contains 26 files in the handover snapshot, including:

- endpoint change and endpoint hotspot;
- seven annual-change and seven annual-hotspot rasters;
- cumulative, mean and maximum annual change;
- persistence and persistent masks;
- variance and slope;
- first hotspot year and maximum change year; and
- supporting CSV exports.

The authoritative grid is `15586 x 12269`, EPSG:4326, approximately 10 m.

## Environment recreation

Recommended commands from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r analysis/requirements.txt
```

The last verified environment used Python 3.12.12, Rasterio 1.5.0 and GDAL
3.12.1 on Apple Silicon macOS. Rasterio wheels can bundle a different compatible
GDAL version on another platform; record it in new run diagnostics.

## Transfer validation

After copying the large folders:

```bash
source .venv/bin/activate
python analysis/scripts/verify_transfer.py --project-root .
```

The optional Sentinel imagery is included in this strict check. If those files
are intentionally omitted, review those warnings separately from missing core
analysis data.

## Recommended smoke tests

### Compile all Python source

```bash
python -m compileall -q analysis/scripts
```

### Phase 5 synthetic test

```bash
python analysis/scripts/phase5_wall_to_wall_dea_summary.py \
  --thresholds analysis/reference_outputs/phase2/phase2_thresholds.csv \
  --self-test
```

### Phase 10 synthetic test

```bash
python analysis/scripts/phase10_wall_to_wall_context.py --self-test
```

### Small DEA coordinate run

```bash
python analysis/scripts/phase3_dea_landcover_pipeline.py \
  --input BassCoast_Phase2_Pixel_Sampling_outputs/basscoast_phase2b_review_points.csv \
  --output-dir migration_smoke_phase3 \
  --max-points 10 \
  --chunk-size 10 \
  --force
```

This requires internet access to DEA COGs. Inspect the warnings and effective
source counts rather than accepting a zero exit code alone.

## Main rerun commands

### Full 89,707-point DEA sample

```bash
python analysis/scripts/phase3_dea_landcover_pipeline.py \
  --input BassCoast_Phase2_Pixel_Sampling_outputs/basscoast_phase2_sampled_pixels.csv \
  --output-dir BassCoast_Phase3_DEA_LandCover_Pipeline_outputs_full_sample \
  --chunk-size 1000 \
  --resume
```

### Wall-to-wall DEA summaries

```bash
python analysis/scripts/phase5_wall_to_wall_dea_summary.py \
  --project-folder GEE_BassCoast_Data \
  --thresholds analysis/reference_outputs/phase2/phase2_thresholds.csv \
  --output-dir BassCoast_Phase5_WallToWall_DEA_Summary_outputs \
  --window-size 512 \
  --resume
```

### NDVI pilot

```bash
python analysis/scripts/phase8_ndvi_pilot.py \
  --review-points BassCoast_Phase2_Pixel_Sampling_outputs/basscoast_phase2b_review_points.csv \
  --dea-context BassCoast_Phase3_DEA_LandCover_Pipeline_outputs/basscoast_phase3_dea_long.csv \
  --output-dir BassCoast_Phase8_NDVI_Pilot_outputs
```

The original default pointed through the Esri cross-check output because that
table carried DEA context during experimentation. Prefer the merged Phase 3 DEA
long table if its columns match the script's expected schema; validate with a
small run first.

### Common-grid map preparation

```bash
python analysis/scripts/phase9_map_data_preparation.py \
  --project-folder GEE_BassCoast_Data \
  --output-dir BassCoast_Phase9_Map_Data_Preparation_outputs \
  --thresholds analysis/reference_outputs/phase2/phase2_thresholds.csv \
  --review-points BassCoast_Phase2_Pixel_Sampling_outputs/basscoast_phase2b_review_points.csv \
  --fresh
```

### Complete annual DEA/NDVI context

```bash
python analysis/scripts/phase10_wall_to_wall_context.py \
  --phase9-dir BassCoast_Phase9_Map_Data_Preparation_outputs \
  --output-dir BassCoast_Phase10_WallToWall_Context_outputs \
  --resume
```

### Rebuild browser-ready data

After Phase 9 and Phase 10 are complete:

```bash
python analysis/scripts/prepare_app_data.py
```

This regenerates `public/data` from the transferred outputs. It intentionally
does not regenerate the separate Esri Wayback release configuration. Commit or
back up the currently deployed browser package before running it.

## Notebooks

The Phase 1 and Phase 2 notebooks were built for Google Colab and mount Google
Drive. On a new local-only setup, either change `PROJECT_FOLDER` to
`GEE_BassCoast_Data` or rerun in Colab after uploading the rasters. Do not load
all rasters into memory. Preserve the windowed implementation.

Before calling a generated notebook ready, compile every code cell sequentially;
`compile()` catches issues that basic JSON or AST inspection can miss.

## External services

The pipeline currently reads public resources from:

- DEA public COG and STAC endpoints;
- Esri Annual Land Cover service for the retained cross-check;
- OpenStreetMap/Nominatim in the application; and
- Esri World Imagery and Wayback metadata/tiles in the application.

Network services can change. Record URLs, product versions, dates and warnings
in every future run.

## Missing provenance item

Export the original Google Earth Engine embedding-analysis code into a source
file such as `analysis/gee/basscoast_embedding_change.js`. The repository has a
Sentinel-2 visual export script in the old local app workspace, but that is not
the source that produced the embedding metrics.
