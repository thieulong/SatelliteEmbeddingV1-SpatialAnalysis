"""Validate completed or partially completed national-pilot sample exports."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


DISTANCES = ['endpoint'] + [f'd{year}' for year in range(2017, 2024)]
VALID = [f'v{year}' for year in range(2017, 2025)]
REQUIRED = {
    'stratum', 'point_id', 'frame_km2', 'n_requested', 'original_lon',
    'original_lat', 'norm2017', 'norm2024', 'dot_endpoint',
    'worldcover2021', 'longitude', 'latitude', *DISTANCES, *VALID,
}


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inspect(path):
    data = pd.read_csv(path)
    missing_columns = sorted(REQUIRED - set(data.columns))
    if missing_columns:
        raise ValueError(f'{path.name}: missing columns {missing_columns}')
    values = data[DISTANCES].to_numpy(float)
    valid = data[VALID].to_numpy(int)
    identity_error = np.abs(
        data.endpoint.to_numpy(float) ** 2
        - (data.norm2017.to_numpy(float) ** 2
           + data.norm2024.to_numpy(float) ** 2
           - 2 * data.dot_endpoint.to_numpy(float))
    )
    strata = sorted(data.stratum.astype(str).unique())
    return {
        'file': path.name,
        'bytes': path.stat().st_size,
        'sha256': sha256(path),
        'rows': len(data),
        'strata': strata,
        'unique_point_ids': int(data.point_id.nunique()),
        'unique_sampled_cells': int(data[['longitude', 'latitude']].drop_duplicates().shape[0]),
        'n_requested_values': sorted(data.n_requested.astype(int).unique().tolist()),
        'frame_km2_values': sorted(data.frame_km2.astype(float).unique().tolist()),
        'distance_sentinel_values': int(np.count_nonzero(values == -9999)),
        'nonfinite_distance_values': int(np.count_nonzero(~np.isfinite(values))),
        'invalid_validity_flags': int(np.count_nonzero(~np.isin(valid, [0, 1]))),
        'water_points_worldcover_80': int((data.worldcover2021 == 80).sum()),
        'unknown_points_worldcover_0': int((data.worldcover2021 == 0).sum()),
        'endpoint_identity_max_abs_error': float(identity_error.max()) if len(data) else None,
        'norm2017_range': [float(data.norm2017.min()), float(data.norm2017.max())],
        'norm2024_range': [float(data.norm2024.min()), float(data.norm2024.max())],
        'checks': {
            'point_ids_unique': bool(data.point_id.is_unique),
            'sampled_cells_unique': bool(
                len(data[['longitude', 'latitude']].drop_duplicates()) == len(data)),
            'distances_finite': bool(np.isfinite(values).all()),
            'distance_identity_within_1e-10': bool(
                len(data) == 0 or identity_error.max() < 1e-10),
            'validity_flags_binary': bool(np.isin(valid, [0, 1]).all()),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path,
                        default=Path('data/raw/national_pilot/2026-09-30'))
    parser.add_argument('--out', type=Path,
                        default=Path('data/processed/national_pilot/2026-09-30/sample_qa.json'))
    args = parser.parse_args()
    files = sorted(args.raw.glob('sample_*.csv'))
    if not files:
        raise FileNotFoundError(f'No sample CSV files in {args.raw}')
    records = [inspect(path) for path in files]
    summary = {
        'status': 'PASS' if all(all(r['checks'].values()) for r in records) else 'FAIL',
        'files': records,
        'total_rows': sum(r['rows'] for r in records),
        'observed_strata': sorted({s for r in records for s in r['strata']}),
        'missing_expected_strata': sorted(
            {'NW', 'NE', 'CW', 'CE', 'SW', 'SE', 'TAS'}
            - {s for r in records for s in r['strata']}),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
