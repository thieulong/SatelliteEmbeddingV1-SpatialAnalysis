# Data Sources and Provenance

Source details were checked against official provider documentation on
2026-08-25. Product versions and URLs can change; verify them before a new run.

## Google Satellite Embedding V1

- Earth Engine collection: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- Catalog:
  `https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL`
- Resolution: 10 m.
- Bands: 64 latent dimensions, `A00` through `A63`.
- Temporal support used here: 2017-2024 annual layers.
- Licence/attribution: follow the current catalog entry.

Google documents the vectors as unit length and the space as consistent across
years. The catalog demonstrates dot product/angle for condition-change
similarity. Euclidean distance is mathematically monotonic with dot similarity
for unit vectors, as documented in the methods file.

Important version risk: the official catalog reports that the 2017 layer was
regenerated in dataset version 1.1. The Bass Coast rasters may have been exported
before that change. Before reproducing or scaling, inspect the exported metadata
or GEE asset properties and record `DATASET_VERSION`, `MODEL_VERSION` and
processing version. Do not silently combine old and regenerated annual layers.

## DEA Land Cover

- Product: `ga_ls_landcover_class_cyear_3`
- Version used by the scripts: `2-0-0` / 2.0.0.
- Product page:
  `https://knowledge.dea.ga.gov.au/data/product/dea-land-cover-landsat/`
- Introductory notebook:
  `https://knowledge.dea.ga.gov.au/notebooks/DEA_products/DEA_Land_Cover/`
- Explorer guide:
  `https://knowledge.dea.ga.gov.au/guides/land-cover-explorer/`
- Resolution: 30 m.
- Frequency: annual.
- Spatial scope: Australia.
- Measurements used: `level3` and `level4`.

The scripts construct public continental COG URLs directly. Preserve the
product version in every run because DEA has published breaking grid/version
changes in the past.

## DEA GeoMAD NDVI source

- Product used: `ga_ls8cls9c_gm_cyear_3`.
- Product family: DEA Geometric Median and Median Absolute Deviation (Landsat).
- Product page:
  `https://knowledge.dea.ga.gov.au/data/product/dea-geometric-median-and-median-absolute-deviation-landsat/`
- Introductory notebook:
  `https://knowledge.dea.ga.gov.au/notebooks/DEA_products/DEA_GeoMAD/`
- Resolution: 30 m.
- Annual composite: Landsat 8, and Landsat 8+9 from 2022 onward in the product
  described by DEA.

The project calculates NDVI from annual representative surface reflectance. It
does not use the GeoMAD variability bands as the main NDVI signal.

DEA documentation has carried product issue notices. Check the current quality
and history tabs before national processing and record the exact version/asset
URLs returned by STAC.

## Esri Annual Land Cover

The retained pilot script queries the Esri Sentinel-2 10 m Land Cover
ImageServer. This source was evaluated only on the 900 review points and is not
a mandatory web-app evidence layer.

The class crosswalk and interpretation boundaries are stored in
`analysis/scripts/phase7_esri_dea_crosscheck.py` and the Phase 7 reference
report.

## Esri World Imagery Wayback

- Provider explanation of capture versus publication dates:
  `https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-with-world-imagery-metadata`
- General Wayback archive guide:
  `https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/mapping/use-world-imagery-wayback`

Wayback archive entries represent basemap publication releases. Source-image
capture dates can differ, sometimes by years. The application therefore queries
metadata at the local map coordinate and never assumes release year equals
capture year.

Wayback is visual context only. Terms, availability, endpoints and usage limits
must be checked before production deployment.

## OpenStreetMap and Nominatim

- OpenStreetMap raster tiles provide the default map.
- Nominatim supplies place search and reverse geocoding.

The static prototype makes browser-side requests. Australia-wide/public traffic
must comply with current tile and Nominatim usage policies or use a managed/self-
hosted provider.

## Local Sentinel-2 visual exports

The old workspace contains nine annual true-colour exports for 2017-2025 under
`AusHabitat_Sentinel2_Annual/`, approximately 4.8 GB. They were produced for
visual comparison and are not part of the 30 m analysis.

The export approach used Sentinel-2 Level-2A surface reflectance, Cloud Score+
masking and annual median compositing. These files need a tile service for web
delivery and are not currently the published annual imagery mode.

## Provenance requirements for future runs

Every run manifest should record:

- provider and product name;
- asset/product/dataset/model version;
- access URL or STAC item IDs;
- retrieval date;
- year range;
- AOI geometry checksum;
- CRS, transform, width and height;
- nodata and mask policy;
- resampling/aggregation method;
- thresholds and how they were estimated;
- source-code Git commit; and
- warnings, failed windows and retries.
