# Google Earth Engine Source

## Canonical embedding source

`hotspot_characterization_analysis.js` is the complete Bass Coast Earth Engine
workflow that generated the retained embedding-derived products. It loads
`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, applies the project AOI and land mask,
computes Euclidean embedding distance, and exports endpoint, annual, cumulative,
persistence, variance, slope, and timing products.

`hotspot_timeseries_analysis.js` is the earlier lighter time-series workflow.
It is retained for provenance, but it does not include the complete endpoint and
temporal-characterization export set. Use the characterization script as the
canonical Bass Coast baseline when adapting the Earth Engine stage.

## Visual-imagery source

`export_sentinel2_annual.js` creates annual 10 m true-colour Sentinel-2 visual
composites for 2017-2025 using Level-2A surface reflectance, Cloud Score+, and a
median composite. Its exports belong under `data/raw/sentinel2_annual/`.

Before national scaling, preserve the collection/version, AOI, land/water mask,
thresholds, CRS, scale, years, and export names in each run manifest. Do not
treat the Sentinel-2 visual export as a substitute for the embedding workflow.

## Mainland-and-Tasmania exploratory pilot

The three `national_*_pilot.js` files record the bounded 2026-09-21 Earth
Engine experiment: candidate boundary construction, seven-interval diagnostics
run one site at a time, and one small derived GeoTIFF export. See
`Documentation/08_NATIONAL_SCALING_PILOT_2026-09-21.md` for results and limits.
These files are not the canonical Bass Coast workflow and do not establish a
national threshold or authorize a wall-to-wall export.

`national_evidence_pilot_20260930.js` is the follow-up bounded experiment:
seven geographic strata with 200 random points each, four 100 km² raster
tiles, and three provenance exports. It creates 14 unsubmitted tasks, not a
national export loop. Keep at most two tasks active; inspect failures before
retrying. The run record in `Documentation/09_NATIONAL_EVIDENCE_PILOT_2026-09-30.md`
distinguishes prepared, submitted, and verified outputs. Do not interpret the
planned sample size as completed results.

`national_sample_recovery_20261004.js` preserves the original SE and Tasmania
random points, seeds, sampling frames, weights, metrics and 10 m grid while
processing them through smaller spatial cells. It also includes an NW check
cell for comparison with the completed NW sample. Run the check and one failed-
stratum diagnostic before the remaining parts; do not rerun the two original
whole-stratum tasks unchanged.

`national_recovery_shard_benchmark_20261005.js` tests one 2.5 x 2.5 degree SE
cell and one 1.5 x 1 degree Tasmania cell. Both benchmark exports completed and
passed local CSV QA. `national_recovery_fine_inventory_20261005.js` is a
count-only, no-export inventory of the remaining fine cells.

`national_recovery_fine_exports_20261005.js` contains only the 30 non-empty
pending cells and uses a hard allowlist of at most two cells per run. Do not use
`RUN ALL`. Review printed counts, submit only the allowlisted pair, and validate
both downloaded CSVs before changing the allowlist. These scripts recover the
bounded 1,400-point evidence pilot; they are not national wall-to-wall exports.

The recovery process subsequently found an unstable Tasmania mapping between
Earth Engine-generated random-point IDs and coordinates. The two
`national_recovery_*_point_stability_20261007.js` scripts diagnose that issue.
`national_frozen_manifest_recovery_20261007.js` and
`national_frozen_manifest_remaining_20261007.js` use explicit canonical
coordinates rather than regenerating random points. All frozen-manifest tasks
completed and the accepted sample now contains 1,400 unique IDs and sampled
cells. Reproduce the reconciliation and threshold-sensitivity outputs with
`analysis/tools/national_pilot_completion.py`. Do not treat completion of this
bounded sample as approval for wall-to-wall processing or as validation of a
national threshold.
