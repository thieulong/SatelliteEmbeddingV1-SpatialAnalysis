# Canonical Pipeline

Historical output filenames retain their original phase identifiers. The
current source and execution model use the eight stages below.

## Signal definition

For pixel location `p` and year `t`, let `e(p,t)` be its 64-dimensional annual
satellite embedding. The implemented annual change magnitude is:

```text
d(p,t) = sqrt(sum((e_i(p,t+1) - e_i(p,t))^2 for i = 1..64))
```

Endpoint change is the same calculation between 2017 and 2024. Because the
official embeddings are unit-length vectors, Euclidean distance is a monotonic
transformation of dot-product similarity:

```text
||u-v|| = sqrt(2 - 2(u dot v))
```

The existing work uses Euclidean distance consistently. Any national rerun
must record the embedding collection/version and should compare results with
the official dot-product/angle recommendation before changing the metric.

## Derived temporal metrics

For the seven annual distances `d_1 ... d_7`:

- **Cumulative change:** `sum(d_t)`.
- **Mean annual change:** `mean(d_t)`.
- **Maximum annual change:** `max(d_t)`.
- **Persistence count:** number of intervals where `d_t > 0.45`, matching the
  strict comparison implemented in the Earth Engine source.
- **Variance:** mean squared deviation from the seven-value mean.
- **Slope:** ordinary least-squares slope of annual distance against interval
  index `1..7`.
- **First hot-spot year:** first interval exceeding the annual threshold.
- **Maximum-change year:** interval containing the largest distance.

The fixed annual hot-spot rule is `d_t > 0.45`. The practical difference from
`d_t >= 0.45` is negligible for floating-point raster values, but the strict
operator records the implemented method. The endpoint hot-spot threshold is the
empirical endpoint 95th percentile. The endpoint and variance/slope percentile
thresholds used for sampling are recorded in
`data/processed/sampling/tables/phase2_thresholds.csv` and compactly in
`analysis/reference_outputs/phase2/phase2_thresholds.csv`.

## Stage 1: inspect rasters

Source: `analysis/notebooks/BassCoast_Phase1_Raster_Inspection.ipynb`

- Reads metadata without retaining full raster arrays.
- Checks CRS, affine transform, width, height, shape, and nodata.
- Scans 1024 x 1024 windows for exact count/min/max/mean/standard deviation.
- Uses documented strides for approximate medians and histograms.
- Uses downsampled arrays only for plotting.

Output: `data/processed/raster_qa/`.

Alignment means the raster grids coincide. It does not mean that land-cover
semantics are consistent between years.

## Stage 2: sample behavioural candidates

Source: `analysis/notebooks/BassCoast_Phase2_Pixel_Sampling.ipynb`

The raster stack is scanned window by window. Each valid pixel can satisfy one
or more rule-based categories:

1. endpoint hot spot;
2. persistence at least two intervals;
3. persistence at least three intervals;
4. top 5% annual-change variance;
5. top 5% positive slope;
6. bottom 5% negative slope;
7. high endpoint change with persistence no more than one;
8. endpoint below p95 with variance at or above p95; or
9. stable control: low endpoint change, zero persistence, low variance, slope
   near zero.

A fixed-seed reservoir-style sampler retains at most 10,000 unique locations
per category. The final table contains 89,707 rows because some categories had
fewer eligible unique cells after duplicate avoidance. A 900-point review set
contains up to 100 per category, combining representative, high-signal, and
random points.

Output: `data/processed/sampling/`.

## Stage 3: enrich sampled points with DEA Land Cover

Source: `analysis/pipeline/stage03_dea_enrichment.py`

For each point and year 2017-2024:

1. transform longitude/latitude to DEA's Australian Albers grid;
2. read the annual DEA Level 3 and Level 4 class at the coordinate;
3. if the exact read is masked, try a 3 x 3 neighbourhood majority;
4. if still missing, try a 5 x 5 majority;
5. record the source used and any warning;
6. construct annual class sequences and transition/timing summaries.

The full retained run used all 89,707 points and produced 717,656 point-year
rows. Run a small network smoke test before a full rerun:

```bash
python analysis/pipeline/stage03_dea_enrichment.py \
  --input data/processed/sampling/basscoast_phase2b_review_points.csv \
  --output-dir /tmp/aushabitat_stage03_smoke \
  --max-points 10 --chunk-size 10 --force
```

Output: `data/processed/dea_sample/`.

## Stage 4: summarize DEA wall-to-wall

Source: `analysis/pipeline/stage04_dea_wall_to_wall.py`

This stage scans the complete valid embedding surface in windows, aligns annual
DEA COGs to the embedding grid, applies the behavioural rules, and aggregates
counts and transitions. It does not generate a 191-million-row CSV.

```bash
python analysis/pipeline/stage04_dea_wall_to_wall.py --self-test
```

Output: `data/processed/dea_wall_to_wall/`.

## Stage 5: calibrate annual NDVI evidence

Source: `analysis/pipeline/stage05_ndvi_pilot.py`

The 900 review points are sampled from annual DEA GeoMAD red and near-infrared
bands. NDVI is calculated as:

```text
NDVI = (NIR - Red) / (NIR + Red)
```

This stage estimates association with embedding change and records the
substantial-NDVI-change threshold used by later evidence summaries. It provides
signed vegetation direction; it does not produce land-use labels.

Output: `data/processed/ndvi_pilot/`.

## Stage 6: build the common map grid

Source: `analysis/pipeline/stage06_map_grid.py`

- Aggregates/resamples aligned 10 m embedding metrics to an approximately 30 m
  common-support grid using a target-grid factor of three. Masks, nodata,
  raster boundaries, and alignment mean a target cell does not necessarily
  summarize exactly nine valid source cells.
- Creates change-state cells from endpoint, annual, persistence, variance, and
  slope evidence.
- Applies minimum connected-patch sizes.
- Groups edge-touching cells with the same interaction-state mask into regions.
- Exports region inventory, compressed geometry, map rasters, and sensitivity
  summaries.

Output: `data/processed/map_grid/`.

The 30 m grid is a common analytical support for integration. It does not
replace or improve the native 10 m embedding measurements.

## Stage 7: build complete region context

Source: `analysis/pipeline/stage07_region_context.py`

- Aligns annual DEA Level 3, Level 4, NDVI, and clear-observation counts to the
  30 m map grid.
- Produces complete annual rasters for 2017-2024.
- Aggregates dominant land-cover classes, alternatives, NDVI, embedding change,
  and strong-change shares for every interaction region and year.
- Writes 13,784 region summaries and 110,272 region-year records.

```bash
python analysis/pipeline/stage07_region_context.py --self-test
```

Output: `data/processed/region_context/`.

## Stage 8: package the browser application

Source: `analysis/pipeline/stage08_package_web_data.py`

This converts Stage 6 and Stage 7 products into compact GeoJSON, raster PNGs,
metadata, and fourteen detail JSON shards under `public/data/`.

```bash
python analysis/pipeline/stage08_package_web_data.py
```

The generated `public/data/` package is committed because GitHub Pages serves
it directly. Validate the app before committing regenerated assets.

## Memory and scaling rules

- Never flatten the complete raster grid into a DataFrame or CSV.
- Use windows, local COG reads, streaming aggregates, and checkpoints.
- Keep exact statistics separate from sampled approximations.
- Partition national work by stable tiles and years.
- Write cloud-optimized rasters and partitioned columnar tables for future AWS
  processing rather than national JSON/CSV products.
