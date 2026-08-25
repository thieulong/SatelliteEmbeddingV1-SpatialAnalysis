# Methods and Pipeline

## 1. Scientific idea

For each location and year, Google Satellite Embedding V1 supplies a learned
64-dimensional vector. The individual dimensions are latent features and are
not interpreted directly as trees, buildings or soil. The project compares the
vector at the same spatial location through time to measure how much the
satellite-observed signal changed.

Google documents the embeddings as unit-length vectors and demonstrates
dot-product/angle similarity. For two unit vectors `u` and `v`, Euclidean
distance satisfies `||u-v|| = sqrt(2 - 2(u dot v))`. Euclidean distance is
therefore a monotonic transformation of dot-product similarity for these
vectors: it reverses the direction (larger means less similar) but preserves the
ordering. This is the mathematical basis for retaining the implemented distance
metric while still treating method comparison as future validation work.

For a pixel with embeddings `E_t` and `E_(t+1)`, annual change is:

```text
d_t = sqrt(sum((E_(t+1,b) - E_(t,b))^2 for b = 1..64))
```

Endpoint change uses the same Euclidean distance calculation between 2017 and
2024. A large distance means the learned representation changed strongly. It
does not reveal the direction or cause of change.

## 2. Earth Engine raster production

The completed Bass Coast Earth Engine stage performed the following:

1. Defined a rectangular Bass Coast area of interest.
2. Applied a land mask to exclude water/non-land pixels.
3. Built annual embedding mosaics for 2017-2024.
4. Calculated seven annual Euclidean-distance rasters.
5. Calculated the 2017-2024 endpoint-distance raster.
6. Applied a fixed annual hotspot threshold of `0.45` to every annual interval.
7. Applied the endpoint 95th-percentile threshold to the endpoint raster. The
   threshold carried into later phases is approximately `0.445133`.
8. Calculated temporal summary rasters.
9. Exported GeoTIFFs and summary CSVs.

### Temporal summary metrics

For annual distances `d_1 ... d_7`:

- **Cumulative change:** `sum(d_i)`. This is total annual movement through
  embedding space, not net physical area changed.
- **Mean annual change:** `sum(d_i) / 7`.
- **Maximum annual change:** the largest `d_i`.
- **Persistence count:** number of annual intervals with `d_i >= 0.45`.
  This counts qualifying intervals; it does not require them to be consecutive.
- **Variance:** the population variance of the seven annual distances,
  `mean((d_i - mean(d))^2)`. High variance means change was concentrated in
  stronger spikes rather than similar each year.
- **Slope:** ordinary least-squares slope fitted to annual distance against
  interval index `0..6`. Positive means change magnitude generally increased;
  negative means it generally decreased. It does not mean greening or browning.
- **First hotspot year:** ending year of the first interval above `0.45`.
- **Maximum change year:** ending year of the interval with maximum distance.

## 3. Phase 1: memory-safe raster QA

The first notebook deliberately avoided retaining all raster arrays.

1. Discover files using case-insensitive/glob-based patterns.
2. Read only raster metadata to build the inventory.
3. Compare CRS, affine transform, width and height with one reference raster.
4. Read one `1024 x 1024` window at a time for statistics.
5. Accumulate exact count, minimum, maximum, mean and standard deviation.
6. Estimate the median using a stride-8 sample because exact median requires
   retaining or externally sorting all valid values.
7. Read a reduced output shape for display maps rather than loading the full
   source resolution.

The exact-versus-approximate distinction must remain visible in future QA:

- counts/min/max/mean/std were streamed over all valid windows;
- the median and display histograms were sampled/downsampled;
- maps were visual previews, not replacements for analytical rasters.

## 4. Phase 2: category-based sampling

Flattening roughly 83 million valid 10 m cells and all variables into one CSV
would be unnecessarily large and memory-intensive. Phase 2 therefore sampled
from interpretable temporal-behaviour masks.

### Threshold estimation

Raster values were sampled with stride 8 to estimate percentiles without
loading all cells. The retained thresholds are:

| Threshold | Value |
| --- | ---: |
| Endpoint p95 | 0.4451330 |
| Endpoint p25 | 0.2292768 |
| Variance p95 | 0.0084274 |
| Variance p25 | 0.0011393 |
| Slope p95 | 0.0187616 |
| Slope p05 | -0.0154007 |
| Absolute slope p25 | 0.0025544 |

### Behavioural candidate rules

| Category | Rule and intended signal |
| --- | --- |
| `endpoint_hotspot` | Exported endpoint-hotspot mask equals 1. |
| `persistent_ge2` | At least 2 annual intervals exceeded 0.45. |
| `persistent_ge3` | At least 3 annual intervals exceeded 0.45. |
| `high_variance` | Variance is at or above variance p95. |
| `positive_slope` | Slope is at or above slope p95. |
| `negative_slope` | Slope is at or below slope p05. |
| `sudden_candidate` | Endpoint >= endpoint p95 and persistence <= 1. |
| `temporary_or_recovery_candidate` | Endpoint < endpoint p95 and variance >= variance p95. |
| `stable_control` | Endpoint <= p25, persistence 0, variance <= p25 and absolute slope <= p25. |

These rules overlap. For example, a point can satisfy endpoint hotspot,
persistent and high-variance rules. The final Phase 2 sample attempted to avoid
duplicate coordinates across category rows, so some categories contain slightly
fewer than 10,000 points.

### Reservoir sampling

1. Scan each raster window and calculate the nine masks only for that window.
2. Give every candidate pixel a random priority from a NumPy generator seeded
   with `42`.
3. For each category, retain only the 10,000 smallest priorities encountered so
   far.
4. After the scan, process categories in a fixed order and skip coordinates
   already used by an earlier category.
5. Sample all required raster variables only at retained row/column locations.

This is fixed-seed, approximately uniform random sampling within each rule-based
candidate pool. It is not selection of only the most extreme points.

### Phase 2B review subset

The 900 review points contain 100 points from each category:

- 40 representative points close to the category median across endpoint,
  persistence, variance and slope;
- 40 high-signal points ranked using the category-relevant metric; and
- 20 random points using seed 42.

This subset was designed for review and pilots, not population prevalence.

## 5. Phase 3: DEA Land Cover enrichment

DEA Land Cover annual Cloud Optimized GeoTIFFs were read remotely with
Rasterio/GDAL. The product was `ga_ls_landcover_class_cyear_3`, version `2-0-0`,
for 2017-2024.

For every sampled coordinate and year:

1. Transform longitude/latitude to the DEA raster coordinate system.
2. Sample the exact 30 m DEA pixel.
3. If it is missing, inspect a 3x3 DEA-pixel neighbourhood and take the majority
   valid class.
4. If still missing, inspect a 5x5 neighbourhood.
5. Record the source used and any warning.
6. Store Level 3 and Level 4 labels.

Level 3 is a broad class such as Natural Terrestrial Vegetation, Cultivated
Terrestrial Vegetation, Artificial Surface, Bare Surface or Water. Level 4 adds
vegetation form and cover detail. Sampling a class means retrieving the class
code at a coordinate; it does not train a classifier.

The pipeline builds annual label sequences, detects any adjacent-year class
change, records first change year, summarizes 2017-to-2024 transitions and
compares DEA timing with embedding first-hotspot and maximum-change years.

The pipeline is local because local GDAL/Rasterio remote-COG behaviour was more
reliable and diagnosable than the tested Colab environment. It supports chunk
checkpoints and resume.

## 6. Wall-to-wall DEA summary

The wall-to-wall phase scanned every valid embedding cell in raster windows. DEA
30 m labels were aligned to the embedding grid using nearest-neighbour
resampling, appropriate for categorical data. It accumulated category counts,
transitions and timing summaries without writing one row per raster cell.

"Wall-to-wall" means the complete valid spatial surface was processed, not only
sampled coordinates. It does not mean every grid position has valid data.

## 7. Esri cross-check

Esri Annual Land Cover was evaluated on the 900 review points. Nine sample
locations spanning each corresponding 30 m DEA footprint were used to aggregate
the 10 m Esri classes. DEA and Esri classes were compared through a documented
crosswalk at both native-label and harmonized broad-family levels.

The test showed that Esri can provide intuitive labels, but native change and
timing disagreement was substantial. Esri was therefore not made a mandatory
final layer.

## 8. NDVI pilot

The NDVI pilot used the public annual DEA Landsat Geometric Median product
`ga_ls8cls9c_gm_cyear_3` at 30 m. It sampled annual red and near-infrared derived
NDVI values for 900 review coordinates.

For each point:

- annual NDVI represents vegetation greenness on a conventional -1 to 1 scale;
- signed annual difference gives greening or browning direction;
- absolute annual difference is compared with unsigned embedding distance;
- Pearson correlation measures linear magnitude association;
- Spearman correlation measures monotonic rank association;
- event/timing comparisons test whether large NDVI changes and embedding hot
  intervals co-occur.

The pilot threshold `0.075778` was the 95th percentile of absolute annual NDVI
change among stable-control intervals. The later region-level wall-to-wall NDVI
threshold `0.052700` was recalculated from cold-reference region annual changes;
these thresholds answer different sampling units and must not be interchanged.

## 9. Common 30 m application grid

The 10 m embedding rasters were aggregated by a factor of three to match the
approximately 30 m DEA and Landsat NDVI support. Continuous variables use
appropriate mean/max summaries; categorical/hotspot products use nearest,
maximum or fractional summaries according to meaning.

The 30 m grid is for comparison and delivery. It does not erase or replace the
authoritative 10 m embedding source.

### 30 m change states

Each valid common-support cell is assigned one state:

- `cold`: endpoint <= p25, persistence 0, variance <= p25, absolute slope <=
  p25, and no endpoint or annual hotspot;
- `background`: valid but not hot or cold;
- `episodic_hotspot`: at least one endpoint or annual hotspot;
- `persistent_hotspot`: persistence >= 2;
- `no_data`: unavailable.

### Region grouping

Hot cells (`episodic` or `persistent`) and cold cells are grouped separately.
Eight-neighbour connectivity is used, so side-touching and corner-touching cells
belong to the same component. Components smaller than 9 hot cells or 100 cold
cells are excluded from interaction polygons. They remain in the full raster.

Areas are calculated by transforming polygon coordinates from longitude/
latitude to Australian Albers (`EPSG:3577`) and measuring in square metres.

### Region summaries

- Repeated-change coverage: share of region cells with persistence >= 2.
- Change mainly once: repeated-change coverage < 10%.
- Some repeated change: 10% to < 50%.
- Widespread repeated change: >= 50%.
- Active in selected period: at least 5% of region area exceeded the annual
  hotspot threshold in that interval.
- Overall activity: low/moderate/high thirds of cumulative change among change
  regions; cold references remain low.
- Year-to-year pattern: thirds of regional annual-change variance.
- Change-intensity trend: slope >= 0.01 increasing, <= -0.01 decreasing,
  otherwise no clear trend.

## 10. Wall-to-wall DEA and NDVI context

Annual DEA Level 3, DEA Level 4, NDVI and observation rasters were aligned to
the 30 m grid. Region-level dominant and secondary classes, class shares,
changed-area shares, NDVI means/medians and clear-observation support were
calculated for every year.

The region-level NDVI event threshold is the 95th percentile of absolute annual
NDVI change across cold-reference region intervals. It is used for evidence
filters and greening/browning direction, not as a universal ecological constant.

## 11. Delivery derivatives

The web application receives:

- compact GeoJSON interaction geometry;
- one small feature summary per region;
- 14 detail JSON shards of up to 1,000 regions each;
- hot/cold raster overlays;
- seven annual hotspot overlays; and
- application metadata and imagery configuration.

This separation lets the browser load the map overview first and fetch detailed
history only when a region is selected.
