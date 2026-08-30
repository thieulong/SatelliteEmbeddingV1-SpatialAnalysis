# Google Earth Engine Source

## Canonical embedding source

`hotspot_characterization_analysis.js` is the complete Bass Coast Earth Engine
workflow that generated the retained embedding-derived products. It loads
`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, applies the project AOI and land mask,
computes Euclidean embedding distance, and exports endpoint, annual, cumulative,
persistence, variance, slope, and timing products.

`hotspot_timeseries_analysis.js` is the earlier lighter time-series workflow.
It is retained for provenance, but it does not include the complete endpoint and
temporal-characterization export set. Use the characterization script as the
canonical Bass Coast baseline when adapting the Earth Engine stage.

## Visual-imagery source

`export_sentinel2_annual.js` creates annual 10 m true-colour Sentinel-2 visual
composites for 2017-2025 using Level-2A surface reflectance, Cloud Score+, and a
median composite. Its exports belong under `data/raw/sentinel2_annual/`.

Before national scaling, preserve the collection/version, AOI, land/water mask,
thresholds, CRS, scale, years, and export names in each run manifest. Do not
treat the Sentinel-2 visual export as a substitute for the embedding workflow.
