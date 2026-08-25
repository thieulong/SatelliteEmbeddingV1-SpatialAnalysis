# Bass Coast Phase 8: NDVI Pilot Findings

## Scope

The pilot compares annual Landsat GeoMAD NDVI with embedding change for 900 Phase 2B review points from 2017 to 2024.

The NDVI source is the public DEA Landsat annual Geometric Median product at 30 m. This is a cloud-screened annual representative surface-reflectance composite, not a 10 m Sentinel-2 monthly time series.

## Coverage

- Valid point-year NDVI values: 7,200/7,200 (100.0%).
- Valid annual intervals: 6,300/6,300 (100.0%).
- Median annual clear-observation count: 13.

## Direct Association

- Overall Pearson correlation between embedding distance and absolute NDVI change: 0.623.
- Overall Spearman correlation: 0.574.
- Point-clustered 95% bootstrap interval for Spearman correlation: [0.552, 0.599].
- Strongest category association: endpoint_hotspot (0.548).
- Weakest category association: stable_control (0.213).

## Event Comparison

The NDVI event threshold is 0.0758, defined as the 95th percentile of absolute annual NDVI change among stable-control intervals.
- Both embedding hotspot and NDVI event: 1,221 intervals.
- Embedding hotspot only: 342 intervals.
- NDVI event only: 1,561 intervals.
- Neither signal: 3,176 intervals.
- NDVI support among embedding hotspot intervals: 1,221/1,563 (78.1%).
- Embedding-hotspot support among NDVI event intervals: 1,221/2,782 (43.9%).

These are cross-signal outcomes, not true positives or false positives.

## Consistency Through Time

Annual-interval Spearman correlations ranged from 0.522 to 0.642. The association was therefore present within every annual interval rather than arising only from differences between years.

## NDVI Support by Behavioural Category

- persistent_ge2: 343/415 embedding hotspot intervals supported (82.7%).
- persistent_ge3: 377/474 embedding hotspot intervals supported (79.5%).
- sudden_candidate: 23/29 embedding hotspot intervals supported (79.3%).
- endpoint_hotspot: 91/118 embedding hotspot intervals supported (77.1%).
- positive_slope: 69/90 embedding hotspot intervals supported (76.7%).
- negative_slope: 84/110 embedding hotspot intervals supported (76.4%).
- temporary_or_recovery_candidate: 132/177 embedding hotspot intervals supported (74.6%).
- high_variance: 102/150 embedding hotspot intervals supported (68.0%).

## Timing

- Comparable maximum-change years: 900 points.
- Exact maximum-change-year agreement: 367/900 (40.8%).
- Maximum-change agreement within one year: 580/900 (64.4%).
- Comparable first-event years: 780 points.
- First-event agreement within one year: 432/780 (55.4%).

## NDVI Evidence Labels

- net_greening_signal: 318 points
- net_vegetation_decline_signal: 235 points
- disturbance_and_recovery_signal: 197 points
- ndvi_stable: 114 points
- temporary_greening_signal: 20 points
- temporary_decline_signal: 16 points

## Interpretation

NDVI and embedding distance should be considered complementary. NDVI supplies a signed greenness response, while embedding distance can respond to broader structural, spectral and contextual changes. A modest correlation would therefore be expected and scientifically useful; perfect agreement would indicate that the embedding metric adds little beyond greenness.

The positive-slope and negative-slope behavioural categories describe whether annual embedding-distance magnitude tends to increase or decrease through time. They do not represent vegetation greening or decline; the signed NDVI evidence labels provide that ecological direction.

The sample is balanced by behavioural category and is not an area-weighted sample of Bass Coast. DEA Land Cover and this NDVI baseline also share Landsat lineage, so agreement is not independent ground-truth validation.

A future 10 m Sentinel-2 implementation should be used when monthly or seasonal vegetation trajectories are required. It requires Earth Engine authentication or a separate cloud-scale processing route.

## Warnings

- None.
