"""Bounded pilot QA: lossless compression and coarse boundary screening.

No downloads or changes to source rasters. Outputs are local, ignored data.
The 1 km boundary comparison is NOT validation of a 10 m coastline.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.shutil import copy as rio_copy
from rasterio.transform import from_origin
from rasterio.warp import transform_geom


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def polygon_area(coords):
    def ring_area(ring):
        xy = np.asarray(ring, dtype=float)
        return abs(np.sum(xy[:-1, 0]*xy[1:, 1]-xy[1:, 0]*xy[:-1, 1]))/2
    return ring_area(coords[0])-sum(ring_area(r) for r in coords[1:])


def boundaries(raw, out):
    candidate_path = raw/'candidate_boundary.geojson'
    ga_path = raw/'ga_landmass.geojson'
    candidate = json.loads(candidate_path.read_text())
    ga = json.loads(ga_path.read_text())
    projected_candidate = [transform_geom('EPSG:4326', 'EPSG:3577', f['geometry'])
                           for f in candidate['features']]
    selected = []
    for f in ga['features']:
        name = f['properties'].get('nam', '')
        if 'howe' in name.lower():
            continue
        geom = transform_geom('EPSG:4326', 'EPSG:3577', f['geometry'])
        parts = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        largest = max(parts, key=polygon_area)
        selected.append({'type':'Feature', 'properties':{'name':name},
                         'geometry':{'type':'Polygon','coordinates':largest}})
    assert len(selected) == 8, 'Expected eight states/territories, excluding Lord Howe'
    geometries = projected_candidate+[f['geometry'] for f in selected]
    def vertices(g):
        parts = g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
        return np.concatenate([np.asarray(r) for p in parts for r in p])
    xy = np.concatenate([vertices(g) for g in geometries])
    xmin, ymin = np.floor(xy.min(axis=0)/1000)*1000
    xmax, ymax = np.ceil(xy.max(axis=0)/1000)*1000
    shape = (int((ymax-ymin)/1000), int((xmax-xmin)/1000))
    transform = from_origin(xmin, ymax, 1000, 1000)
    a = rasterize(projected_candidate, out_shape=shape, transform=transform, dtype='uint8')
    b = rasterize([f['geometry'] for f in selected], out_shape=shape, transform=transform, dtype='uint8')
    result = {'method':'EPSG:3577, 1 km pixel-centre rasterization; coarse comparison, not coastline ground truth',
              'candidate_sha256':digest(candidate_path), 'ga_sha256':digest(ga_path),
              'candidate_components':len(projected_candidate),
              'ga_selected_state_parts':[f['properties']['name'] for f in selected],
              'candidate_grid_km2':int(a.sum()), 'ga_grid_km2':int(b.sum()),
              'candidate_only_grid_km2':int(np.count_nonzero((a==1)&(b==0))),
              'ga_only_grid_km2':int(np.count_nonzero((a==0)&(b==1))),
              'intersection_grid_km2':int(np.count_nonzero((a==1)&(b==1)))}
    (out/'boundary_screening.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def raster_benchmark(path, out):
    records = []
    with rasterio.open(path) as src:
        reference = src.read()
        valid = (reference != src.nodata) & np.isfinite(reference)
        base = {'source':path.name, 'source_sha256':digest(path), 'width':src.width,
                'height':src.height, 'bands':src.count, 'crs':str(src.crs),
                'transform':list(src.transform), 'nodata':src.nodata,
                'valid_values':int(valid.sum()), 'total_values':reference.size,
                'min':float(reference[valid].min()), 'max':float(reference[valid].max()),
                'mean':float(reference[valid].mean(dtype=np.float64)),
                'overviews':src.overviews(1), 'source_image_structure':src.tags(ns='IMAGE_STRUCTURE')}
        for codec in ['original', 'DEFLATE', 'ZSTD']:
            target = path if codec=='original' else out/(path.stem+'_'+codec.lower()+'.tif')
            started = time.perf_counter()
            if codec!='original':
                rio_copy(path, target, driver='COG', COMPRESS=codec, PREDICTOR='FLOATING_POINT',
                         OVERVIEWS='FORCE_USE_EXISTING', BLOCKSIZE=512, NUM_THREADS='2')
            elapsed = time.perf_counter()-started
            with rasterio.open(target) as dst:
                assert dst.crs == src.crs and dst.transform == src.transform
                assert dst.nodata == src.nodata and dst.dtypes == src.dtypes
                assert dst.overviews(1) == src.overviews(1)
                assert dst.read().tobytes() == reference.tobytes(), 'Base pixels changed'
                assert dst.tags(ns='IMAGE_STRUCTURE').get('LAYOUT') == 'COG'
                records.append({**base, 'codec':codec, 'bytes':target.stat().st_size,
                                'sha256':digest(target), 'write_seconds':elapsed,
                                'base_pixels_bitwise_equal':True, 'cog_layout_tag':True})
    return records


def tile_manifest_checks(raw):
    manifest_path = raw/'tile_manifest.geojson'
    if not manifest_path.exists():
        return {'status': 'NOT_AVAILABLE', 'tiles': []}
    manifest = json.loads(manifest_path.read_text())
    records = []
    for feature in manifest['features']:
        props = feature['properties']
        tile_id = props['tile_id']
        path = raw/f'tile_{tile_id}_8dist_10m.tif'
        if not path.exists():
            records.append({'tile_id': tile_id, 'status': 'RASTER_MISSING'})
            continue
        with rasterio.open(path) as src:
            expected_bounds = [props['xmin'], props['ymin'],
                               props['xmax'], props['ymax']]
            actual_bounds = [src.bounds.left, src.bounds.bottom,
                             src.bounds.right, src.bounds.top]
            checks = {
                'width_matches': src.width == props['width'],
                'height_matches': src.height == props['height'],
                'bounds_match': np.allclose(actual_bounds, expected_bounds),
                'crs_matches': str(src.crs) == props['crs'],
                'pixel_size_matches': (
                    abs(src.transform.a) == props['pixel_size_m']
                    and abs(src.transform.e) == props['pixel_size_m']),
                'band_count_matches': src.count == len(
                    props['band_order'].split(';')),
            }
            records.append({
                'tile_id': tile_id,
                'status': 'PASS' if all(checks.values()) else 'FAIL',
                'expected_dimensions': [props['width'], props['height']],
                'actual_dimensions': [src.width, src.height],
                'expected_bounds': expected_bounds,
                'actual_bounds': actual_bounds,
                'checks': checks,
            })
    return {
        'status': 'PASS' if records and all(
            r['status'] == 'PASS' for r in records) else 'FAIL',
        'tiles': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=Path('data/raw/national_pilot/2026-09-30'))
    parser.add_argument('--out', type=Path, default=Path('data/processed/national_pilot/2026-09-30'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    results = {
        'raw_files': [
            {'file': path.name, 'bytes': path.stat().st_size,
             'sha256': digest(path)}
            for path in sorted(args.raw.iterdir()) if path.is_file()
        ],
        'boundary': boundaries(args.raw, args.out),
        'tile_manifest': tile_manifest_checks(args.raw),
        'rasters': [],
    }
    for path in sorted(args.raw.glob('*.tif')):
        results['rasters'].extend(raster_benchmark(path,args.out))
    (args.out/'file_qa.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__ == '__main__':
    main()
