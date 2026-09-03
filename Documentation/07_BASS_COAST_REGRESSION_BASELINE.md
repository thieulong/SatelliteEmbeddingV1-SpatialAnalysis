# Bass Coast Regression Baseline

Freeze date: 2026-09-03

Baseline identifier: `bass-coast-regression-2026-09-03`

Canonical Git tag: `bass-coast-regression-2026-09-03`

Scientific and application source commit: `b75da7ac54f47ebee26742e8dee0266c13021597`

The source commit identifies the unchanged scientific and application state
immediately before this documentation-only freeze. The annotated tag resolves
the complete frozen checkpoint, including this baseline record. The baseline
identifier is intentionally fixed; future run records must also capture the
actual Git commit used for each run.

## Status and scope

This is the frozen regression baseline for the completed Bass Coast prototype.
It covers Bass Coast, Victoria, for 2017-2024 and includes the eight-stage
embedding, DEA Land Cover, DEA GeoMAD NDVI, common-support region, and static
web-application workflow.

The baseline is a reproducibility and regression reference. It does not approve
or initiate a next milestone. Scientific validation, national processing,
cloud infrastructure, and web-product development are separate workstreams.
Their priority, scope, acceptance criteria, and sequencing remain subject to a
future planning decision.

## Fixed scientific definitions

- Annual embedding change is Euclidean distance between co-located annual
  64-dimensional Google Satellite Embedding V1 vectors.
- Annual hot spots use the strict Earth Engine comparison `distance > 0.45`.
- Endpoint change is Euclidean distance between 2017 and 2024. Endpoint hot
  spots use the empirical endpoint 95th percentile.
- The application grid is an approximately 30 m common-support
  aggregation/resampling of the 10 m embedding products. Its target grid uses a
  factor of three, but masks, nodata, raster boundaries, and grid alignment mean
  a target cell must not always be interpreted as exactly nine valid source
  cells.
- The original 10 m embedding rasters remain authoritative for the embedding
  measurements. The common-support layer enables integration with
  approximately 30 m DEA and NDVI evidence.
- Hot spots are embedding-space change signals, not confirmed causal events.
  DEA and NDVI provide context, not perfect ground truth or accuracy labels.

## Frozen counts and thresholds

| Item | Baseline value |
| --- | ---: |
| Complete 10 m rectangular grid | 191,224,634 positions |
| Finite 10 m endpoint cells | 83,045,578 |
| Complete approximately 30 m common-support grid | 21,251,640 positions |
| Finite common-support cells | 9,267,716 |
| Category-balanced sample | 89,707 points |
| Review subset | 900 points |
| DEA point-year records | 717,656 |
| Interaction regions | 13,784 |
| Change regions | 13,477 |
| Low-change reference regions | 307 |
| Region-year context rows | 110,272 |
| Annual hot-spot rule | `distance > 0.45` |
| Endpoint p95 | `0.4451330006122589` |
| Variance p95 | `0.008427411317825317` |
| NDVI region-event threshold | `0.05270013838570708` |

The browser package contains fourteen detail shards. Every interaction region
has annual Level 3 and NDVI context for 2017-2024. One small region has no
dominant DEA Level 4 class in 2021; this is a known baseline limitation, not a
missing file.

## Baseline assets

- Canonical Earth Engine workflow:
  `analysis/gee/hotspot_characterization_analysis.js`.
- Authoritative local embedding products: 26 GeoTIFFs under
  `data/raw/embedding_metrics/`.
- Required completed local products: `sampling/`, `dea_sample/`, `map_grid/`,
  and `region_context/` under `data/processed/`.
- Compact versioned evidence: `analysis/reference_outputs/`.
- Versioned application package: `public/data/`.
- Optional verified Sentinel-2 visual archive:
  `data/raw/sentinel2_annual/`, covering 2017-2025.

Large scientific assets remain local and ignored by Git. The transfer checker
confirms expected filenames, non-empty files, and Stage 7 manifest counts; it
does not provide full-file cryptographic verification.

## Regression checks at freeze

The migration regression checks passed using the repository-local Python
3.12.12 environment and the 18 versions pinned in `requirements.txt`:

- exact dependency-version comparison and `pip check`;
- core and optional-imagery transfer verification;
- compilation of Python sources and all 28 code cells in the two notebooks;
- Stage 4 and Stage 7 self-tests;
- ten-point Stage 3 network smoke test with 80/80 successful point-year
  records, complete Level 3 and Level 4 sequences, and zero warnings;
- local browser checks for filters, all timeline states, early/middle/final
  detail shards, basemap modes, evidence matching, and desktop/mobile layout;
  and
- published-application load with the expected 13,784-region metadata.

The ten-point smoke result is a pipeline-health check, not a new scientific
estimate or accuracy assessment.

## Regression contract

Future changes that affect the scientific pipeline or application data must be
tested against this Bass Coast baseline. At minimum, compare:

1. raster alignment, finite-cell counts, thresholds, and state counts;
2. sample and point-year row counts, coverage, warnings, and fallback use;
3. interaction-region and region-year counts;
4. compact reference summaries and application metadata;
5. representative region histories and all detail-shard boundaries; and
6. the interpretation boundaries stated above.

Differences are not automatically failures, but they must be explained,
versioned, and approved as intentional before replacing this baseline.

## Planning boundary

No immediate post-baseline implementation milestone is approved. The next
activity is a planning discussion to select one workstream and define its
question, scope, inputs, deliverables, validation standard, risks, and stopping
conditions before technical implementation begins.
