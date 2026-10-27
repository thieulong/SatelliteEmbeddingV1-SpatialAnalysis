// Diagnose whether repeated TAS randomPoints evaluation preserves point IDs.
//
// This creates two tiny Drive exports of the same 200-point definition. It
// does not calculate embedding distances or change the recovery sample. The
// outputs must be compared with each other and with the 186 verified TAS rows
// before any further recovery cell is submitted.

var RUN = '20260930';
var DIAGNOSTIC = '20261007';
var FOLDER = 'AusHabitat_Pilot_' + RUN + '_Recovery_20261005';
var BOUNDARY = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var FRAME = {bounds: [143, -44, 149, -40], seed: 20260936};
var N = 200;

function points(realisation) {
  var frame = BOUNDARY.geometry().intersection(
    ee.Geometry.Rectangle(FRAME.bounds, null, false), 100);
  return ee.FeatureCollection.randomPoints(frame, N, FRAME.seed, 100)
    .map(function(feature) {
      var coordinates = feature.geometry().coordinates();
      return ee.Feature(null, {
        realisation: realisation,
        point_id: ee.String('TAS_').cat(ee.String(feature.id())),
        original_lon: coordinates.get(0),
        original_lat: coordinates.get(1),
        seed: FRAME.seed,
        n_requested: N
      });
    });
}

['A', 'B'].forEach(function(realisation) {
  var manifest = points(realisation);
  Export.table.toDrive({
    collection: manifest,
    description: 'AU_' + RUN + '_TAS_POINT_STABILITY_' + realisation,
    folder: FOLDER,
    fileNamePrefix: 'tas_point_stability_' + DIAGNOSTIC + '_' + realisation,
    fileFormat: 'CSV',
    selectors: [
      'realisation', 'point_id', 'original_lon', 'original_lat',
      'seed', 'n_requested'
    ]
  });
  print('TAS point stability ' + realisation + ' count', manifest.size());
});

print('Diagnostic only: compare A, B, and all verified TAS rows before recovery resumes.');
