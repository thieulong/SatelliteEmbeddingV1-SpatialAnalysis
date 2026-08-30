# Data and Reproduction

## Storage policy

GitHub contains source code, documentation, compact reference evidence, and the
browser-ready application package. Multi-gigabyte scientific data lives under
ignored `data/raw/` and `data/processed/`.

```text
data/
  raw/
    embedding_metrics/
    sentinel2_annual/          # optional
  processed/
    raster_qa/
    sampling/
    dea_sample/
    dea_wall_to_wall/
    ndvi_pilot/
    map_grid/
    region_context/
```

The directory names describe analytical ownership, while existing filenames
retain historical phase identifiers for provenance.

## Retention tiers

### Required inputs

- `data/raw/embedding_metrics/`: authoritative 10 m embedding-derived GeoTIFFs.
- `data/processed/sampling/`: 89,707-point and 900-point tables plus thresholds.

### Required completed products

- `data/processed/dea_sample/`: final sampled annual DEA history and enriched
  point tables. Completed-run checkpoints and the redundant raw probe table are
  not retained.
- `data/processed/map_grid/`: 30 m map rasters, region inventory, and geometry.
- `data/processed/region_context/`: annual DEA/NDVI rasters, region summaries,
  and region-year histories. Completed checkpoints are not retained.

### Compact analytical evidence

- `data/processed/raster_qa/`
- `data/processed/dea_wall_to_wall/`
- `data/processed/ndvi_pilot/`

These are small enough to preserve locally. Compact headline tables are also
versioned under `analysis/reference_outputs/`.

### Optional imagery

`data/raw/sentinel2_annual/` contains nine approximately 10 m annual visual
composites from 2017-2025. They are useful for research and future tile serving
but are not required by the current GitHub Pages application.

## Authoritative embedding raster set

`data/raw/embedding_metrics/` contains 26 GeoTIFFs:

- seven annual-change rasters;
- seven annual-hot-spot rasters;
- endpoint change and endpoint hot spots;
- cumulative, mean, and maximum annual change;
- persistence and persistent-hot-spot masks;
- annual-change variance and slope; and
- first-hot-spot and maximum-change year.

Do not recompute or overwrite these files until the original Earth Engine
source and collection version have been recorded.

## Environment setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r analysis/requirements.txt
```

Do not migrate `.venv`, `.matplotlib_cache`, `.cache`, `.tmp`, `__pycache__`, or
package-manager caches. They are machine-specific and regenerable.

## Transfer verification

Core data:

```bash
python analysis/tools/verify_transfer.py --project-root .
```

Core data plus optional Sentinel-2 exports:

```bash
python analysis/tools/verify_transfer.py \
  --project-root . --include-optional-imagery
```

The checker validates expected filenames and reads the Stage 7 manifest counts.
It does not checksum every multi-gigabyte file. For archival transfer, generate
SHA-256 checksums separately and retain them with the transfer record.

## Code validation

```bash
python -m compileall -q analysis research
python analysis/pipeline/stage04_dea_wall_to_wall.py --self-test
python analysis/pipeline/stage07_region_context.py --self-test
```

Compile notebook code cells as Python after parsing the notebook JSON. A valid
`.ipynb` file alone does not prove each generated code cell compiles.

## Safe rerun order

1. Verify transferred raw and processed data.
2. Run Stage 1 raster QA if raw rasters changed.
3. Run Stage 2 only if thresholds or behavioural rules changed.
4. Run a 10-point Stage 3 network smoke test.
5. Rerun Stage 3 full sample only if DEA extraction logic or inputs changed.
6. Run Stage 4 self-test before a complete wall-to-wall comparison.
7. Rerun Stage 5 only if NDVI calibration or sample design changed.
8. Run Stage 6 when thresholds, aggregation, or region rules change.
9. Run Stage 7 when the grid, years, or external context changes.
10. Run Stage 8 and test the browser application.

## Checkpoint policy

Stages 3, 4, and 7 support checkpoints during long runs. Keep checkpoints while
a job is incomplete. After successful final-output verification, checkpoints
may be removed because the final tables/rasters and run manifests are the
retained products.

Never remove checkpoints from an active or failed run until its recovery value
has been assessed.

## Original Earth Engine source

Export the missing embedding-processing script from the Earth Engine Code
Editor and save it as:

```text
analysis/gee/basscoast_embedding_change.js
```

Record collection ID, collection version, AOI, land mask, thresholds, exports,
scale, CRS, and date ranges in the source comments. The retained
`analysis/gee/export_sentinel2_annual.js` is only the optional visual export.

## National scaling

Do not create national CSV or GeoJSON files at cell scale. Recommended cloud
forms are:

- Cloud-Optimized GeoTIFF or Zarr for raster products;
- partitioned Parquet/GeoParquet for summaries and regions;
- object storage partitioned by product, tile, and year;
- a spatial database or vector-tile service for interaction regions; and
- resumable orchestration with per-tile manifests and checksums.

Bass Coast is the regression-test study area for every national pipeline
change.
