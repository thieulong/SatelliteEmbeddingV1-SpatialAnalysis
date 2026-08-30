# AusHabitat Codex Handover

This is the mandatory entry point for a new Codex instance or developer.

## Read in this order

1. `Documentation/README.md`
2. `Documentation/01_PROJECT_OVERVIEW.md`
3. `Documentation/02_CANONICAL_PIPELINE.md`
4. `Documentation/03_RESULTS_AND_LIMITATIONS.md`
5. `Documentation/04_DATA_AND_REPRODUCTION.md`
6. `Documentation/05_WEB_APPLICATION.md`
7. `Documentation/06_DECISIONS_AND_ROADMAP.md`
8. `Documentation/SOURCES_AND_PROVENANCE.md`
9. `Documentation/GLOSSARY.md`
10. `Documentation/MIGRATION_CHECKLIST.md`
11. `Documentation/CLEANUP_MANIFEST.md`

## Current checkpoint

AusHabitat is a working Bass Coast prototype for exploring annual landscape
change from 2017 to 2024. It combines:

- Google Satellite Embedding V1 change signals;
- DEA Land Cover Level 3 and Level 4 annual context; and
- DEA GeoMAD annual NDVI vegetation context.

The published application is
`https://thieulong.github.io/SatelliteEmbeddingV1-SpatialAnalysis/`.
It contains 13,784 interaction regions: 13,477 change regions and 307
low-change references.

## Canonical repository layout

- `analysis/`: eight-stage scientific pipeline, notebooks, tools, and compact
  reference evidence.
- `analysis/gee/`: recovered project-owned Earth Engine embedding workflows and
  the optional Sentinel-2 visual export.
- `data/`: ignored local-only raw and processed data; see `data/README.md`.
- `public/`, `src/`, `index.html`: deployed static web application.
- `deliverables/`: latest presentations and technical report.
- `research/`: optional external-dataset experiments, not production stages.
- `Documentation/`: decisions, methods, results, boundaries, and migration.

## Non-negotiable interpretation boundaries

- A hot spot is strong change in embedding space. It is not automatically
  clearing, construction, degradation, restoration, or another causal event.
- DEA and NDVI provide contextual evidence, not perfect ground truth.
- Agreement percentages are enrichment or association signals, not model
  accuracy scores.
- The nine behavioural categories overlap and are rule-based signal patterns,
  not mutually exclusive real-world land-use classes.
- The 89,707-point table is category-balanced, not area-weighted.
- The 191,224,634 figure is the complete 10 m rectangular grid, not a table of
  enriched records. There are 83,045,578 finite endpoint cells.
- The embedding metrics remain authoritative at 10 m. Integrated DEA/NDVI and
  application analysis use an approximately 30 m common-support grid.

## Before changing anything

1. Inspect Git status and preserve user changes.
2. Run `python analysis/tools/verify_transfer.py --project-root .`.
3. Confirm the expected files under `data/`; they are not in GitHub.
4. Use windowed raster processing and checkpoint long network/raster jobs.
5. Test on a small area or sample before any national run.
6. Keep detection, contextual interpretation, validation, and future
   prediction as separate stages with explicit provenance.

## Reproducibility status

The project-owned Earth Engine source is retained under `analysis/gee/`.
`hotspot_characterization_analysis.js` is the canonical complete Bass Coast
embedding workflow; `hotspot_timeseries_analysis.js` is its earlier lighter
time-series predecessor. National scaling still requires a versioned run
manifest recording the dataset version, AOI/tiling scheme, masks, thresholds,
CRS, scale, years, export names, and output checksums.
