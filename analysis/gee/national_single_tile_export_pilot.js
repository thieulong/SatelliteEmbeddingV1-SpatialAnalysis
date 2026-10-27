// One bounded derived raster for storage/throughput measurement only.
// Do not turn this into a national export loop without a separate plan.
var roi = ee.Geometry.Rectangle([134.20, -24.20, 134.38, -24.02], null, false);
var collection = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
var boundary = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var land = ee.ImageCollection('ESA/WorldCover/v200').first()
  .select('Map').neq(80);
function annual(year) {
  return collection.filterDate(year + '-01-01', (year + 1) + '-01-01')
    .filterBounds(roi).mosaic().clip(roi);
}
var start = annual(2017);
var end = annual(2024);
var distance = end.subtract(start).pow(2).reduce(ee.Reducer.sum()).sqrt()
  .rename('embedding_distance_2017_2024').toFloat()
  .updateMask(land).clipToCollection(boundary).unmask(-9999);
print('2017 source tile count', collection.filterDate('2017-01-01', '2018-01-01')
  .filterBounds(roi).size());
print('2024 source tile count', collection.filterDate('2024-01-01', '2025-01-01')
  .filterBounds(roi).size());
print('Pilot area km2', roi.area(1).divide(1e6));

// Already exported on 2026-09-21. Do not run again unless intentional.
Export.image.toDrive({
  image: distance,
  description: 'AusHabitat_pilot_endpoint_central_arid_2017_2024_10m',
  folder: 'AusHabitat_NationalPilot_20260921',
  fileNamePrefix: 'central_arid_endpoint_2017_2024_10m_epsg3577_cog',
  region: roi,
  scale: 10,
  crs: 'EPSG:3577',
  maxPixels: 1e8,
  fileFormat: 'GeoTIFF',
  formatOptions: {cloudOptimized: true, noData: -9999}
});
Map.centerObject(roi, 10);
