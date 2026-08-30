# Verified Results and Limitations

The files under `analysis/reference_outputs/` are the compact evidence for the
figures in this document. Values below are confirmed completed-run results, not
projections.

## Raster health

- All expected core, annual-change, and annual-hot-spot rasters were found.
- CRS, transform, width, height, and shape matched the reference raster.
- Alignment passed.
- Windowed statistics completed without retaining the full stack in RAM.

This establishes data integrity and grid compatibility, not semantic accuracy.

## Sampling outcome

- 89,707 category-based sampled rows.
- Nine behavioural candidate categories.
- Up to 10,000 locations per category with duplicate avoidance.
- 900 review points: up to 100 per category using representative, high-signal,
  and fixed-seed random selection.

The sample is designed to compare behaviours efficiently. It cannot estimate
the area share of those behaviours across Bass Coast without weighting.

## DEA sampled enrichment

All 717,656 point-year records obtained effective DEA Level 3 and Level 4
classes:

| Effective source | Point-year records |
| --- | ---: |
| Exact coordinate | 717,609 |
| 3 x 3 majority fallback | 39 |
| 5 x 5 majority fallback | 8 |
| Missing | 0 |

Complete coverage means the pipeline retrieved a class. It does not mean every
class is correct at 10 m scale or that DEA captured every real-world event.

## Embedding behaviours are enriched for DEA class change

Share of sampled points with at least one DEA Level 3 change during 2017-2024:

| Behavioural category | DEA Level 3 changed share |
| --- | ---: |
| Positive slope | 75.5% |
| Persistent at least 3 intervals | 74.4% |
| Persistent at least 2 intervals | 71.8% |
| Temporary/recovery candidate | 68.4% |
| High variance | 68.2% |
| Negative slope | 65.8% |
| Endpoint hot spot | 64.8% |
| Sudden candidate | 61.6% |
| Stable control | 29.9% |

This is the main validation signal: change-oriented embedding categories were
substantially more likely than stable controls to coincide with at least one
broad DEA land-cover change. It is not an accuracy score because:

- categories were selected from the embedding metrics rather than randomly;
- DEA is supporting data, not perfect truth;
- class changes and embedding changes measure different phenomena; and
- the categories overlap.

## Wall-to-wall comparison

The complete-surface DEA aggregation reproduced the same ordering and similar
shares. For example, positive slope was 75.3%, persistent at least three was
74.0%, endpoint hot spot was 64.7%, and stable control was 30.0%.

This close sample/wall-to-wall agreement supports using the sampled pipeline
for development and diagnostics. It does not make the 89,707-point table an
area-weighted sample.

Wall-to-wall category cell counts must not be added together because the masks
overlap. A cell can be both endpoint-hot, persistent, and high variance.

## Timing agreement is partial

Comparisons used DEA first broad-class change year against:

- embedding maximum-change year, within plus or minus one year; and
- embedding first-hot-spot year, within plus or minus one year.

Agreement varied substantially by behavioural category and timing metric.
Persistent categories aligned better with first-hot-spot timing, while some
slope/sudden categories aligned better with maximum-change timing. The result
supports partial temporal correspondence, not exact annual event dating.

Potential causes include 10 m versus 30 m support, annual compositing, class
boundary noise, seasonal/spectral changes without class changes, and embedding
sensitivity to texture or structures beyond vegetation and land cover.

## NDVI pilot

Across 6,300 valid point-interval comparisons:

- Pearson correlation between embedding magnitude and absolute NDVI change:
  `0.623`.
- Spearman rank correlation: `0.574`.
- Cluster-bootstrap 95% interval for Spearman: approximately `0.552-0.599`.

Event comparison using the pilot's substantial-NDVI-change threshold:

| Comparison | Intervals | Share |
| --- | ---: | ---: |
| Both embedding and NDVI | 1,221 | 19.4% |
| Embedding only | 342 | 5.4% |
| NDVI only | 1,561 | 24.8% |
| Neither | 3,176 | 50.4% |

Among 1,563 embedding-hot intervals, 1,221 also had substantial NDVI change
(`78.1%`). This makes NDVI useful vegetation evidence. The NDVI-only intervals
also show that vegetation varies without necessarily creating an embedding hot
spot.

NDVI is not a categorical label, cannot separate canopy from understory, and
can respond to season, moisture, crop cycles, clouds, and observation quality.

## Complete map context

- 21,251,640 positions in the common 30 m grid.
- 9,267,716 finite common-support cells.
- 1,181,703 hot-state cells: 853,175 episodic and 328,528 persistent.
- 379,956 low-change reference cells.
- 13,784 connected interaction regions.
- 110,272 region-year rows.

Every region/year obtained Level 3 and NDVI context. One region in 2021 lacked
a dominant Level 4 class, although Level 4 cell coverage remained above
99.98%. Annual Level 3 cell coverage exceeded 99.98%, and NDVI coverage was
effectively complete.

## Esri cross-check decision

The 900-point Esri comparison found:

- 801 points where both DEA and Esri broad families remained stable;
- 32 where both changed;
- 34 DEA-only changes; and
- 33 Esri-only changes.

Esri is therefore useful as an optional broad-family cross-check, but native
class definitions and timing did not add enough reliable information to make it
a required final layer. Its code is retained under `research/` rather than the
production pipeline.

## Current scientific limits

- No field-labelled accuracy assessment has been completed.
- No causal event classifier has been trained.
- A land-cover class remaining unchanged does not imply no landscape change.
- A class transition does not establish cause.
- Connected regions are application interaction units, not confirmed event
  boundaries.
- Esri Wayback annual imagery availability and capture dates vary spatially.
- Results are currently demonstrated for Bass Coast and cannot be assumed to
  transfer nationally without stratified validation.
