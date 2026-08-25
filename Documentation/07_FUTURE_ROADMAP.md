# Future Roadmap

## Recommended sequence

### Stage 0: complete migration and provenance

1. Transfer and verify all essential local data.
2. Recreate the Python environment and pass smoke tests.
3. Export/version the missing Earth Engine embedding source.
4. Create checksums or an object-storage manifest for authoritative rasters.
5. Record product versions, AOI, thresholds and run metadata in one machine-
   readable configuration.

Do not begin a national run before this stage is complete.

### Stage 1: convert scripts into an AOI-driven pipeline

Current scripts contain Bass Coast paths, years and thresholds. Refactor into a
configuration-driven pipeline with:

- AOI identifier and geometry;
- embedding product/version;
- start/end years;
- source and output object-storage paths;
- grid resolution and CRS;
- threshold policy;
- patch connectivity and minimum sizes;
- DEA/NDVI product versions; and
- run ID, checkpoint path and provenance manifest.

Separate stages into independently resumable jobs:

1. embedding acquisition/export;
2. raster QA;
3. temporal metrics and state raster;
4. DEA/NDVI alignment;
5. region extraction and tile-edge dissolve;
6. region histories and summaries;
7. browser tile/index publication; and
8. validation/report generation.

### Stage 2: multi-area pilot before Australia

Choose several contrasting AOIs: urban growth, agricultural land, forest,
coastal vegetation and a low-change reference landscape. Confirm:

- threshold stability;
- water/cloud/nodata behaviour;
- region grouping sensitivity;
- DEA/NDVI coverage;
- processing time and storage per square kilometre;
- browser performance; and
- case-study interpretability.

This is safer than jumping directly from Bass Coast to all of Australia.

### Stage 3: cloud-scale Australia processing

Likely AWS architecture:

- S3 for source and derived COGs, Parquet tables and manifests;
- STAC catalog for raster discovery and provenance;
- AWS Batch/ECS/EC2 or Kubernetes jobs for window/tile processing;
- DynamoDB/PostgreSQL/PostGIS for region metadata and spatial queries;
- CloudFront/CDN for raster/vector tiles and static assets;
- Step Functions or a workflow engine for retries/checkpoints; and
- CloudWatch for logs, duration, failures and cost.

Process by stable spatial tiles, not by a national in-memory array. Each tile
must include a small overlap, then connected regions crossing tile boundaries
must be reconciled/dissolved to avoid duplicate or truncated events.

Storage estimates must be measured from a multi-AOI pilot. A naive area-ratio
projection from Bass Coast is unreliable because ocean fraction, compression,
region density and retained products vary. Expect tens to hundreds of gigabytes
for optimized national derivatives and potentially terabytes if all yearly raw
and intermediate rasters are retained. Establish retention rules before export.

### Stage 4: production map services

Replace national GeoJSON/PNG delivery with:

- vector tiles for regions;
- tiled raster services for annual change and hot/cold surfaces;
- server-side spatial/attribute filtering;
- paged detail/history APIs;
- stable feature IDs and versioned schemas;
- caching and rate limiting; and
- monitoring and accessibility testing.

Keep the current MapLibre UI concepts, but load only data for the visible map
and selected filters.

### Stage 5: mobile delivery

Build the shared web/API foundation first. Then choose:

- responsive Progressive Web App for the lowest maintenance cost; or
- a native shell/React Native/Flutter client if offline maps, push alerts or
  device-native workflows are required.

Do not duplicate analytical logic in mobile clients. Mobile and web should call
the same versioned APIs.

## Dataset integration priorities

### High-value candidates

- fire history/severity where wildfire interpretation is required;
- canopy cover/height or vegetation structure for forest questions;
- restoration/project boundary datasets for known before/after evaluation;
- planning/development footprints for artificial-surface investigation;
- climate/rainfall/drought context for NDVI anomalies; and
- field observations or curated case-study labels for accuracy assessment.

For every new source, define:

1. the question it answers;
2. temporal coverage and update frequency;
3. spatial resolution and alignment rule;
4. access/licence/API limits;
5. uncertainty/nodata meaning;
6. whether it is evidence, reference or target label; and
7. how it changes a user decision.

### Lower immediate priority

- Esri full-scale enrichment: retain as optional broad-family cross-check.
- Dynamic World: reconsider only for a 10 m/sub-annual question that justifies
  class noise and Earth Engine dependency.
- Nearmap: potentially useful for high-resolution case validation, subject to
  licence, historical access and delivery constraints.

## Predictive modelling

Do not train a model simply because the feature table exists. First define:

- prediction target;
- decision horizon;
- spatial/temporal validation split;
- reliable labels and class balance;
- leakage controls;
- uncertainty and abstention; and
- stakeholder action based on prediction.

Potential research models include embedding/NDVI trajectory clustering,
land-cover transition prediction, anomaly prioritization and restoration
response modelling. These should be separate from the existing descriptive
pipeline.

## Quality gates for national readiness

- Reproducible GEE source and versioned config.
- Window/tile processing with resume and idempotency.
- Cross-tile region reconciliation.
- Stable thresholds or documented regional calibration.
- Independent validation beyond DEA/NDVI agreement.
- Storage, compute and API cost benchmark.
- Browser load test with realistic concurrency.
- Accessibility and mobile viewport test.
- Provenance visible for every displayed metric and imagery source.
- Clear public wording that avoids causal overclaiming.
