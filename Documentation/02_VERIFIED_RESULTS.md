# Verified Results

This document records confirmed results from completed local runs. Values are
also retained under `analysis/reference_outputs/`.

## Raster health

- Core rasters loaded: 12/12.
- Annual-change rasters loaded: 7/7.
- Annual-hotspot rasters loaded: 7/7.
- Alignment passed for CRS, transform, width and height.
- No Phase 1 issues were reported.

## Phase 2 sample

- Expected/loaded raster stack: 24/24.
- Total unique sampled rows: 89,707.
- Random seed: 42.
- Maximum requested per category: 10,000.

| Category | Candidate pixels | Sampled pixels |
| --- | ---: | ---: |
| Endpoint hotspot | 4,550,716 | 10,000 |
| Persistent >= 2 | 1,992,917 | 9,984 |
| Persistent >= 3 | 781,578 | 9,946 |
| High variance | 4,149,329 | 9,950 |
| Positive slope | 4,153,371 | 9,971 |
| Negative slope | 4,156,136 | 9,976 |
| Sudden candidate | 3,064,197 | 9,954 |
| Temporary/recovery candidate | 2,150,815 | 9,926 |
| Stable control | 3,484,658 | 10,000 |

Counts overlap at the candidate-mask level. They must not be summed to estimate
unique Bass Coast area.

## Full sampled DEA enrichment

- Points: 89,707.
- Point-year records: 717,656.
- Successful year records: 717,656.
- Effective complete Level 3 sequences: 89,707/89,707.
- Effective complete Level 4 sequences: 89,707/89,707.
- Exact-point class reads: 717,609.
- 3x3 majority fallbacks: 39.
- 5x5 majority fallbacks: 8.
- Missing effective records: 0.

### DEA change enrichment by category

The percentage below is the share of sampled points in that behavioural
category with at least one DEA Level 3 class change during 2017-2024.

| Category | DEA Level 3 changed share |
| --- | ---: |
| Positive slope | 75.5% |
| Persistent >= 3 | 74.4% |
| Persistent >= 2 | 71.8% |
| Temporary/recovery candidate | 68.4% |
| High variance | 68.2% |
| Negative slope | 65.8% |
| Endpoint hotspot | 64.8% |
| Sudden candidate | 61.6% |
| Stable control | 29.9% |

This is an agreement/enrichment pattern, not classification accuracy. The
embedding-defined change groups contain substantially more DEA broad-class
change than the stable controls, supporting the usefulness of the signal while
also showing that the datasets measure different aspects of change.

### Common sampled Level 3 transitions

- Cultivated -> Cultivated: 34,175 points.
- Natural -> Natural: 25,443 points.
- Natural -> Cultivated: 20,931 points.
- Cultivated -> Natural: 3,184 points.
- Natural -> Artificial: 1,550 points.
- Cultivated -> Artificial: 935 points.

An unchanged 2017-to-2024 endpoint class does not imply no intermediate class
changes; the annual sequence must be inspected.

### Timing agreement

The first DEA Level 3 change year was compared with the embedding maximum-change
year and first-hotspot year using a +/-1-year tolerance. Results varied strongly
by behavioural category. Examples:

- Persistent >= 3: first DEA change matched first embedding hotspot within one
  year for 64.6% of DEA-changed points.
- Negative slope: first DEA change matched embedding maximum-change year within
  one year for 62.6%.
- Positive slope: the analogous shares were low, showing that a trend metric is
  not a direct event-year detector.

Timing agreement is partial rather than universal. Annual products, spatial
support and class stability can all shift apparent event years.

## Wall-to-wall DEA summary

The complete valid raster surface produced category-level shares close to the
89,707-point sample:

| Category | Wall-to-wall Level 3 changed share |
| --- | ---: |
| Positive slope | 75.3% |
| Persistent >= 3 | 74.0% |
| Persistent >= 2 | 72.3% |
| High variance | 68.3% |
| Temporary/recovery candidate | 67.9% |
| Negative slope | 67.2% |
| Endpoint hotspot | 64.7% |
| Sudden candidate | 60.8% |
| Stable control | 30.0% |

This similarity supports the category-balanced sample as a diagnostic summary,
while the wall-to-wall run remains the source for spatial prevalence.

## Esri cross-check

Scope: 900 points x 8 years = 7,200 records.

- Usable Esri coverage: 7,200/7,200.
- Broad-family annual agreement with DEA: 6,719/7,200 (93.3%).
- Strong or broad semantic native-label matches: 65.9%.
- Native-class changed/stable agreement: 48.3%.
- Native changed-point overlap (Jaccard): 35.8%.
- Native first-change timing within +/-1 year: 54.8% of points changed in both.
- Harmonized broad-family changed/stable agreement: 92.6%.

Conclusion: Esri is useful as a high-level cross-check and supplies intuitive
labels, but it did not add enough reliable temporal detail to replace DEA or
become a required final pipeline input. "Rangeland" was especially ambiguous.

## NDVI pilot

Scope: 900 points, 7,200 annual records and 6,300 annual intervals.

- NDVI point-year and interval coverage: 100%.
- Overall Pearson correlation between embedding distance and absolute NDVI
  change: 0.623.
- Overall Spearman correlation: 0.574.
- Point-clustered 95% bootstrap interval for Spearman: 0.552-0.599.
- Interval-specific Spearman range: 0.522-0.642.
- Exact maximum-change-year agreement: 40.8%.
- Maximum-change-year agreement within one year: 64.4%.
- First-event agreement within one year: 55.4%.

### NDVI event comparison

Using pilot threshold `0.075778`:

- Both embedding hotspot and NDVI event: 1,221 intervals.
- Embedding hotspot only: 342.
- NDVI event only: 1,561.
- Neither: 3,176.
- NDVI support among embedding hotspot intervals: 78.1%.
- Embedding hotspot support among NDVI event intervals: 43.9%.

These are cross-signal outcomes, not true/false positives. NDVI can change due
to vegetation condition without a broad structural embedding event; embedding
can respond to non-vegetation changes that NDVI should not detect.

## Complete 30 m map surface

The common-support grid contains 21,251,640 cells:

| State | Cell count | Share of finite support |
| --- | ---: | ---: |
| No data | 11,983,924 | not applicable |
| Cold | 379,956 | 4.1% |
| Background | 7,706,057 | 83.1% |
| Episodic hotspot | 853,175 | 9.2% |
| Persistent hotspot | 328,528 | 3.5% |

Finite support totals 9,267,716 cells.

The interaction polygons contain 13,477 hot regions and 307 low-change
reference regions. Polygon thresholds retained 93.0% of hot source-state cells
and 38.8% of cold source-state cells. Excluded small cells remain in the raster.

## Complete annual context

- Interactive regions: 13,784.
- Region-year rows: 110,272.
- Years: 2017-2024.
- NDVI region coverage: effectively 100% every year.
- DEA Level 3/4 cell coverage within mapped regions: above 99.98% every year.
- One region has an unknown Level 4 dominant class in 2021; Level 3 and NDVI
  remain available.
- Warnings: none.

Evidence-pattern counts:

- embedding + DEA + NDVI: 11,735 regions;
- embedding + DEA: 1,041;
- embedding + NDVI: 429;
- embedding only: 272;
- other/non-embedding combinations: remaining regions, including cold
  references.

These patterns are descriptive evidence combinations, not confidence scores.

## Overall conclusion at handover

The project has demonstrated a reliable end-to-end Bass Coast workflow from
embedding-change detection to raster QA, sampled diagnostics, independent land
cover and vegetation context, complete region summaries and interactive web
delivery. It has not demonstrated causal land-change classification or national
production readiness.
