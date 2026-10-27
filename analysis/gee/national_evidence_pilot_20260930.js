// Bounded evidence pilot: 1,400 random points, four 10 km raster tiles.
// Creates unsubmitted tasks. Run at most two tasks concurrently; do not retry
// failed tasks more than once without diagnosing the failure.
var RUN = '20260930';
var FOLDER = 'AusHabitat_Pilot_' + RUN;
var DATA = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL');
var BOUNDARY = ee.FeatureCollection('projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1');
var WC = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map');
var YEARS = [2017,2018,2019,2020,2021,2022,2023,2024];
var CRS = 'EPSG:3577';
var TRANSFORM = [10,0,0,0,-10,0];
var N = 200;
var STRATA = [
  ['NW',[112,-20,134,-9]], ['NE',[134,-20,154,-9]],
  ['CW',[112,-30,134,-20]], ['CE',[134,-30,154,-20]],
  ['SW',[112,-40,134,-30]], ['SE',[134,-40,154,-30]],
  ['TAS',[143,-44,149,-40]]
];
var DIST_NAMES = ['endpoint','d2017','d2018','d2019','d2020','d2021','d2022','d2023'];
function source(year, roi) {
  return DATA.filterDate(year+'-01-01',(year+1)+'-01-01').filterBounds(roi).sort('system:index');
}
function stack(roi) {
  var annual = YEARS.map(function(y) { return source(y,roi).mosaic().select('A.*'); });
  var valid = annual.map(function(img,i) {
    return img.mask().reduce(ee.Reducer.min()).unmask(0,false).rename('v'+YEARS[i]);
  });
  function dist(a,b,name) {
    return b.subtract(a).pow(2).reduce(ee.Reducer.sum()).sqrt().rename(name).unmask(-9999,false);
  }
  var distances = [dist(annual[0],annual[7],'endpoint')];
  for (var i=0;i<7;i++) distances.push(dist(annual[i],annual[i+1],'d'+YEARS[i]));
  var norms = [annual[0].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2017'),
    annual[7].pow(2).reduce(ee.Reducer.sum()).sqrt().rename('norm2024'),
    annual[0].multiply(annual[7]).reduce(ee.Reducer.sum()).rename('dot_endpoint')];
  return ee.Image.cat(distances.concat(valid)).addBands(ee.Image.cat(norms).unmask(-9999,false))
    .addBands(WC.unmask(0,false).rename('worldcover2021')).addBands(ee.Image.pixelLonLat());
}
var metadata = [];
STRATA.forEach(function(spec,i) {
  var roi = BOUNDARY.geometry().intersection(ee.Geometry.Rectangle(spec[1],null,false),100);
  var area = roi.area(100).divide(1e6);
  var points = ee.FeatureCollection.randomPoints(roi,N,20260930+i,100).map(function(f) {
    var xy = f.geometry().coordinates();
    return f.set({stratum:spec[0],point_id:ee.String(spec[0]).cat('_').cat(ee.String(f.id())),
      frame_km2:area,n_requested:N,original_lon:xy.get(0),original_lat:xy.get(1)});
  });
  var samples = stack(roi).sampleRegions({collection:points,projection:ee.Projection(CRS,TRANSFORM),
    tileScale:4,geometries:false});
  Export.table.toDrive({collection:samples,description:'AU_'+RUN+'_sample_'+spec[0],
    folder:FOLDER,fileNamePrefix:'sample_'+spec[0],fileFormat:'CSV'});
  YEARS.forEach(function(y) {
    var c = source(y,roi);
    metadata.push(ee.Feature(null,{stratum:spec[0],year:y,frame_km2:area,n_requested:N,
      seed:20260930+i,source_count:c.size(),source_ids:c.aggregate_array('system:index').join(';'),
      dataset_versions:c.aggregate_array('DATASET_VERSION').distinct().join(';')}));
  });
});
Export.table.toDrive({collection:ee.FeatureCollection(metadata),description:'AU_'+RUN+'_sources',
  folder:FOLDER,fileNamePrefix:'sources',fileFormat:'CSV'});
Export.table.toDrive({collection:BOUNDARY,description:'AU_'+RUN+'_candidate_boundary',
  folder:FOLDER,fileNamePrefix:'candidate_boundary',fileFormat:'GeoJSON'});
var TILES = [['arid',134.25,-24.15],['wheatbelt',117.05,-32.45],
  ['tasmania',147.05,-42.75],['sydney',150.75,-33.75]];
var tileMetadata = [];
TILES.forEach(function(spec) {
  var xy = ee.Geometry.Point([spec[1],spec[2]]).transform(CRS,1).coordinates();
  var x = ee.Number(xy.get(0)).divide(10000).floor().multiply(10000);
  var y = ee.Number(xy.get(1)).divide(10000).floor().multiply(10000);
  var roi = ee.Geometry.Rectangle(ee.List([x,y,x.add(10000),y.add(10000)]),CRS,false);
  var image = stack(roi).select(DIST_NAMES).toFloat()
    .updateMask(WC.neq(80).and(WC.neq(0))).clipToCollection(BOUNDARY)
    .unmask(-9999,false).clip(roi);
  Export.image.toDrive({image:image,description:'AU_'+RUN+'_tile_'+spec[0],folder:FOLDER,
    fileNamePrefix:'tile_'+spec[0]+'_8dist_10m',region:roi,crs:CRS,crsTransform:TRANSFORM,
    maxPixels:10000000,fileFormat:'GeoTIFF',formatOptions:{cloudOptimized:true,noData:-9999}});
  var props = {tile_id:spec[0],xmin:x,ymin:y,xmax:x.add(10000),ymax:y.add(10000),
    crs:CRS,pixel_size_m:10,width:1000,height:1000,band_order:DIST_NAMES.join(';')};
  YEARS.forEach(function(y) { props['ids_'+y] = source(y,roi).aggregate_array('system:index').join(';'); });
  tileMetadata.push(ee.Feature(roi,props));
});
Export.table.toDrive({collection:ee.FeatureCollection(tileMetadata),description:'AU_'+RUN+'_tiles',
  folder:FOLDER,fileNamePrefix:'tile_manifest',fileFormat:'GeoJSON'});
print('Bounded tasks: 7 samples x 200 points, 4 rasters x 100 km2 x 8 bands, 3 manifests.');
print('Sampling retains water and missing embedding values for explicit QA. Use frame-area weights.');
print('The GAUL candidate boundary remains provisional. No thresholds are selected by this script.');
Map.setCenter(134,-27,4);
