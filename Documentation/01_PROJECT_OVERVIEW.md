# Project Overview

Status date: 2026-08-31

## Purpose

AusHabitat investigates whether annual satellite-embedding changes can locate
and characterize landscape change at scale. The current implementation covers
Bass Coast, Victoria, and is the technical foundation for a future
Australia-wide interactive product.

The system deliberately separates three questions:

1. **Where and when is the satellite signal changing?** Google Satellite
   Embedding V1 and derived temporal metrics.
2. **What land-cover and vegetation context is present?** DEA Land Cover and
   DEA GeoMAD NDVI.
3. **How should a person explore the evidence?** Connected map regions,
   timelines, filters, and annual imagery.

It does not yet provide causal event labels or predictions.

## Milestone reached

- Annual 2017-2024 embedding-change rasters were exported and passed alignment
  and data-health checks.
- The complete project-owned Earth Engine embedding workflow and its earlier
  time-series predecessor are retained under `analysis/gee/`.
- A reproducible 89,707-point behavioural sample and a 900-point review subset
  were created without flattening the full raster surface.
- Complete annual DEA Level 3 and Level 4 histories were retrieved for the
  89,707 sampled coordinates.
- Wall-to-wall embedding summaries and complete 30 m annual DEA/NDVI context
  were built in memory-safe windows.
- The common grid was converted into 13,784 connected interaction regions.
- A static browser application was built and published through GitHub Pages.
- Technical and client-facing presentation deliverables were produced.

## Confirmed scale

| Item | Value |
| --- | ---: |
| Complete 10 m rectangular grid | 191,224,634 cells |
| Finite 10 m endpoint cells | 83,045,578 cells |
| Complete 30 m common-support grid | 21,251,640 cells |
| Finite 30 m common-support cells | 9,267,716 cells |
| Category-balanced sample | 89,707 points |
| Review subset | 900 points |
| Sampled DEA point-year records | 717,656 |
| Interaction regions | 13,784 |
| Change regions | 13,477 |
| Low-change reference regions | 307 |
| Region-year context rows | 110,272 |

Grid positions include masked and no-data space within the rectangular extent.
Do not describe every non-finite cell as water without checking the original
mask.

## Current evidence stack

### Detection layer

Google Satellite Embedding V1 annual 64-dimensional vectors. Euclidean distance
between co-located annual vectors is the implemented change magnitude.

### Context layers

- DEA Land Cover annual Level 3 broad class and Level 4 detailed class.
- DEA GeoMAD annual red and near-infrared reflectance, converted to NDVI.

### Visual layer

- OpenStreetMap for labels and roads.
- Esri World Imagery for high-detail present-day reference.
- Date-checked Esri Wayback releases for annual visual context.
- Local Sentinel-2 annual composites are retained as optional research assets,
  not the deployed analytical grid.

## What is not complete

- Australia-wide processing and national storage architecture.
- Independent field/reference validation and a formal accuracy assessment.
- A causal real-world change classifier.
- A supervised prediction model.
- Production APIs, authentication, monitoring, or mobile application.

## Immediate priority after migration

Verify the consolidated local data and recovered Earth Engine sources,
reproduce a Bass Coast smoke test, then design tiled national processing,
versioned run manifests, and cloud-native storage before expanding the area of
interest.
