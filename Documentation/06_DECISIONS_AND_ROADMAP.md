# Decisions and Roadmap

## Decision principles

- Prefer evidence that can be reproduced from coordinates and annual products.
- Keep detection separate from contextual interpretation.
- Use samples for development and diagnostics; use wall-to-wall aggregation for
  complete-area summaries and application products.
- Avoid claims that exceed the resolution, class system, or validation source.
- Design Bass Coast as the regression-test case for national scaling.

## Major decisions

### Euclidean embedding distance retained

The project consistently used Euclidean distance between co-located annual
64-dimensional embeddings. For unit-length embeddings it is monotonic with
dot-product similarity, so relative ranking is coherent. The choice remains
part of the implemented method, but a future national methods review should
compare it with the official dot-product/angle guidance and version the choice.

### Samples before wall-to-wall processing

The complete 10 m grid is too large for exploratory flattening. Category-based
sampling enabled rapid inspection, external-data debugging, and balanced
comparison of rare behaviours. Wall-to-wall processing was added only after
the sampled pipeline and access methods were reliable.

### Local Python for remote COG processing

Colab remote raster reads were inconsistent and obscured useful error details.
The DEA pipeline moved to local Python with GDAL/rasterio configuration,
coordinate diagnostics, fallbacks, checkpointing, and resume support.

### DEA Land Cover as primary categorical context

DEA was selected because it provides annual, Australia-wide, analysis-ready
Level 3 and Level 4 land-cover classes, accessible as cloud-optimized rasters.
It aligned with the Australian scope and scaled better than manually scraping a
viewer.

### DEA Level 3 and Level 4 retained together

- Level 3 gives robust broad classes such as natural terrestrial vegetation,
  cultivated terrestrial vegetation, artificial surface, bare surface, water,
  and aquatic vegetation.
- Level 4 adds detailed vegetation structure and cover information.

The application shows broad and detailed context but avoids implying that a
Level 4 class is more spatially precise than the native DEA support.

### Approximately 30 m common support

Embedding metrics originate at 10 m; DEA Land Cover and GeoMAD NDVI are
approximately 30 m. The application aggregates three-by-three embedding cells
to a common 30 m grid rather than pretending each 10 m cell has independent
30 m context. The original 10 m rasters remain authoritative and available for
fine-scale analysis.

### NDVI added as continuous vegetation evidence

Stakeholder feedback emphasized NDVI as a familiar baseline for vegetation
condition and temporal drying/restoration studies, while noting that NDVI
cannot distinguish canopy, understory, structures, or many non-vegetation
changes. The project therefore uses NDVI to describe greening/browning evidence
and to compare vegetation-change magnitude, not as a land-cover label.

### Esri and Dynamic World kept outside the core stack

Dynamic World offered similar broad classes but added Google Earth Engine
access and temporal-compositing complexity without a clear gain for the current
Australian implementation. Esri Annual Land Cover was tested at 900 review
points and retained as optional research: useful broad-family agreement, but
insufficient added native-class/timing value to justify another production
dependency.

### Connected regions instead of individual cells

Rendering millions of cells is not usable or scalable. Neighbouring common-grid
cells with the same interaction-state mask are connected into regions. This
reduces rendering load and gives users an area to select. The trade-off is that
region boundaries are analytical interaction boundaries, not surveyed event
polygons.

### Explicit evidence filters instead of opaque confidence tiers

Early prototypes used attention/evidence tiers. They were removed because the
meaning was difficult for non-specialists. The current UI exposes the actual
supporting evidence—DEA transition and NDVI change—and lets users require all
or any selected signals.

### Static web prototype before cloud architecture

The Bass Coast product uses GitHub Pages to validate interaction design and
communication without backend complexity. This architecture is not the target
for national delivery.

## Stakeholder and supervisor direction retained

- Keep the presentation and product understandable to non-specialists while
  preserving technical defensibility.
- Show both hot/change areas and low-change references.
- Provide annual timelines, land-cover history, NDVI, and visual imagery.
- Compare embedding signals with traditional vegetation indices rather than
  assuming one replaces the other.
- Investigate whether embeddings detect complex spatial, temporal, and textural
  change that NDVI cannot represent.
- Preserve opportunities for known-site before/after studies, forecasting,
  clustering, and future predictive models.
- Build toward an interactive national map and eventually mobile access.

## Roadmap

### 1. Complete reproducibility

- Export and version the original embedding Earth Engine script.
- Create checksums for local data and record exact product versions.
- Recreate the environment on the new computer and pass all smoke tests.
- Keep a small Bass Coast regression dataset for future pipeline changes.

### 2. Strengthen validation

- Select known disturbance, restoration, urban-development, agricultural, and
  stable sites across multiple Australian bioregions.
- Add independent reference evidence where licensing permits.
- Define evaluation questions separately for detection, timing, broad context,
  and causal interpretation.
- Quantify sensitivity to threshold, season, resolution, region grouping, and
  embedding collection version.

### 3. Design national processing

- Partition Australia into stable tiles with overlap handling.
- Estimate compute, storage, and egress from representative urban, forest,
  agricultural, arid, coastal, and tropical tiles.
- Store raster products as COG/Zarr and tables as partitioned Parquet or
  GeoParquet in object storage.
- Use resumable jobs, per-tile manifests, checksums, and idempotent processing.
- Build deterministic national region IDs and merge boundary-crossing regions.

### 4. Build production delivery

- Generate vector and raster tiles rather than national GeoJSON.
- Use a spatial database/search service for region and place queries.
- Add an API for region summaries and annual histories.
- Add CDN caching, observability, data-version indicators, and graceful imagery
  fallbacks.
- Keep client interfaces thin so web and future mobile apps share the same API.

### 5. Add modelling only after labels exist

Potential models include event prioritization, anomaly ranking, clustering, or
forecasting. They require a governed training/evaluation dataset with explicit
labels and provenance. DEA/NDVI agreement alone is not sufficient ground truth.

## Definition of the next milestone

The next defensible milestone is not “Australia complete.” It is a versioned,
tile-based pipeline that reproduces Bass Coast, succeeds on several diverse
pilot tiles, records costs and failures, and serves those tiles through the
same API/data contract planned for national deployment.
