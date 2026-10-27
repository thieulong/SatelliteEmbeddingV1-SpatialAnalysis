// Resource-bounded recovery for the failed SE and TAS sample exports.
//
// The original random points, seeds, frame geometries, grid, years and metrics
// are preserved. Spatial parts only reduce the upstream mosaic footprint.
// This script creates unsubmitted tasks. Run NW_CHECK2 and one failed-stratum
// diagnostic first; compare NW_CHECK2 with the original NW output before the
// remaining parts. Keep at most two tasks active.

var RUN = '20260930';
var RECOVERY = '20261004';
var FOLDER = 'AusHabitat_Pilot_' + RUN + '_Recovery_' + RECOVERY;
var DATA = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
var BOUNDARY = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var WC = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map');
var YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];
var CRS = 'EPSG:3577';
var TRANSFORM = [10, 0, 0, 0, -10, 0];
var PROJECTION = ee.Projection(CRS, TRANSFORM);
var N = 200;

var FRAMES = {
  NW: {bounds: [112, -20, 134, -9], seed: 20260930},
  SE: {bounds: [134, -40, 154, -30], seed: 20260935},
  TAS: {bounds: [143, -44, 149, -40], seed: 20260936}
};

// NW_CHECK2 tests the revised extraction method against an already completed
// sample. The SE/TAS parts are mutually exclusive half-open processing cells.
var PARTS = [
  ['NW_CHECK2', 'NW', 123, -20, 125.75, -14.5],
  ['SE_00', 'SE', 134, -40, 139, -35],
  ['SE_01', 'SE', 139, -40, 144, -35],
  ['SE_02', 'SE', 144, -40, 149, -35],
  ['SE_03', 'SE', 149, -40, 154, -35],
  ['SE_04', 'SE', 134, -35, 139, -30],
  ['SE_05', 'SE', 139, -35, 144, -30],
  ['SE_06', 'SE', 144, -35, 149, -30],
  ['SE_07', 'SE', 149, -35, 154, -30],
  ['TAS_00', 'TAS', 143, -44, 146, -42],
  ['TAS_01', 'TAS', 146, -44, 149, -42],
  ['TAS_02', 'TAS', 143, -42, 146, -40],
  ['TAS_03', 'TAS', 146, -42, 149, -40]
];

var DIST_NAMES = [
  'endpoint', 'd2017', 'd2018', 'd2019',
  'd2020', 'd2021', 'd2022', 'd2023'
];

function source(year, roi) {
  return DATA.filterDate(year + '-01-01', (year + 1) + '-01-01')
    .filterBounds(roi).sort('system:index');
}

function stack(roi) {
  var annual = YEARS.map(function(year) {
    return source(year, roi).mosaic().select('A.*');
  });
  var valid = annual.map(function(image, index) {
    return image.mask().reduce(ee.Reducer.min()).unmask(0, false)
      .rename('v' + YEARS[index]);
  });
  function distance(left, right, name) {
    return right.subtract(left).pow(2).reduce(ee.Reducer.sum()).sqrt()
      .rename(name).unmask(-9999, false);
  }
  var distances = [distance(annual[0], annual[7], 'endpoint')];
  for (var index = 0; index < 7; index++) {
    distances.push(distance(annual[index], annual[index + 1],
      'd' + YEARS[index]));
  }
  var diagnostics = [
    annual[0].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2017'),
    annual[7].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2024'),
    annual[0].multiply(annual[7]).reduce(ee.Reducer.sum())
      .rename('dot_endpoint')
  ];
  return ee.Image.cat(distances.concat(valid))
    .addBands(ee.Image.cat(diagnostics).unmask(-9999, false))
    .addBands(WC.unmask(0, false).rename('worldcover2021'))
    .addBands(ee.Image.pixelLonLat());
}

function originalPoints(stratum) {
  var spec = FRAMES[stratum];
  var frame = BOUNDARY.geometry().intersection(
    ee.Geometry.Rectangle(spec.bounds, null, false), 100);
  var area = frame.area(100).divide(1e6);
  return ee.FeatureCollection.randomPoints(frame, N, spec.seed, 100)
    .map(function(feature) {
      var coordinates = feature.geometry().coordinates();
      return feature.set({
        stratum: stratum,
        point_id: ee.String(stratum).cat('_').cat(ee.String(feature.id())),
        frame_km2: area,
        n_requested: N,
        sample_weight_km2: area.divide(N),
        seed: spec.seed,
        original_lon: coordinates.get(0),
        original_lat: coordinates.get(1),
        recovery_method: 'original_frame_srs_spatial_processing_shard'
      });
    });
}

function inPart(points, part) {
  return points.filter(ee.Filter.and(
    ee.Filter.gte('original_lon', part[2]),
    ee.Filter.lt('original_lon', part[4]),
    ee.Filter.gte('original_lat', part[3]),
    ee.Filter.lt('original_lat', part[5])
  ));
}

var selectors = [
  'stratum', 'point_id', 'frame_km2', 'n_requested', 'sample_weight_km2',
  'seed', 'original_lon', 'original_lat', 'recovery_method', 'recovery_part'
].concat(DIST_NAMES)
  .concat(['v2017', 'v2018', 'v2019', 'v2020', 'v2021', 'v2022',
    'v2023', 'v2024', 'norm2017', 'norm2024', 'dot_endpoint',
    'worldcover2021', 'longitude', 'latitude']);

PARTS.forEach(function(part) {
  var cell = ee.Geometry.Rectangle(
    [part[2], part[3], part[4], part[5]], null, false);
  var points = inPart(originalPoints(part[1]), part).map(function(feature) {
    return feature.set('recovery_part', part[0]);
  });
  // Earth Engine recommends reduceRegions for point collections. Supplying a
  // simple processing cell to stack() prevents a whole-stratum mosaic.
  var samples = stack(cell).reduceRegions({
    collection: points,
    reducer: ee.Reducer.first(),
    crs: PROJECTION,
    tileScale: 4
  });
  Export.table.toDrive({
    collection: samples,
    description: 'AU_' + RUN + '_recovery_' + part[0],
    folder: FOLDER,
    fileNamePrefix: 'recovery_' + part[0],
    fileFormat: 'CSV',
    selectors: selectors
  });
  print(part[0] + ' planned point count', points.size());
});

print('Run NW_CHECK2 and one failed-stratum diagnostic first.');
print('Do not rerun the original failed whole-stratum tasks.');
print('After recovery, SE parts must total 200 rows and TAS parts 200 rows.');
