// Staged fine-shard recovery for the incomplete SE and TAS pilot samples.
//
// The 30 non-empty cells below contain the 304 points that remain after the
// verified SE_03, TAS_03, SE_FINE_04_01 and TAS_FINE_01_01 outputs. Cells are
// computational partitions only; the original frames, seeds, sample weights,
// identifiers, grid, years and measurements are unchanged.
//
// Safety gate: only cells named in BATCH create tasks. Keep BATCH at no more
// than two entries, run the script, review the printed counts, and submit at
// most those two tasks. Validate their CSVs before changing BATCH.

var RUN = '20260930';
var RECOVERY = '20261005';
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
  SE: {bounds: [134, -40, 154, -30], seed: 20260935},
  TAS: {bounds: [143, -44, 149, -40], seed: 20260936}
};

// Current batch uses the largest remaining point count in each grid.
// These create task definitions only; task submission remains manual.
var BATCH = ['SE_FINE_04_02', 'TAS_FINE_03_01'];

// [name, stratum, west, south, east, north, verified planned point count]
var PARTS = [
  ['SE_FINE_02_00', 'SE', 139, -40, 141.5, -37.5, 2],
  ['SE_FINE_03_00', 'SE', 141.5, -40, 144, -37.5, 5],
  ['SE_FINE_04_00', 'SE', 144, -40, 146.5, -37.5, 7],
  ['SE_FINE_05_00', 'SE', 146.5, -40, 149, -37.5, 4],
  ['SE_FINE_01_01', 'SE', 136.5, -37.5, 139, -35, 1],
  ['SE_FINE_02_01', 'SE', 139, -37.5, 141.5, -35, 6],
  ['SE_FINE_03_01', 'SE', 141.5, -37.5, 144, -35, 8],
  ['SE_FINE_05_01', 'SE', 146.5, -37.5, 149, -35, 8],
  ['SE_FINE_00_02', 'SE', 134, -35, 136.5, -32.5, 6],
  ['SE_FINE_01_02', 'SE', 136.5, -35, 139, -32.5, 9],
  ['SE_FINE_02_02', 'SE', 139, -35, 141.5, -32.5, 10],
  ['SE_FINE_03_02', 'SE', 141.5, -35, 144, -32.5, 11],
  ['SE_FINE_04_02', 'SE', 144, -35, 146.5, -32.5, 12],
  ['SE_FINE_05_02', 'SE', 146.5, -35, 149, -32.5, 13],
  ['SE_FINE_06_02', 'SE', 149, -35, 151.5, -32.5, 4],
  ['SE_FINE_07_02', 'SE', 151.5, -35, 154, -32.5, 1],
  ['SE_FINE_00_03', 'SE', 134, -32.5, 136.5, -30, 13],
  ['SE_FINE_01_03', 'SE', 136.5, -32.5, 139, -30, 12],
  ['SE_FINE_02_03', 'SE', 139, -32.5, 141.5, -30, 9],
  ['SE_FINE_03_03', 'SE', 141.5, -32.5, 144, -30, 12],
  ['SE_FINE_04_03', 'SE', 144, -32.5, 146.5, -30, 11],
  ['SE_FINE_05_03', 'SE', 146.5, -32.5, 149, -30, 9],
  ['SE_FINE_06_03', 'SE', 149, -32.5, 151.5, -30, 10],
  ['SE_FINE_07_03', 'SE', 151.5, -32.5, 154, -30, 9],
  ['TAS_FINE_01_00', 'TAS', 144.5, -44, 146, -43, 2],
  ['TAS_FINE_02_00', 'TAS', 146, -44, 147.5, -43, 28],
  ['TAS_FINE_02_01', 'TAS', 146, -43, 147.5, -42, 42],
  ['TAS_FINE_03_01', 'TAS', 147.5, -43, 149, -42, 9],
  ['TAS_FINE_01_02', 'TAS', 144.5, -42, 146, -41, 28],
  ['TAS_FINE_01_03', 'TAS', 144.5, -41, 146, -40, 3]
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
        recovery_method: 'original_frame_srs_fine_shard_recovery'
      });
    });
}

var POINTS = {
  SE: originalPoints('SE'),
  TAS: originalPoints('TAS')
};

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

var selected = PARTS.filter(function(part) {
  return BATCH.indexOf(part[0]) !== -1;
});

if (BATCH.length > 2) {
  throw new Error('Safety gate: BATCH must contain at most two cells.');
}
if (selected.length !== BATCH.length) {
  throw new Error('Safety gate: every BATCH name must match one PARTS entry.');
}

selected.forEach(function(part) {
  var cell = ee.Geometry.Rectangle(
    [part[2], part[3], part[4], part[5]], null, false);
  var points = inPart(POINTS[part[1]], part).map(function(feature) {
    return feature.set('recovery_part', part[0]);
  });
  Export.table.toDrive({
    collection: stack(cell).reduceRegions({
      collection: points,
      reducer: ee.Reducer.first(),
      crs: PROJECTION,
      tileScale: 4
    }),
    description: 'AU_' + RUN + '_recovery_' + part[0],
    folder: FOLDER,
    fileNamePrefix: 'recovery_' + part[0],
    fileFormat: 'CSV',
    selectors: selectors
  });
  print(part[0] + ' planned / live point counts', part[6], points.size());
});

print('Selected batch', BATCH);
print('Safety gate: submit at most these two tasks, then validate both CSVs.');
