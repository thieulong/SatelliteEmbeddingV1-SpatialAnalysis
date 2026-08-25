# Current State

Status date: 2026-08-25

## Milestone reached

AusHabitat has a working Bass Coast prototype that connects three evidence
types:

- Google Satellite Embedding V1 change magnitude;
- annual DEA Land Cover Level 3 and Level 4 context; and
- annual DEA GeoMAD NDVI vegetation context.

The prototype supports search, hot- and cold-region display, temporal filters,
behavioural-pattern filters, DEA and NDVI evidence filters, annual summaries,
region details and three basemap modes. It is published through GitHub Pages.

## Completed analytical stages

### Earth Engine export stage

Annual 64-dimensional satellite embedding mosaics were prepared for 2017-2024
over a rectangular Bass Coast area, with water masked. Embedding distances and
temporal summary rasters were exported as GeoTIFFs. The Earth Engine processing
itself is complete for this Bass Coast checkpoint.

### Phase 1: raster inspection

- Loaded metadata for all expected raster products.
- Confirmed 12 core rasters, 7 annual-change rasters and 7 annual-hotspot
  rasters.
- Verified common CRS, transform, width and height.
- Produced windowed statistics and downsampled diagnostic plots without loading
  the complete raster stack into RAM.
- Alignment passed and no issues were reported.

### Phase 2: pixel sampling

- Scanned the aligned rasters in windows.
- Constructed nine temporal-behaviour candidate masks.
- Used fixed-seed reservoir sampling to retain at most 10,000 unique pixels per
  category.
- Produced 89,707 sampled rows.
- Produced a 900-point review subset: 100 points per category, split into 40
  representative, 40 high-signal and 20 random selections.

### Phase 3: DEA Land Cover enrichment

- Processed all 89,707 sampled coordinates for 2017-2024.
- Produced 717,656 point-year records.
- Achieved complete effective Level 3 and Level 4 sequences for every point.
- Used exact-coordinate sampling first, then 3x3 and 5x5 majority fallbacks for
  the small number of missing exact samples.
- Merged extraction and comparison into one checkpointed local Python pipeline.

### Wall-to-wall DEA summary

- Processed the complete valid embedding raster surface in windows.
- Reprojected/resampled annual 30 m DEA classes to the embedding grid for
  aggregate category summaries.
- Did not create a 191-million-row table.
- Confirmed that sampled category-level DEA change shares closely reflected the
  wall-to-wall summary.

### Esri cross-check

- Compared 900 review points over eight years with Esri Annual Land Cover.
- Found strong broad-family agreement but weaker native-class change/timing
  agreement.
- Retained Esri as useful supplementary validation research, not as a required
  final analytical layer.

### NDVI pilot and wall-to-wall context

- Tested annual DEA GeoMAD NDVI at 900 review points.
- Found a stable, moderate association with embedding change and useful signed
  vegetation direction.
- Built complete 30 m annual DEA and NDVI raster context for the application.
- Built 110,272 region-year records: 13,784 regions x 8 years.

### Map preparation and web application

- Aggregated the 10 m embedding surface to a common approximately 30 m support
  grid for DEA/NDVI integration.
- Preserved the complete common-support raster and created interaction polygons
  from connected change/reference cells.
- Published a static, interactive Bass Coast web application.
- Added visual annual imagery through Esri World Imagery Wayback with local
  capture-date verification and an approximately +/-18-month acceptance limit.

## Key current counts

| Item | Confirmed value |
| --- | ---: |
| Complete 10 m rectangular grid | 191,224,634 cells |
| Finite 10 m endpoint embedding cells | 83,045,578 cells |
| Complete 30 m common-support grid | 21,251,640 cells |
| Finite 30 m support cells | 9,267,716 cells |
| Phase 2 sampled points | 89,707 |
| Phase 2B review points | 900 |
| Phase 3 point-year records | 717,656 |
| Interactive regions | 13,784 |
| Change regions | 13,477 |
| Low-change reference regions | 307 |
| Region-year context rows | 110,272 |

The difference between grid positions and finite cells is mainly masked or
non-data space in the rectangular extent, including water and locations outside
the usable land signal. Do not call every non-finite cell water without checking
the original mask.

## What is not complete

- Australia-wide processing has not been run.
- The original embedding Earth Engine source is not versioned in this repo.
- The multi-gigabyte authoritative rasters are not stored in GitHub.
- The web app is a static prototype, not a production national platform.
- Esri is not integrated as a required final evidence layer.
- No supervised predictive model or causal change classifier has been trained.
- No field-validated accuracy assessment has been completed.
- The 10 m Sentinel-2 annual exports are local visual assets and are not the
  deployed analytical grid.

## Immediate handover priority

Transfer the local-only raster/output directories, recreate the Python
environment, run the supplied smoke tests, and export the missing Earth Engine
source before expanding the area of interest.
