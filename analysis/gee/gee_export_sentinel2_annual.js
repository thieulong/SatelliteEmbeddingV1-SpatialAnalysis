// AusHabitat annual true-colour Sentinel-2 exports for Bass Coast.
// Run this script in the Google Earth Engine Code Editor.

var START_YEAR = 2017;
var END_YEAR = 2025;
var CLEAR_THRESHOLD = 0.60;
var EXPORT_FOLDER = 'AusHabitat_Sentinel2_Annual';

var aoi = ee.Geometry.Rectangle([
  144.89996212751865,
  -39.20211967286227,
  146.30007632934735,
  -38.09997665077603
], null, false);

var sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED');
var cloudScore = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');

function annualComposite(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');
  var collection = sentinel2
    .filterBounds(aoi)
    .filterDate(start, end)
    .linkCollection(cloudScore, ['cs_cdf'])
    .map(function (image) {
      return image.updateMask(image.select('cs_cdf').gte(CLEAR_THRESHOLD));
    });

  print('Sentinel-2 scenes for ' + year, collection.size());

  return collection
    .select(['B4', 'B3', 'B2'])
    .median()
    .clip(aoi)
    .visualize({
      bands: ['B4', 'B3', 'B2'],
      min: 0,
      max: 3000,
      gamma: 1.1
    })
    .set({
      year: year,
      source: 'COPERNICUS/S2_SR_HARMONIZED',
      cloud_mask: 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED',
      clear_threshold: CLEAR_THRESHOLD
    });
}

for (var year = START_YEAR; year <= END_YEAR; year++) {
  var image = annualComposite(year);
  Map.addLayer(image, {}, 'Sentinel-2 annual ' + year, year === END_YEAR);

  Export.image.toDrive({
    image: image,
    description: 'bass_coast_sentinel2_annual_' + year,
    folder: EXPORT_FOLDER,
    fileNamePrefix: 'bass_coast_sentinel2_annual_' + year,
    region: aoi,
    scale: 10,
    crs: 'EPSG:3857',
    maxPixels: 1e13,
    fileFormat: 'GeoTIFF',
    formatOptions: { cloudOptimized: true }
  });
}

Map.centerObject(aoi, 9);
