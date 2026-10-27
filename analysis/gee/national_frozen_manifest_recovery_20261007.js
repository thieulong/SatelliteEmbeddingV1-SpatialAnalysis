// Fixed-coordinate recovery after the 2026-10-07 point-stability diagnostic.
//
// The point coordinates below come from the frozen canonical manifests:
//   SE:  se_point_stability_20261007_A.csv
//        SHA-256 f33c7e3e74ff09984f0d0d2d0d71242e0e4d726c1e369633cfc8bbb150a91516
//   TAS: tas_point_stability_20261007_B.csv
//        SHA-256 5af57108db1b707e744004f7cc609d7f5ad4e9570066095ca629e7172e721fd7
//
// This script deliberately does not call ee.FeatureCollection.randomPoints.
// It creates exactly two unsubmitted tasks. Run at most these two together,
// retrieve both CSVs, and pass the identity and numerical QA gates before
// adding another recovery cell.

var RUN = '20260930';
var RECOVERY = '20261007';
var FOLDER = 'AusHabitat_Pilot_' + RUN + '_Recovery_20261005';
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

var RECOVERY_PARTS = [
  {
    name: 'SE_FINE_03_03',
    stratum: 'SE',
    bounds: [141.5, -32.5, 144, -30],
    points: [
      ['SE_23', 143.35505970285197, -30.26085639108105],
      ['SE_46', 142.78136995547823, -31.061823314866423],
      ['SE_56', 143.1502309527733, -31.157598836833586],
      ['SE_63', 143.9102003817975, -30.34737022977347],
      ['SE_88', 142.18408714599107, -30.46195727371944],
      ['SE_119', 142.97137993875575, -30.134161404122395],
      ['SE_134', 141.70436187961533, -30.014671755431863],
      ['SE_155', 142.26134766533448, -31.98457725587885],
      ['SE_174', 143.02351586920258, -30.412627719339007],
      ['SE_177', 141.62651126853817, -30.778242028494393],
      ['SE_186', 143.5602541813148, -30.711870995727782],
      ['SE_195', 143.83885365274605, -31.417562397386085]
    ]
  },
  {
    name: 'TAS_FINE_01_03',
    stratum: 'TAS',
    bounds: [144.5, -41, 146, -40],
    points: [
      ['TAS_25', 145.09315822764285, -40.90823205455268],
      ['TAS_55', 144.78641736745436, -40.976886446844205],
      ['TAS_148', 145.12022182414645, -40.92656395021389]
    ]
  }
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

function frameArea(stratum) {
  var spec = FRAMES[stratum];
  return BOUNDARY.geometry().intersection(
    ee.Geometry.Rectangle(spec.bounds, null, false), 100)
    .area(100).divide(1e6);
}

function fixedPoints(part) {
  var area = frameArea(part.stratum);
  var seed = FRAMES[part.stratum].seed;
  return ee.FeatureCollection(part.points.map(function(point) {
    return ee.Feature(ee.Geometry.Point([point[1], point[2]]), {
      stratum: part.stratum,
      point_id: point[0],
      frame_km2: area,
      n_requested: N,
      sample_weight_km2: area.divide(N),
      seed: seed,
      original_lon: point[1],
      original_lat: point[2],
      recovery_method: 'frozen_manifest_fixed_coordinate_recovery',
      recovery_part: part.name,
      manifest_date: RECOVERY
    });
  }));
}

var selectors = [
  'stratum', 'point_id', 'frame_km2', 'n_requested', 'sample_weight_km2',
  'seed', 'original_lon', 'original_lat', 'recovery_method', 'recovery_part',
  'manifest_date'
].concat(DIST_NAMES)
  .concat(['v2017', 'v2018', 'v2019', 'v2020', 'v2021', 'v2022',
    'v2023', 'v2024', 'norm2017', 'norm2024', 'dot_endpoint',
    'worldcover2021', 'longitude', 'latitude']);

RECOVERY_PARTS.forEach(function(part) {
  var cell = ee.Geometry.Rectangle(part.bounds, null, false);
  var samples = stack(cell).reduceRegions({
    collection: fixedPoints(part),
    reducer: ee.Reducer.first(),
    crs: PROJECTION,
    tileScale: 4
  });
  Export.table.toDrive({
    collection: samples,
    description: 'AU_' + RUN + '_frozen_recovery_' + part.name,
    folder: FOLDER,
    fileNamePrefix: 'frozen_recovery_' + part.name,
    fileFormat: 'CSV',
    selectors: selectors
  });
  print(part.name + ' frozen point count', fixedPoints(part).size());
});

print('Two fixed-coordinate recovery tasks only; validate both before extending the list.');
