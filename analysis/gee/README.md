# Google Earth Engine Source

## Retained source

`export_sentinel2_annual.js` creates annual 10 m true-colour Sentinel-2 visual
composites for 2017-2025 using Level-2A surface reflectance, Cloud Score+, and a
median composite. Its exports belong under `data/raw/sentinel2_annual/`.

## Missing source required before scaling

The Earth Engine source that generated the 64-dimensional embedding-change
rasters was not available as a standalone file during consolidation. Export it
from the owner's Earth Engine account and save it as:

```text
analysis/gee/basscoast_embedding_change.js
```

The file must record the collection/version, AOI, land/water mask, embedding
distance calculation, annual and endpoint thresholds, temporal metrics, CRS,
scale, years, and every export name. Do not treat the Sentinel-2 visual export
as a substitute.
