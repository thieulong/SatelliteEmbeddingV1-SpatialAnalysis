// Count-only inventory for the remaining SE and TAS national-pilot recovery.
//
// This preserves the original sample frames, seeds and requested point count.
// The cells are computational partitions, not new sampling strata. Cells
// covered by SE_03, TAS_03 or the two 2026-10-05 benchmarks are omitted.
// This script creates no exports and submits no tasks.

var BOUNDARY = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var N = 200;
var FRAMES = {
  SE: {bounds: [134, -40, 154, -30], seed: 20260935},
  TAS: {bounds: [143, -44, 149, -40], seed: 20260936}
};

// Half-open cells: [name, stratum, west, south, east, north].
// SE grid: 2.5 x 2.5 degrees. TAS grid: 1.5 x 1 degree.
var PARTS = [
  ['SE_FINE_00_00', 'SE', 134, -40, 136.5, -37.5],
  ['SE_FINE_01_00', 'SE', 136.5, -40, 139, -37.5],
  ['SE_FINE_02_00', 'SE', 139, -40, 141.5, -37.5],
  ['SE_FINE_03_00', 'SE', 141.5, -40, 144, -37.5],
  ['SE_FINE_04_00', 'SE', 144, -40, 146.5, -37.5],
  ['SE_FINE_05_00', 'SE', 146.5, -40, 149, -37.5],
  ['SE_FINE_00_01', 'SE', 134, -37.5, 136.5, -35],
  ['SE_FINE_01_01', 'SE', 136.5, -37.5, 139, -35],
  ['SE_FINE_02_01', 'SE', 139, -37.5, 141.5, -35],
  ['SE_FINE_03_01', 'SE', 141.5, -37.5, 144, -35],
  ['SE_FINE_05_01', 'SE', 146.5, -37.5, 149, -35],
  ['SE_FINE_00_02', 'SE', 134, -35, 136.5, -32.5],
  ['SE_FINE_01_02', 'SE', 136.5, -35, 139, -32.5],
  ['SE_FINE_02_02', 'SE', 139, -35, 141.5, -32.5],
  ['SE_FINE_03_02', 'SE', 141.5, -35, 144, -32.5],
  ['SE_FINE_04_02', 'SE', 144, -35, 146.5, -32.5],
  ['SE_FINE_05_02', 'SE', 146.5, -35, 149, -32.5],
  ['SE_FINE_06_02', 'SE', 149, -35, 151.5, -32.5],
  ['SE_FINE_07_02', 'SE', 151.5, -35, 154, -32.5],
  ['SE_FINE_00_03', 'SE', 134, -32.5, 136.5, -30],
  ['SE_FINE_01_03', 'SE', 136.5, -32.5, 139, -30],
  ['SE_FINE_02_03', 'SE', 139, -32.5, 141.5, -30],
  ['SE_FINE_03_03', 'SE', 141.5, -32.5, 144, -30],
  ['SE_FINE_04_03', 'SE', 144, -32.5, 146.5, -30],
  ['SE_FINE_05_03', 'SE', 146.5, -32.5, 149, -30],
  ['SE_FINE_06_03', 'SE', 149, -32.5, 151.5, -30],
  ['SE_FINE_07_03', 'SE', 151.5, -32.5, 154, -30],
  ['TAS_FINE_00_00', 'TAS', 143, -44, 144.5, -43],
  ['TAS_FINE_01_00', 'TAS', 144.5, -44, 146, -43],
  ['TAS_FINE_02_00', 'TAS', 146, -44, 147.5, -43],
  ['TAS_FINE_03_00', 'TAS', 147.5, -44, 149, -43],
  ['TAS_FINE_00_01', 'TAS', 143, -43, 144.5, -42],
  ['TAS_FINE_02_01', 'TAS', 146, -43, 147.5, -42],
  ['TAS_FINE_03_01', 'TAS', 147.5, -43, 149, -42],
  ['TAS_FINE_00_02', 'TAS', 143, -42, 144.5, -41],
  ['TAS_FINE_01_02', 'TAS', 144.5, -42, 146, -41],
  ['TAS_FINE_00_03', 'TAS', 143, -41, 144.5, -40],
  ['TAS_FINE_01_03', 'TAS', 144.5, -41, 146, -40]
];

function originalPoints(stratum) {
  var spec = FRAMES[stratum];
  var frame = BOUNDARY.geometry().intersection(
    ee.Geometry.Rectangle(spec.bounds, null, false), 100);
  return ee.FeatureCollection.randomPoints(frame, N, spec.seed, 100)
    .map(function(feature) {
      var coordinates = feature.geometry().coordinates();
      return feature.set({
        original_lon: coordinates.get(0),
        original_lat: coordinates.get(1)
      });
    });
}

var POINTS = {
  SE: originalPoints('SE'),
  TAS: originalPoints('TAS')
};

function pointCount(part) {
  return POINTS[part[1]].filter(ee.Filter.and(
    ee.Filter.gte('original_lon', part[2]),
    ee.Filter.lt('original_lon', part[4]),
    ee.Filter.gte('original_lat', part[3]),
    ee.Filter.lt('original_lat', part[5])
  )).size();
}

var inventory = ee.FeatureCollection(PARTS.map(function(part) {
  return ee.Feature(null, {
    recovery_part: part[0],
    stratum: part[1],
    west: part[2], south: part[3], east: part[4], north: part[5],
    planned_points: pointCount(part)
  });
}));

print('Pending recovery inventory', inventory);
print('Pending SE points', inventory
  .filter(ee.Filter.eq('stratum', 'SE')).aggregate_sum('planned_points'));
print('Pending TAS points', inventory
  .filter(ee.Filter.eq('stratum', 'TAS')).aggregate_sum('planned_points'));
print('Expected pending totals after completed shards: SE 192; TAS 112.');
print('This script creates no export tasks.');
print('Pending point-count vector', inventory.aggregate_array('planned_points'));
