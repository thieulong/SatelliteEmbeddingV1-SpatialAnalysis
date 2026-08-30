# Sources and Provenance

## Google Satellite Embedding V1 Annual

- Earth Engine collection: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- Official catalogue:
  https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL
- Native pixel size: 10 m.
- Annual vector: 64 dimensions, normalized to unit length.
- Project period: 2017-2024.

Important version risk: the official catalogue notes that the 2017 layer was
regenerated in dataset version 1.1. A national rerun must record collection
version and should not mix exports from different versions without a documented
comparison.

The catalogue primarily demonstrates dot product/angle for similarity. The
project implemented Euclidean distance. For unit vectors the two rankings are
monotonically related, but the exact metric remains a method decision that must
be versioned.

## DEA Land Cover

- Product: `ga_ls_landcover_class_cyear_3`
- Retained version in code: `2-0-0`.
- Official documentation:
  https://knowledge.dea.ga.gov.au/data/product/dea-land-cover-landsat/
- Delivery: annual continental Cloud-Optimized GeoTIFFs.
- Coordinate system: Australian Albers (`EPSG:3577`).
- Approximate support: 30 m.

The project reads Level 3 broad classes and Level 4 detailed classes at each
year. It uses direct COG access, not website scraping.

## DEA GeoMAD / annual NDVI

- Product used: `ga_ls8cls9c_gm_cyear_3`.
- Official documentation:
  https://knowledge.dea.ga.gov.au/data/product/dea-geometric-median-and-median-absolute-deviation-landsat/
- Access: DEA STAC plus public COG assets.
- Bands used: `nbart_red`, `nbart_nir`, and clear-observation count.
- Derived value: `(NIR - Red) / (NIR + Red)`.
- Approximate support: 30 m.

GeoMAD annual composites combine available Landsat observations; they are not a
single-date image. NDVI is continuous vegetation greenness evidence, not a
land-cover class or direct ecological-condition score.

## Esri World Imagery and Wayback

- Current reference basemap: Esri World Imagery.
- Annual visual context: Esri World Imagery Wayback.
- Wayback metadata overview:
  https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-with-world-imagery-metadata

The application queries local metadata for several candidate releases and
shows the capture closest to the selected year only when it is within the
configured tolerance. Availability, capture date, and source resolution vary
by place and release.

Wayback imagery is display context and is not used in scientific calculations.

## OpenStreetMap

OpenStreetMap provides the default labelled basemap. Attribution remains
visible in the application. It does not contribute analytical evidence.

## Optional Sentinel-2 visual exports

`analysis/gee/export_sentinel2_annual.js` generates annual 2017-2025 visual
composites from Sentinel-2 Level-2A surface reflectance using Cloud Score+ and a
median composite. Local GeoTIFFs live in `data/raw/sentinel2_annual/`.

These rasters are optional visual experiments. They are not current
application basemaps and do not replace the embedding-processing workflow.

## Original project-owned sources

The following project-owned assets require version/provenance protection:

- canonical Earth Engine embedding-change script
  (`analysis/gee/hotspot_characterization_analysis.js`);
- earlier lighter Earth Engine time-series script
  (`analysis/gee/hotspot_timeseries_analysis.js`);
- exported 10 m embedding metric rasters;
- thresholds and behavioural rules;
- processed 30 m map/context products;
- browser-ready application package; and
- presentation/report deliverables.

Every future run should record the Git commit, data-product versions, source
URLs, AOI, years, thresholds, CRS, grid transform, runtime environment, and
output checksums.
