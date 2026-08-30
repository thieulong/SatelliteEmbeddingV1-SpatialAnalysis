// 1. Define AOI
var aoi = ee.Geometry.Rectangle([144.9, -39.2, 146.3, -38.1]);

Map.centerObject(aoi, 9);

var aoiOutline = ee.Image().byte().paint({
  featureCollection: ee.FeatureCollection([ee.Feature(aoi)]),
  color: 1,
  width: 2
});

Map.addLayer(aoiOutline, {palette: ['red']}, 'AOI outline', true);

// 2. Load dataset
var dataset = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
print('Dataset size:', dataset.size());


// 3. Land mask
var worldcover = ee.ImageCollection('ESA/WorldCover/v200')
  .first()
  .select('Map');

var landMask = worldcover.neq(80).clip(aoi);

Map.addLayer(
  landMask.selfMask(),
  {palette: ['white']},
  'Land mask',
  false
);

// 4. Year setup
var years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];
var pairStarts = [2017, 2018, 2019, 2020, 2021, 2022, 2023];

// 5. Helper functions
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

function computeEmbeddingDistance(img1, img2, bandName) {
  var diff = img2.subtract(img1);

  return diff.pow(2)
    .reduce(ee.Reducer.sum())
    .sqrt()
    .rename(bandName)
    .clip(aoi)
    .updateMask(landMask);
}

function computeAnnualChange(startYear) {
  var img1 = getAnnualMosaic(startYear);
  var img2 = getAnnualMosaic(startYear + 1);

  return computeEmbeddingDistance(img1, img2, 'change_score')
    .set({
      start_year: startYear,
      end_year: startYear + 1,
      label: startYear + '_to_' + (startYear + 1)
    });
}

// 6. Diagnostics
var tileCountFeatures = years.map(function(year) {
  return ee.Feature(null, {
    year: year,
    tile_count: getYearCollection(year).size()
  });
});

var tileCountTable = ee.FeatureCollection(tileCountFeatures);
print('Tile counts by year over AOI:', tileCountTable);

// 7. Endpoint analysis: 2017 vs 2024
var endpointChange = computeEmbeddingDistance(
  getAnnualMosaic(2017),
  getAnnualMosaic(2024),
  'endpoint_change'
);

print('Endpoint change image:', endpointChange);

// Current p95 from previous successful run
var endpointThreshold = 0.43352768060772184;
print('Endpoint threshold used (current p95):', endpointThreshold);

var endpointHotspots = endpointChange
  .gt(endpointThreshold)
  .selfMask()
  .rename('endpoint_hotspots');

var endpointHotspotArea = ee.Number(
  endpointHotspots
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

print('Endpoint hotspot area (sq km):', endpointHotspotArea);

var endpointStats = endpointChange.reduceRegion({
  reducer: ee.Reducer.min()
    .combine({reducer2: ee.Reducer.max(), sharedInputs: true})
    .combine({reducer2: ee.Reducer.mean(), sharedInputs: true})
    .combine({reducer2: ee.Reducer.percentile([90, 95, 99]), sharedInputs: true}),
  geometry: aoi,
  scale: 30,
  maxPixels: 1e9
});

print('Endpoint change stats:', endpointStats);

// 8. Annual time-series analysis
var annualChangeImages = pairStarts.map(function(year) {
  return computeAnnualChange(year);
});

var annualChangeIC = ee.ImageCollection.fromImages(annualChangeImages);
print('Annual change ImageCollection:', annualChangeIC);

// 9. Annual stats table
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
print('Annual stats table:', annualStatsTable);

// 10. Derived annual products
var cumulativeChange = annualChangeIC
  .sum()
  .rename('cumulative_change')
  .clip(aoi)
  .updateMask(landMask);

var meanAnnualChange = annualChangeIC
  .mean()
  .rename('mean_annual_change')
  .clip(aoi)
  .updateMask(landMask);

var maxAnnualChange = annualChangeIC
  .max()
  .rename('max_annual_change')
  .clip(aoi)
  .updateMask(landMask);

var varianceAnnualChange = annualChangeIC
  .reduce(ee.Reducer.variance())
  .rename('variance_annual_change')
  .clip(aoi)
  .updateMask(landMask);

// 11. Slope of annual change
// We create a 2-band image collection:
// x = time step index, y = annual change score.
// Then linearFit estimates slope per pixel.
var annualChangeWithTime = ee.ImageCollection.fromImages(
  pairStarts.map(function(year) {
    var t = year - 2017 + 1;

    var timeBand = ee.Image.constant(t)
      .rename('time')
      .toFloat()
      .clip(aoi)
      .updateMask(landMask);

    var changeBand = computeAnnualChange(year)
      .rename('change')
      .toFloat();

    return timeBand
      .addBands(changeBand)
      .set({
        start_year: year,
        end_year: year + 1,
        time_index: t,
        label: year + '_to_' + (year + 1)
      });
  })
);

var slopeFit = annualChangeWithTime
  .select(['time', 'change'])
  .reduce(ee.Reducer.linearFit());

var slopeAnnualChange = slopeFit
  .select('scale')
  .rename('slope_annual_change')
  .clip(aoi)
  .updateMask(landMask);

print('Slope annual change image:', slopeAnnualChange);

// 12. Persistence analysis
var annualThreshold = 0.45;
print('Annual threshold:', annualThreshold);

var annualHotspotImages = pairStarts.map(function(year) {
  var change = computeAnnualChange(year);

  return change
    .gt(annualThreshold)
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

var persistenceCount = annualHotspotIC
  .sum()
  .rename('persistence_count')
  .clip(aoi)
  .updateMask(landMask);

var persistentHotspots2 = persistenceCount
  .gte(2)
  .selfMask()
  .rename('persistent_hotspots_ge_2');

var persistentHotspots3 = persistenceCount
  .gte(3)
  .selfMask()
  .rename('persistent_hotspots_ge_3');

// 13. First hotspot year
var firstHotspotYear = ee.Image(0).clip(aoi).updateMask(landMask);

pairStarts.forEach(function(year) {
  var annualHotspot = computeAnnualChange(year).gt(annualThreshold);

  firstHotspotYear = firstHotspotYear.where(
    firstHotspotYear.eq(0).and(annualHotspot),
    year + 1
  );
});

firstHotspotYear = firstHotspotYear
  .updateMask(firstHotspotYear.neq(0))
  .rename('first_hotspot_year');

// 14. Max change year
var maxChangeYear = ee.Image(0).clip(aoi).updateMask(landMask);
var currentMax = ee.Image(0).clip(aoi).updateMask(landMask);

pairStarts.forEach(function(year) {
  var annualChange = computeAnnualChange(year);

  maxChangeYear = maxChangeYear.where(
    annualChange.gt(currentMax),
    year + 1
  );

  currentMax = currentMax.max(annualChange);
});

maxChangeYear = maxChangeYear
  .updateMask(maxChangeYear.neq(0))
  .rename('max_change_year');

// 15. Area summaries
function areaSqKm(maskImage, name) {
  var area = ee.Number(
    maskImage
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

  print(name + ' area (sq km):', area);
}

areaSqKm(persistentHotspots2, 'Persistent hotspots >=2 years');
areaSqKm(persistentHotspots3, 'Persistent hotspots >=3 years');

// 16. Summary statistics
function printStats(image, name) {
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

printStats(cumulativeChange, 'Cumulative change');
printStats(meanAnnualChange, 'Mean annual change');
printStats(maxAnnualChange, 'Max annual change');
printStats(varianceAnnualChange, 'Variance annual change');
printStats(slopeAnnualChange, 'Slope annual change');
printStats(persistenceCount, 'Persistence count');

// 17. Display layers
Map.addLayer(
  endpointChange,
  {
    min: 0.15,
    max: 0.70,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Endpoint change 2017-2024',
  true
);

Map.addLayer(
  endpointHotspots,
  {palette: ['magenta']},
  'Endpoint hotspots',
  false
);

Map.addLayer(
  cumulativeChange,
  {
    min: 0.5,
    max: 2.5,
    palette: ['black', 'blue', 'cyan', 'yellow', 'orange', 'red']
  },
  'Cumulative change',
  false
);

Map.addLayer(
  persistenceCount.selfMask(),
  {
    min: 1,
    max: 7,
    palette: ['navy', 'blue', 'cyan', 'yellow', 'orange', 'red', 'magenta']
  },
  'Persistence count',
  false
);

Map.addLayer(
  persistentHotspots2,
  {palette: ['yellow']},
  'Persistent hotspots >=2 years',
  false
);

Map.addLayer(
  persistentHotspots3,
  {palette: ['red']},
  'Persistent hotspots >=3 years',
  false
);

Map.addLayer(
  varianceAnnualChange,
  {
    min: 0,
    max: 0.1,
    palette: ['black', 'blue', 'cyan', 'yellow', 'red']
  },
  'Variance annual change',
  false
);

Map.addLayer(
  slopeAnnualChange,
  {
    min: -0.08,
    max: 0.08,
    palette: ['blue', 'white', 'red']
  },
  'Slope annual change',
  false
);

Map.addLayer(
  firstHotspotYear,
  {
    min: 2018,
    max: 2024,
    palette: ['blue', 'cyan', 'green', 'yellow', 'orange', 'red', 'magenta']
  },
  'First hotspot year',
  false
);

Map.addLayer(
  maxChangeYear,
  {
    min: 2018,
    max: 2024,
    palette: ['blue', 'cyan', 'green', 'yellow', 'orange', 'red', 'magenta']
  },
  'Max change year',
  false
);

print('Temporal characterization workflow with slope complete.');

// 18. Export functions for Python analysis

var exportFolder = 'GEE_BassCoast_SatelliteEmbedding';

var exportRegion = aoi;
var exportScale = 10;
var exportMaxPixels = 1e13;

// 18.1 Export summary tables
Export.table.toDrive({
  collection: annualStatsTable,
  description: 'BassCoast_annual_change_stats_csv',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_annual_change_stats',
  fileFormat: 'CSV'
});

Export.table.toDrive({
  collection: tileCountTable,
  description: 'BassCoast_tile_counts_csv',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_tile_counts',
  fileFormat: 'CSV'
});

// 18.2 Export endpoint products
Export.image.toDrive({
  image: endpointChange.toFloat(),
  description: 'BassCoast_endpoint_change_2017_2024_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_endpoint_change_2017_2024',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: endpointHotspots.unmask(0).toByte(),
  description: 'BassCoast_endpoint_hotspots_2017_2024_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_endpoint_hotspots_2017_2024',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 18.3 Export existing annual summary products
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

// ---------------------------
// 18.4 Export new temporal behaviour products
// ---------------------------
Export.image.toDrive({
  image: varianceAnnualChange.toFloat(),
  description: 'BassCoast_variance_annual_change_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_variance_annual_change',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: slopeAnnualChange.toFloat(),
  description: 'BassCoast_slope_annual_change_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_slope_annual_change',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: firstHotspotYear.unmask(0).toInt16(),
  description: 'BassCoast_first_hotspot_year_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_first_hotspot_year',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: maxChangeYear.unmask(0).toInt16(),
  description: 'BassCoast_max_change_year_tif',
  folder: exportFolder,
  fileNamePrefix: 'basscoast_max_change_year',
  region: exportRegion,
  scale: exportScale,
  maxPixels: exportMaxPixels,
  fileFormat: 'GeoTIFF'
});

// 18.5 Export annual change rasters
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

// 18.6 Export annual hotspot rasters
pairStarts.forEach(function(year) {
  var annualHotspot = computeAnnualChange(year)
    .gt(annualThreshold)
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