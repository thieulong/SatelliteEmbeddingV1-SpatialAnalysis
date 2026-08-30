// =====================================================
// Satellite Embedding V1: Bass Coast lighter full time-series analysis
// Full ready-to-paste script with export functions
// =====================================================

// ---------------------------
// 1. Define study area (AOI)
// ---------------------------
var aoi = ee.Geometry.Rectangle([144.9, -39.2, 146.3, -38.1]);

Map.centerObject(aoi, 9);

// AOI outline
var aoiOutline = ee.Image().byte().paint({
  featureCollection: ee.FeatureCollection([ee.Feature(aoi)]),
  color: 1,
  width: 2
});

Map.addLayer(aoiOutline, {palette: ['red']}, 'AOI outline', true);

// ---------------------------
// 2. Load dataset
// ---------------------------
var dataset = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
print('Dataset size:', dataset.size());

// ---------------------------
// 3. Land mask
// ---------------------------
var worldcover = ee.ImageCollection('ESA/WorldCover/v200')
  .first()
  .select('Map');

// 80 = permanent water
var landMask = worldcover.neq(80).clip(aoi);

Map.addLayer(
  landMask.selfMask(),
  {palette: ['white']},
  'Land mask',
  false
);

// ---------------------------
// 4. Year setup
// ---------------------------
var years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];
var pairStarts = [2017, 2018, 2019, 2020, 2021, 2022, 2023];

// ---------------------------
// 5. Helper functions
// ---------------------------
function getYearCollection(year) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');

  return dataset
    .filterDate(start, end)
    .filterBounds(aoi);
}

function getAnnualMosaic(year) {
  return getYearCollection(year)
    .mosaic()
    .clip(aoi)
    .updateMask(landMask)
    .set('year', year);
}

function computeAnnualChange(startYear) {
  var img1 = getAnnualMosaic(startYear);
  var img2 = getAnnualMosaic(startYear + 1);

  var diff = img2.subtract(img1);

  return diff.pow(2)
    .reduce(ee.Reducer.sum())
    .sqrt()
    .rename('change_score')
    .clip(aoi)
    .updateMask(landMask)
    .set({
      start_year: startYear,
      end_year: startYear + 1,
      label: startYear + '_to_' + (startYear + 1)
    });
}

// ---------------------------
// 6. Diagnostics
// ---------------------------
var tileCountFeatures = years.map(function(year) {
  return ee.Feature(null, {
    year: year,
    tile_count: getYearCollection(year).size()
  });
});

var tileCountTable = ee.FeatureCollection(tileCountFeatures);
print('Tile counts by year over AOI:', tileCountTable);

// Visual check of first and last year
var img2017 = getAnnualMosaic(2017);
var img2024 = getAnnualMosaic(2024);

print('2017 mosaic:', img2017);
print('2024 mosaic:', img2024);
print('2017 band names:', img2017.bandNames());
print('2024 band names:', img2024.bandNames());

Map.addLayer(
  img2017.select(['A00', 'A01', 'A02']),
  {bands: ['A00', 'A01', 'A02'], min: -0.3, max: 0.3},
  'Embedding 2017',
  false
);

Map.addLayer(
  img2024.select(['A00', 'A01', 'A02']),
  {bands: ['A00', 'A01', 'A02'], min: -0.3, max: 0.3},
  'Embedding 2024',
  false
);

// ---------------------------
// 7. Compute annual change images
// ---------------------------
var annualChangeImages = pairStarts.map(function(year) {
  return computeAnnualChange(year);
});

var annualChangeIC = ee.ImageCollection.fromImages(annualChangeImages);
print('Annual change ImageCollection:', annualChangeIC);

// ---------------------------
// 8. Build a lighter annual stats table
// ---------------------------
var annualStatsFeatures = pairStarts.map(function(year) {
  var change = computeAnnualChange(year);

  var stats = change.reduceRegion({
    reducer: ee.Reducer.mean()
      .combine({reducer2: ee.Reducer.max(), sharedInputs: true})
      .combine({reducer2: ee.Reducer.percentile([90, 95]), sharedInputs: true}),
    geometry: aoi,
    scale: 30,
    maxPixels: 1e9
  });

  return ee.Feature(null, {
    start_year: year,
    end_year: year + 1,
    label: year + '_to_' + (year + 1),
    mean: stats.get('change_score_mean'),
    max: stats.get('change_score_max'),
    p90: stats.get('change_score_p90'),
    p95: stats.get('change_score_p95')
  });
});

var annualStatsTable = ee.FeatureCollection(annualStatsFeatures);
print('Annual change stats table:', annualStatsTable);

// ---------------------------
// 9. Derived change products
// ---------------------------
var cumulativeChange = annualChangeIC.sum()
  .rename('cumulative_change')
  .clip(aoi)
  .updateMask(landMask);

var meanAnnualChange = annualChangeIC.mean()
  .rename('mean_annual_change')
  .clip(aoi)
  .updateMask(landMask);

var maxAnnualChange = annualChangeIC.max()
  .rename('max_annual_change')
  .clip(aoi)
  .updateMask(landMask);

// ---------------------------
// 10. Persistence using a fixed threshold
// ---------------------------
var annualHighChangeThreshold = 0.45;
print('Annual high-change threshold:', annualHighChangeThreshold);

var annualHotspotImages = pairStarts.map(function(year) {
  var change = computeAnnualChange(year);

  return change.gt(annualHighChangeThreshold)
    .rename('annual_hotspot')
    .clip(aoi)
    .updateMask(landMask)
    .set({
      start_year: year,
      end_year: year + 1,
      label: year + '_to_' + (year + 1)
    });
});

var annualHotspotIC = ee.ImageCollection.fromImages(annualHotspotImages);
print('Annual hotspot ImageCollection:', annualHotspotIC);

// Count number of years each pixel exceeded the threshold
var persistenceCount = annualHotspotIC.sum()
  .rename('persistence_count')
  .clip(aoi)
  .updateMask(landMask);

// Persistent hotspot definitions
var persistentHotspots2 = persistenceCount.gte(2).selfMask().rename('persistent_hotspots_ge_2');
var persistentHotspots3 = persistenceCount.gte(3).selfMask().rename('persistent_hotspots_ge_3');

// ---------------------------
// 11. Derived stats
// ---------------------------
function printDerivedStats(image, name) {
  var stats = image.reduceRegion({
    reducer: ee.Reducer.min()
      .combine({reducer2: ee.Reducer.max(), sharedInputs: true})
      .combine({reducer2: ee.Reducer.mean(), sharedInputs: true}),
    geometry: aoi,
    scale: 30,
    maxPixels: 1e9
  });

  print(name + ' stats:', stats);
}

printDerivedStats(cumulativeChange, 'Cumulative change');
printDerivedStats(meanAnnualChange, 'Mean annual change');
printDerivedStats(maxAnnualChange, 'Max annual change');
printDerivedStats(persistenceCount, 'Persistence count');

// Persistent hotspot areas
var persistentArea2 = ee.Number(
  persistentHotspots2
    .multiply(ee.Image.pixelArea())
    .rename('area_m2')
    .reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: aoi,
      scale: 30,
      maxPixels: 1e9
    })
    .get('area_m2')
).divide(1e6);

var persistentArea3 = ee.Number(
  persistentHotspots3
    .multiply(ee.Image.pixelArea())
    .rename('area_m2')
    .reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: aoi,
      scale: 30,
      maxPixels: 1e9
    })
    .get('area_m2')
).divide(1e6);

print('Persistent hotspot area (>= 2 years, sq km):', persistentArea2);
print('Persistent hotspot area (>= 3 years, sq km):', persistentArea3);

// ---------------------------
// 12. Display layers
// ---------------------------
var change2023_2024 = computeAnnualChange(2023);
Map.addLayer(
  change2023_2024,
  {
    min: 0,
    max: 0.8,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Annual change 2023-2024',
  false
);

Map.addLayer(
  cumulativeChange,
  {
    min: 0.5,
    max: 2.5,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Cumulative change 2017-2024',
  true
);

Map.addLayer(
  meanAnnualChange,
  {
    min: 0.1,
    max: 0.5,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Mean annual change',
  false
);

Map.addLayer(
  maxAnnualChange,
  {
    min: 0.2,
    max: 1.0,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Max annual change',
  false
);

Map.addLayer(
  persistenceCount,
  {
    min: 0,
    max: 7,
    palette: ['black', 'navy', 'blue', 'cyan', 'yellow', 'orange', 'red', 'magenta']
  },
  'Persistence count',
  true
);

Map.addLayer(
  persistentHotspots2,
  {palette: ['magenta']},
  'Persistent hotspots (>= 2 years)',
  true
);

Map.addLayer(
  persistentHotspots3,
  {palette: ['yellow']},
  'Persistent hotspots (>= 3 years)',
  false
);

// ---------------------------
// 13. Export functions
// ---------------------------
// Exports go to Google Drive.
// After running this script, open the Tasks tab and click Run for each task.

// Folder name in Google Drive
var exportFolder = 'GEE_BassCoast_SatelliteEmbedding';

// Common export settings
var exportRegion = aoi;
var exportScale = 10;
var exportMaxPixels = 1e13;

// 13.1 Export annual stats table as CSV
Export.table.toDrive({
  collection: annualStatsTable,
  description: 'BassCoast_annual_change_stats_csv',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_annual_change_stats',
  fileFormat: 'CSV'
});

// 13.2 Export tile counts table as CSV
Export.table.toDrive({
  collection: tileCountTable,
  description: 'BassCoast_tile_counts_csv',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_tile_counts',
  fileFormat: 'CSV'
});

// 13.3 Export cumulative change raster
Export.image.toDrive({
  image: cumulativeChange.toFloat(),
  description: 'BassCoast_cumulative_change_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_cumulative_change',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.4 Export mean annual change raster
Export.image.toDrive({
  image: meanAnnualChange.toFloat(),
  description: 'BassCoast_mean_annual_change_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_mean_annual_change',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.5 Export max annual change raster
Export.image.toDrive({
  image: maxAnnualChange.toFloat(),
  description: 'BassCoast_max_annual_change_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_max_annual_change',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.6 Export persistence count raster
Export.image.toDrive({
  image: persistenceCount.toInt16(),
  description: 'BassCoast_persistence_count_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_persistence_count',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.7 Export persistent hotspots >= 2 years
Export.image.toDrive({
  image: persistentHotspots2.unmask(0).toByte(),
  description: 'BassCoast_persistent_hotspots_ge2_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_persistent_hotspots_ge2',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.8 Export persistent hotspots >= 3 years
Export.image.toDrive({
  image: persistentHotspots3.unmask(0).toByte(),
  description: 'BassCoast_persistent_hotspots_ge3_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_persistent_hotspots_ge3',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 13.9 Export annual change rasters for each year pair
pairStarts.forEach(function(year) {
  var annualChange = computeAnnualChange(year).toFloat();

  Export.image.toDrive({
    image: annualChange,
    description: 'BassCoast_annual_change_' + year + '_' + (year + 1) + '_tif',
    folder: exportFolder,
    fileNamePrefix: 'basscoast_annual_change_' + year + '_' + (year + 1),
    region: exportRegion,
    scale: exportScale,
    maxPixels: exportMaxPixels,
    fileFormat: 'GeoTIFF'
  });
});

// 13.10 Export annual hotspot rasters for each year pair
pairStarts.forEach(function(year) {
  var annualHotspot = computeAnnualChange(year)
    .gt(annualHighChangeThreshold)
    .unmask(0)
    .toByte()
    .rename('annual_hotspot');

  Export.image.toDrive({
    image: annualHotspot,
    description: 'BassCoast_annual_hotspot_' + year + '_' + (year + 1) + '_tif',
    folder: exportFolder,
    fileNamePrefix: 'basscoast_annual_hotspot_' + year + '_' + (year + 1),
    region: exportRegion,
    scale: exportScale,
    maxPixels: exportMaxPixels,
    fileFormat: 'GeoTIFF'
  });
});

print('Export tasks have been created. Open the Tasks tab and click Run for each export.');