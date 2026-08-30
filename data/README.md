# Local Data Layout

The contents of `data/raw/` and `data/processed/` are intentionally ignored by
Git because they contain multi-gigabyte rasters and generated tables.

## Required structure

```text
data/
  raw/
    embedding_metrics/       # Authoritative 10 m GEE-derived metric rasters
    sentinel2_annual/        # Optional 10 m visual composites, 2017-2025
  processed/
    raster_qa/               # Stage 1 reports and figures
    sampling/                # Stage 2 full and review samples
    dea_sample/              # Stage 3 complete sampled DEA histories
    dea_wall_to_wall/        # Stage 4 aggregate comparison tables
    ndvi_pilot/              # Stage 5 pilot tables and threshold provenance
    map_grid/                # Stage 6 common-grid rasters and region geometry
    region_context/          # Stage 7 annual DEA/NDVI rasters and histories
```

Only `embedding_metrics`, `sampling`, `dea_sample`, `map_grid`, and
`region_context` are required to reproduce the present application package.
The Sentinel-2 folder is optional because the deployed app currently uses
date-checked Esri Wayback imagery for annual visual context.

Run `python analysis/tools/verify_transfer.py --project-root .` after copying
the data. Add `--include-optional-imagery` to verify Sentinel-2 exports too.
