# Bass Coast NDVI–Embedding Comparison Study Design

## Decision Context

Dynamic World will not be added at this stage because it would contribute another categorical land-cover model with substantial overlap with the existing Esri labels. DEA Land Cover remains the primary contextual classification. Esri is retained only as an optional secondary descriptor and disagreement flag.

NDVI addresses a different question: whether the annual embedding-distance signal corresponds to observable changes in vegetation greenness, and whether the embedding signal detects changes that NDVI does not represent well.

## Research Question

Can annual AI embedding-space distance detect vegetation degradation and restoration patterns as well as, or more comprehensively than, traditional NDVI change measures across different land-cover settings in Bass Coast?

This is a comparative signal study. NDVI is a baseline, not ground truth, and correlation is not classification accuracy.

## Why the Wildfire NDVI Threshold Is Not Transferable

The referenced wildfire study calibrated an NDVI threshold of 0.66 using experiments within a selected dense forest and excluded non-forest land-cover types. Its outcome represented locally defined forest vulnerability, not general landscape change.

Bass Coast contains natural woody and herbaceous vegetation, cultivated land, built surfaces, bare ground and water. A single 0.66 threshold would therefore mix ecological condition with land-cover type and seasonality. Thresholds for this project must be estimated from Bass Coast controls and stratified by land-cover context.

## Analysis Unit

The first test will use the existing 900 Phase 2B review points:

- 9 behavioural categories;
- 100 points per category;
- 8 annual observations from 2017 through 2024;
- 7 annual intervals per point;
- 6,300 point-interval comparisons.

The 900-point table is intentionally balanced by behavioural category. Results describe these selected behavioural groups and must not be presented as Bass Coast area prevalence.

## NDVI Source and Preparation

Use harmonized Sentinel-2 Level-2A surface reflectance in Google Earth Engine. Calculate NDVI from the red and near-infrared bands after cloud and shadow masking.

For every point and year, retain:

- annual median NDVI;
- annual 25th and 75th percentiles;
- annual minimum and maximum after quality filtering;
- within-year NDVI amplitude;
- number of valid observations;
- optional fixed-season medians using identical calendar windows each year.

Monthly or seasonal composites should be created before annual summaries so that cloud contamination and seasonal crop/grass cycles can be identified. A valid-observation threshold must be applied before interpreting a yearly value.

Sample the corresponding 10 m NDVI pixel and a 3-by-3 footprint summary. This preserves direct alignment with the 10 m embedding point while measuring local spatial sensitivity.

## Derived NDVI Change Metrics

For each annual interval, calculate:

- signed NDVI change: `NDVI(t+1) - NDVI(t)`;
- absolute NDVI change;
- percentage or standardized change where mathematically appropriate;
- largest absolute NDVI-change year;
- endpoint NDVI change from 2017 to 2024;
- NDVI variance and linear slope;
- disturbance-and-recovery pattern flags.

The signed value is important because embedding Euclidean distance measures magnitude but does not independently indicate whether vegetation increased or decreased.

## Core Comparisons

### 1. Direct Magnitude Association

Compare annual embedding distance with absolute annual NDVI change using:

- Spearman rank correlation as the primary association measure;
- Pearson correlation as a secondary linear measure;
- point-clustered bootstrap confidence intervals;
- scatter plots and binned response curves.

Calculate results overall and separately by DEA Level 3 and selected Level 4 classes. A single pooled correlation could hide strong vegetation relationships behind irrelevant water or built-surface observations.

### 2. Timing Agreement

Compare the year of maximum annual embedding change with the year of maximum absolute NDVI change:

- exact-year agreement;
- agreement within one year;
- distribution of year differences.

This repeats the existing DEA timing framework using a continuous spectral baseline.

### 3. Threshold-Based Event Comparison

Estimate an NDVI change threshold from the stable controls, preferably within relevant DEA land-cover strata. A starting definition is the 95th percentile of absolute annual NDVI change among quality-controlled stable controls.

Compare this NDVI event flag with the embedding annual-hotspot flag. Report agreement, embedding-only events and NDVI-only events. Do not describe these as true positives or false positives without independent event records.

### 4. Trajectory Comparison

Compare complete 2017–2024 sequences to distinguish:

- persistent low-change trajectories;
- abrupt NDVI decline;
- decline followed by recovery;
- sustained NDVI increase;
- high embedding change with little NDVI response;
- high NDVI change with little embedding response.

The last two groups are scientifically important because they show where the methods capture different properties.

### 5. Land- and Object-Type Stratification

Use DEA as the primary stratification layer:

- natural woody vegetation;
- natural herbaceous vegetation;
- cultivated vegetation;
- artificial surfaces;
- bare surfaces;
- water and aquatic vegetation.

Use Esri only as a secondary descriptor where it provides an intuitive distinction such as Trees, Crops, Rangeland or Built Area. NDVI performance should be judged primarily in vegetation-relevant strata; limited NDVI response over buildings, roads or water is not evidence that the embedding hotspot is incorrect.

## Known-Site Extension

If Bass Coast Landcare Network can provide independently documented disturbance or restoration sites with event dates and boundaries, run a before-and-after analysis using:

- affected polygons;
- nearby matched control polygons;
- pre-event and post-event NDVI trajectories;
- embedding-distance trajectories;
- event-year and recovery-rate comparisons.

These records would provide stronger validation than DEA or Esri because they supply an independently known event and date. Without documented events, the work remains a cross-signal comparison rather than an accuracy test.

## Interpretation Rules

- High embedding change plus large NDVI decline: vegetation disturbance is spectrally supported.
- High embedding change plus large NDVI increase: greening or restoration is plausible.
- High embedding change plus stable NDVI: investigate structural, built, water, texture or non-greenness change.
- Low embedding change plus large NDVI movement: investigate seasonality, cloud contamination, agriculture or a potentially missed vegetation event.
- Neither signal changes: stable-control evidence.

NDVI must be used as evidence and stratification, not as a universal deletion mask.

## Minimum Outputs

- Quality-controlled annual NDVI table for 900 points.
- Point-interval table containing embedding and NDVI changes.
- Correlation table overall and by DEA class.
- Timing-agreement table.
- NDVI-event versus embedding-hotspot contingency table.
- Trajectory examples for each comparison outcome.
- Maps of embedding-only, NDVI-only and jointly supported vegetation-change candidates.
- Technical report stating denominators, sampling scope and interpretation limits.

## Decision Gate

Scale NDVI to the 89,707 Phase 2 sampled points only if the pilot demonstrates useful coverage and interpretable relationships. Wall-to-wall NDVI production should be performed in Earth Engine as raster exports rather than by making per-pixel web requests.

## References

- [Bayesian prediction of wildfire event probability using NDVI data from an Australian forest](https://www.sciencedirect.com/science/article/pii/S1574954122003491)
- [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
- [Harmonized Sentinel-2 Level-2A surface reflectance](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED)
- [DEA guide to calculating NDVI](https://knowledge.dea.ga.gov.au/notebooks/How_to_guides/Calculating_band_indices/)
