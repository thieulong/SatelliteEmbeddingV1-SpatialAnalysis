// Candidate mainland-and-Tasmania boundary for a bounded national pilot.
// GAUL 2015's four largest Australian polygon components are used here.
// This is not a final coastline/island or licensing decision.
var australia = ee.FeatureCollection('FAO/GAUL/2015/level0')
  .filter(ee.Filter.eq('ADM0_NAME', 'Australia'));
var parts = ee.List(australia.geometry().geometries());
var ranked = ee.FeatureCollection(parts.map(function(part) {
  var geometry = ee.Geometry(part);
  var centroid = geometry.centroid(100).coordinates();
  return ee.Feature(geometry, {
    km2: geometry.area(100).divide(1e6),
    lon: centroid.get(0),
    lat: centroid.get(1)
  });
})).sort('km2', false);
var selected = ranked.limit(4);
var mask = selected.geometry();

print('Selected component areas km2', selected.aggregate_array('km2'));
print('Selected component centroids lon/lat',
  selected.aggregate_array('lon'), selected.aggregate_array('lat'));
print('Selected total area km2', mask.area(100).divide(1e6));
function inside(lon, lat) {
  return mask.contains(ee.Geometry.Point([lon, lat]), 100);
}
print('Named point checks', ee.Dictionary({
  Perth: inside(115.86, -31.95), Darwin: inside(130.84, -12.46),
  AliceSprings: inside(133.88, -23.70), Sydney: inside(151.21, -33.87),
  Melbourne: inside(144.96, -37.81), Hobart: inside(147.33, -42.88),
  KangarooIsland: inside(136.90, -35.80),
  FlindersIsland: inside(148.0, -40.0), NorfolkIsland: inside(167.96, -29.04)
}));

// Run once only if the named asset does not already exist.
Export.table.toAsset({
  collection: selected,
  description: 'AusHabitat_mainland_Tas_GAUL2015_pilot_v1',
  assetId: 'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1',
  maxVertices: 100000
});
