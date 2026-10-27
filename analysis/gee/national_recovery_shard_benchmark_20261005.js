// Fine-shard benchmark for the incomplete SE and TAS national-pilot samples.
//
// This preserves the original frames, random points, seeds, weights, grid,
// years and measurements. The two cells are computational partitions only:
// one contrasting inland SE cell and one unprocessed central TAS cell. They
// align with candidate 2.5 x 2.5 degree SE and 1.5 x 1 degree TAS grids so
// successful outputs can be retained in the eventual recovery merge.
//
// Run the script, inspect the printed point counts, then submit only these two
// exports. Do not run additional recovery cells until runtime, EECU usage and
// output QA have been reviewed.

var RUN = '20260930';
var BENCHMARK = '20261005';
var FOLDER = 'AusHabitat_Pilot_' + RUN + '_Recovery_' + BENCHMARK;
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

// Half-open cells: [west, south, east, north].
// SE cell is inland/eastern Victoria and does not overlap completed SE_03.
// TAS cell is within the unprocessed western half of the former TAS_00 cell.
var PARTS = [
  ['SE_FINE_04_01', 'SE', 144, -37.5, 146.5, -35],
  ['TAS_FINE_01_01', 'TAS', 144.5, -43, 146, -42]
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
        recovery_method: 'original_frame_srs_fine_shard_benchmark'
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
  var samples = stack(cell).reduceRegions({
    collection: points,
    reducer: ee.Reducer.first(),
    crs: PROJECTION,
    tileScale: 4
  });
  Export.table.toDrive({
    collection: samples,
    description: 'AU_' + RUN + '_benchmark_' + part[0],
    folder: FOLDER,
    fileNamePrefix: 'benchmark_' + part[0],
    fileFormat: 'CSV',
    selectors: selectors
  });
  print(part[0] + ' planned point count', points.size());
});

print('Submit only the two fine-shard benchmark exports.');
print('Review runtime, EECU usage and CSV QA before preparing more cells.');
