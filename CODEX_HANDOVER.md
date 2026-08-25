# AusHabitat Codex Handover

This file is the entry point for a new Codex instance or developer taking over
the AusHabitat project.

## Read first

Read these files in order before changing analysis logic or the web application:

1. `Documentation/README.md`
2. `Documentation/00_CURRENT_STATE.md`
3. `Documentation/01_METHODS_AND_PIPELINE.md`
4. `Documentation/02_VERIFIED_RESULTS.md`
5. `Documentation/03_DECISION_LOG_AND_BOUNDARIES.md`
6. `Documentation/04_DATA_AND_REPRODUCTION.md`
7. `Documentation/05_WEB_APPLICATION.md`
8. `Documentation/06_STAKEHOLDER_DIRECTION.md`
9. `Documentation/07_FUTURE_ROADMAP.md`
10. `Documentation/08_GLOSSARY.md`
11. `Documentation/09_DATA_SOURCES_AND_PROVENANCE.md`
12. `Documentation/MIGRATION_CHECKLIST.md`

The small files under `analysis/reference_outputs/` are the evidence behind the
main numerical statements in the handover. Core notebooks and Python scripts
are under `analysis/`.

## Non-negotiable interpretation boundaries

- A satellite-embedding hot spot is evidence of strong change in embedding
  space. It is not, by itself, a causal label such as clearing, construction,
  restoration or degradation.
- DEA Land Cover and NDVI provide supporting context. Agreement is not a model
  accuracy score and neither dataset is treated as perfect ground truth.
- The behavioural categories overlap and describe temporal signal patterns.
  They are not mutually exclusive real-world land-use classes.
- The 89,707-point table is a balanced, category-based sample. It is not an
  area-weighted representation of Bass Coast.
- The 191,224,634 figure is the number of cells in the complete 10 m rectangular
  raster grid, not a CSV containing 191 million enriched records.
- The authoritative embedding rasters remain 10 m. The integrated DEA/NDVI and
  web-map analytical grid is approximately 30 m.

## Current product

- Published application:
  `https://thieulong.github.io/SatelliteEmbeddingV1-SpatialAnalysis/`
- Study area: Bass Coast, Victoria, Australia.
- Analysis period: 2017-2024, with seven annual change intervals.
- Application regions: 13,784 total, comprising 13,477 change regions and 307
  low-change reference regions.
- Application stack: static HTML/CSS/JavaScript, MapLibre GL JS, browser-ready
  GeoJSON/JSON/PNG assets, OpenStreetMap, Esri reference imagery and date-checked
  Esri Wayback imagery.

## Before doing new work

1. Inspect `git status` and do not discard user changes.
2. Run the migration checks in `Documentation/MIGRATION_CHECKLIST.md`.
3. Confirm which large local datasets are present; they are intentionally not
   stored in GitHub.
4. Use windowed raster processing. Do not load or flatten the complete raster
   stack into memory.
5. Reproduce a smoke test before starting an Australia-wide run.
6. Keep detection, contextual interpretation and any future prediction model as
   separate stages with explicit provenance.

## Known handover gap

The original Google Earth Engine script that generated the embedding-change
rasters was not found as a standalone source file in the local repository at
handover time. Its implemented equations, thresholds and exported products are
documented, but the Earth Engine source should be exported from the owner's GEE
account and added to version control before national scaling.
