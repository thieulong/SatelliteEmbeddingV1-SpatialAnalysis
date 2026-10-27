// Exploratory diagnostics only: these windows are not a national sample.
// Run ONE site at a time. Running all seven together exceeded GEE capacity.
// Bass Coast's canonical analysis and frozen baseline remain unchanged.
var dataset = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
var boundary = ee.FeatureCollection(
  'projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var land = ee.ImageCollection('ESA/WorldCover/v200').first()
  .select('Map').neq(80);
var years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];
var selectedSite = 'Bass Coast';
var sites = [
  {name: 'Bass Coast', box: [145.55, -38.60, 145.65, -38.50]},
  {name: 'Tasmania', box: [147.00, -42.80, 147.10, -42.70]},
  {name: 'Central arid', box: [134.20, -24.20, 134.30, -24.10]},
  {name: 'Tropical north', box: [145.30, -16.80, 145.40, -16.70]},
  {name: 'Western Sydney', box: [150.70, -33.80, 150.80, -33.70]},
  {name: 'Southwest WA', box: [117.00, -32.50, 117.10, -32.40]},
  {name: 'Murray valley', box: [144.70, -35.30, 144.80, -35.20]}
];

function analyzeSite(site) {
  var roi = ee.Geometry.Rectangle(site.box, null, false);
  var images = years.map(function(year) {
    return dataset.filterDate(year + '-01-01', (year + 1) + '-01-01')
      .filterBounds(roi).mosaic().clip(roi).updateMask(land);
  });
  var counts = years.map(function(year) {
    return dataset.filterDate(year + '-01-01', (year + 1) + '-01-01')
      .filterBounds(roi).size();
  });
  function distance(a, b, name) {
    return b.subtract(a).pow(2).reduce(ee.Reducer.sum()).sqrt().rename(name);
  }

  var distances = [distance(images[0], images[7], 'endpoint')];
  var hot = [];
  var distanceNames = ['endpoint'];
  var hotNames = [];
  for (var i = 0; i < 7; i++) {
    var distanceName = 'd' + years[i];
    var hotName = 'h' + years[i];
    var annual = distance(images[i], images[i + 1], distanceName);
    distances.push(annual);
    hot.push(annual.gt(0.45).rename(hotName));
    distanceNames.push(distanceName);
    hotNames.push(hotName);
  }

  var stack = ee.Image.cat(distances.concat(hot));
  var samples = stack.sample({
    region: roi, scale: 10, numPixels: 100, seed: 2026,
    geometries: false, tileScale: 4
  });
  var reducer = ee.Reducer.percentile([50, 95]).repeat(8)
    .combine({reducer2: ee.Reducer.mean().repeat(7), sharedInputs: false});
  var stats = samples.reduceColumns({
    reducer: reducer, selectors: distanceNames.concat(hotNames)
  });
  print(site.name, ee.Dictionary({
    sample_n: samples.size(), tile_counts_2017_2024: counts,
    distance_names: distanceNames, annual_hot_names: hotNames, stats: stats
  }));
}

sites.filter(function(site) { return site.name === selectedSite; })
  .forEach(analyzeSite);
print('Boundary component count', boundary.size());
print('Caveat: about 100 sampled common-valid pixels per site; not area-weighted or representative. Annual hot comparison is strictly >0.45. No causal interpretation.');
Map.centerObject(ee.Geometry.Rectangle([112, -44, 154, -10]), 4);
