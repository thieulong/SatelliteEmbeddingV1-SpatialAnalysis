# Mainland-and-Tasmania evidence pilot — 2026-09-30

## Scope and checkpoint

The user approved gathering bounded evidence before choosing thresholds and
storage. This is not approval for wall-to-wall national exports, infrastructure
provisioning, or web expansion. Mainland and Tasmania are in scope; offshore
islands and coastal waters are excluded in the intended final product. The
candidate geometry and water mask still require validation.

Run-start Git commit: `4fb9f9e951129a663261b8e742b3aa85231ddecb`, branch `main`.
New pilot code is uncommitted and is **not** contained in that commit. The frozen
Bass Coast baseline and application have not been changed. Previous 2026-09-21
pilot working-tree additions are retained.

Local source SHA-256 at this checkpoint:

- GEE pilot: `7f64d7a7fb42c2430af9605d706aa80ff3c65785c5d9aea7b96ba22039a90203`.
- File-QA tool after the 2026-10-04 manifest check:
  `1a373eafee91b740d1145ebfd35a3992f753a1aa3efffd9f8c06f0c2109de087`.
- Sample-QA tool: `991e29bb314fd12a3cf211f4a57aa74560c0867020ea2b8048d8cbb7816ed845`.
- Recovery GEE script after the 2026-10-04 control-window correction:
  `f1af6e5e2a81e31b69a168aeb7619a5bf6eadb00a7c342de2faa161002056480`.

## Prepared sampling and raster experiment

Source: `analysis/gee/national_evidence_pilot_20260930.js`. Equivalent compact
code was saved as `AusHabitat_evidence_pilot_20260930` in the existing Earth
Engine script repository. Cloud and local source formatting is not identical.
Submitted-task [source snapshot](https://code.earthengine.google.com/823ca1295a658b03f92857c85e864b3e)
and [separate output folder](https://drive.google.com/drive/folders/1FMxaA8P0W1Ty2XQh0AccJEHOk8uoA2kf)
retain cloud provenance.

- 2017–2024, endpoint plus seven consecutive-year Euclidean distances using all
  64 dimensions. Annual hot comparison remains strictly `distance > 0.45` when
  comparing with Bass Coast; no national threshold is selected.
- Seven geographic sampling strata: northwest, northeast, central-west,
  central-east, southwest, southeast, Tasmania; 200 independently randomized
  locations per stratum, seeds 20260930–20260936, total 1,400 planned points.
- Each rectangular stratum is intersected with the existing four-component
  GAUL pilot boundary. Samples are evaluated on a fixed EPSG:3577 10 m grid.
  Missing values and WorldCover water observations are retained explicitly;
  validity flags, endpoint vector norms, dot product, original and sampled
  coordinates support QA. This is geographic stratification, not yet a
  land-cover-stratified allocation. Rare classes may remain poorly represented.
- Area weights must be `frame_km2 / 200`, not equal weights across strata.
  Estimate separately for valid non-water support and report its coverage;
  do not silently discard missing observations. Compare pair-valid with
  common-eight-year-valid support. Check frame coverage, duplicate snapped
  cells, vector norms, and distance/dot-product consistency before inference.
- WorldCover 2021 is static contextual stratification, not annual truth.
  Report weighted distributions and threshold sensitivity with uncertainty,
  not an optimal threshold or accuracy claim. Class-conditional results with
  sparse samples need explicit warnings or additional sampling.
- Four aligned 10 km × 10 km tiles: central arid, WA wheatbelt, Tasmania,
  western Sydney. Each is planned as 1,000 × 1,000 cells, eight Float32
  distance bands, EPSG:3577, 10 m, `-9999` nodata, COG. The tiles exclude
  WorldCover class 80 and unknown class 0 and clip to the provisional boundary.
- Four raster tasks, seven sample tasks, three provenance tasks. No national
  tile loop. At most two active tasks; diagnose before at most one retry.
  No billing, quota, access, or storage-account changes. Stop on unexpected
  geometry, output dimensions, or repeated resource errors.

### Actual export state at handoff

| Output | Verified state |
| --- | --- |
| Candidate boundary | Completed; task `SPIGT2GHGVOKC7V6ON4AJ7BA`, 18 s; downloaded and hashed |
| Source metadata | Submitted; task `FJTHAELIPLQFQQW4HYRLJTNZ`; last UI observation running at 10 min, 3,118.4446 EECU-seconds; completion not verified |
| Northwest sample | Export confirmation dialog opened; submission not verified |
| Other six samples, four rasters, tile manifest | Prepared but not submitted |

### Status reviewed 2026-10-04

The user subsequently submitted all original tasks. Five sample strata (NW,
NE, CW, CE and SW), all four raster tiles, source metadata, tile manifest and
candidate boundary completed. SE task `NBNSQUXXRVVNTCQGUUO3ZPSW` and Tasmania
task `YNEKUUVP6WZKZ6NX6PVBHNG3` each failed after 12 hours with
`Computation timed out` (error code 3). They used 722.4974 and 19,165.4531
EECU-seconds respectively. This is a resource failure, not evidence of missing
embedding coverage or invalid observations.

The completed Drive files were downloaded into the ignored raw pilot directory.
The five CSVs contain 1,000 rows: 200 unique point IDs and 200 unique sampled
cells per stratum. All distance values are finite, all validity flags are
binary, and the endpoint distance/dot-product identity agrees within
2.4 × 10^-15. SE and Tasmania comprise about 16.98% of the candidate frame
area, so the five completed strata must not be reported as a national estimate.

`analysis/gee/national_sample_recovery_20261004.js` implements a bounded repair.
It recreates the exact original SRS point collections from their original frame,
seed and requested count, then assigns the points to mutually exclusive spatial
processing cells. Each cell builds its embedding mosaic only over its simple
rectangle and uses point-oriented `reduceRegions`. Original frame weights remain
`frame_km2 / 200`; the cells are computational shards, not new sampling strata.
An NW check cell is included to verify equivalence with an already successful
sample before completing SE and Tasmania.

### Recovery diagnostic status — 2026-10-04 to 2026-10-05

The user created the cloud script `AusHabitat_sample_recovery_20261004` and
submitted the first two diagnostics. Both completed without a resource error:

- `AU_20260930_recovery_NW_CHECK` completed in about 2 minutes, but its
  112–117.5°E control window contained none of the original NW sample points.
  The resulting CSV has a header and zero data rows, so it cannot establish
  extraction equivalence. This is a diagnostic-design issue, not an embedding
  result. The local script now replaces it with `NW_CHECK2`, using
  123–125.75°E and 20–14.5°S; 28 original NW points fall in that window.
- `AU_20260930_recovery_SE_03` completed in about 5 minutes. Its CSV contains
  two unique original points (`SE_54` and `SE_164`), binary validity flags,
  finite distance values and endpoint-vector identity within numerical
  tolerance. The small row count is consistent with the coastal processing
  cell and is not by itself an error.
- `AU_20260930_recovery_TAS_03`, task
  `I774XQYQ5OVSVV3Q6WEA7LRD`, completed on its first attempt in about 2 hours
  after starting at 2026-10-04 22:29:05 +1100. Final batch usage was
  12,181.1084 EECU-seconds. Its CSV contains 67 unique original points and 67
  unique sampled cells, with finite distances, binary validity flags and
  endpoint-vector identity within 1.92 × 10^-15. Three points have static
  WorldCover class 80; none has class 0. File size is 29,539 bytes and SHA-256
  is `24e012ea65dc0ca843c5c1e8c8417c97808338cd402ffba1b48f02ae1089a34d`.
  The successful output validates this shard scientifically, but the runtime
  and compute usage show that the present 3 x 2 degree Tasmania cells are too
  expensive to treat as the default recovery partition without refinement.
- `AU_20260930_recovery_NW_CHECK2`, task
  `XINES4MPFOP3ELRCPSK5J4W4`, completed on its first attempt in about 3 minutes
  after starting at 2026-10-05 01:05:47 +1100. Final batch usage was 729.8237
  EECU-seconds. Its CSV contains exactly the 28 original NW points expected in
  the corrected half-open control window, with no duplicate sampled cells,
  non-finite distances, sentinel distances, class-0 observations or class-80
  observations. All 28 point IDs and every field shared with the original NW
  export match exactly; the maximum numerical difference is zero. The
  endpoint-vector identity agrees within 2.28 × 10^-15. File size is 12,503
  bytes and SHA-256 is
  `becd2fbe26b2979bab1aac182447f755312d7cfc483353565bc591e51ad932bd`.
  This establishes extraction equivalence for the revised recovery method.

The recovery Drive folder is
[`AusHabitat_Pilot_20260930_Recovery_20261004`](https://drive.google.com/drive/folders/1PPsneopPecxJzIBDI6RXsF3WdwD_9gXA).
Retrieved files are retained under the ignored directory
`data/raw/national_pilot/2026-10-04-recovery/`. No remaining SE or Tasmania
shard was submitted during this diagnostic checkpoint.

At the original handoff, browser observation remained available but clicks
returned `noWindowsAvailable`; no unsafe fallback input was sent. The user later
submitted the tasks manually. The status reviewed above supersedes that earlier
operational state.

The metadata task is heavier than expected for a table-only diagnostic.
Investigate boundary intersection/union complexity and source-filter geometry
before scaling this design or retrying it; 1,400 output points do not by
themselves guarantee a cheap upstream Earth Engine computation.

### Fine-shard runtime benchmark started 2026-10-05

`analysis/gee/national_recovery_shard_benchmark_20261005.js` preserves the
original frames, random points, seeds, weights, 10 m EPSG:3577 grid, years and
measurements, but tests smaller processing footprints. Only two benchmark
exports were submitted; no additional recovery cells were started:

- `SE_FINE_04_01`: 144–146.5°E, 37.5–35°S, with 6 planned original SE points.
  Task `SSKNY2TYXULBNDWZWD4IXJ35` completed on its first attempt in about
  5 minutes after starting at 2026-10-05 02:59:47 +1100. Final batch usage was
  1,312.5271 EECU-seconds, and it produced all 6 expected rows.
  The rows have unique point IDs and sampled cells, finite distances, binary
  validity flags, no distance sentinels, no WorldCover class 0 or 80 values,
  endpoint-vector identity within 8.61 × 10^-16, and no overlap with `SE_03`.
  File size is 2,877 bytes and SHA-256 is
  `1472b182ad48a6e4a429ff6b1bc311bd8874c3054b2580c80eab63dea71f7fb3`.
- `TAS_FINE_01_01`: 144.5–146°E, 43–42°S, with 21 planned original Tasmania
  points. Task `S7GSWDRU7GGNAC5AU5P7NXL3` completed on its first attempt in
  about 14 minutes after starting at 2026-10-05 03:00:13 +1100. Final batch
  usage was 4,103.4409 EECU-seconds. Its CSV contains all 21 expected rows,
  21 unique point IDs and 21 unique sampled cells, with finite distances,
  binary validity flags, no distance sentinels, no WorldCover class 0 or 80
  values, and endpoint-vector identity within 1.74 × 10^-15. It has no
  overlap with `TAS_03`. File size is 9,541 bytes and SHA-256 is
  `2130ffcdaeeb7fe5628482e446e7da8c15df66d98053b53fdb4f37bd6afe0867`.

Outputs target the Drive folder
[`AusHabitat_Pilot_20260930_Recovery_20261005`](https://drive.google.com/drive/folders/1fIkS2YpFUNsjB0FvapMncB6cVnYMqqmb).
Retrieved files are retained under the ignored directory
`data/raw/national_pilot/2026-10-05-benchmark/`. The Southeast cell is a bounded
interior contrast to the completed coastal `SE_03` cell. The Tasmania cell is
an unprocessed part of the former `TAS_00` footprint and tests a 1.5 x 1 degree
partition instead of the expensive 3 x 2 degree design. Completion alone is
not acceptance: both CSVs were retrieved and passed the specified checks.
Together, the completed original strata and verified recovery outputs now
cover 1,096 of the 1,400 planned points, leaving 304.

### Fine-shard recovery inventory — 2026-10-05

`analysis/gee/national_recovery_fine_inventory_20261005.js` reconstructs the
same original SE and Tasmania point collections and counts the remaining points
in a complete non-overlapping fine grid. It creates no exports. The script was
also saved and run as `AusHabitat_recovery_fine_inventory_20261005` in Earth
Engine. The live console resolved a 38-cell candidate inventory and the full
ordered count vector. The totals are exactly 192 pending SE points and 112
pending Tasmania points, agreeing with the original samples minus the four
verified recovery outputs.

The reviewed inventory is recorded in
`Documentation/national_recovery_fine_inventory_2026-10-05.csv`. Eight cells
contain no original points and must not become export tasks; 30 non-empty cells
contain all 304 remaining points. The largest SE cell contains 13 points. The
largest Tasmania cell contains 42 points, so the successful 21-point Tasmania
benchmark supports the finer geometry but does not prove that every remaining
cell will have the same runtime. No recovery export was created or submitted
during this inventory step.

`analysis/gee/national_recovery_fine_exports_20261005.js` is the staged export
script. Its hard allowlist is limited to two cells and rejects unknown names or
more than two entries. The initial proposed batch is the maximum point-count
cell in each grid: `SE_FINE_05_02` (13 points) and `TAS_FINE_02_01` (42 points).
This is a deliberate upper-load test for the accepted cell geometries, not a
claim that point count alone predicts Earth Engine cost. At this checkpoint the
script is prepared locally; the two task definitions have not been created or
submitted in Earth Engine.

The script was subsequently saved as
`AusHabitat_recovery_fine_exports_20261005`, parsed successfully, and created
exactly the two allowlisted task definitions. Both were submitted on their
first attempts on 2026-10-05; no other recovery task was submitted:

- `AU_20260930_recovery_SE_FINE_05_02`, task
  `JSGHG4LSCHH3C72IMRKYUXJI`, started at 12:19:06 +1100.
- `AU_20260930_recovery_TAS_FINE_02_01`, task
  `EGINHY3BB36FVCLI25SBSDD5`, started at 12:19:31 +1100.

Both completed on their first attempts and their original Drive CSVs were
retrieved into the ignored directory
`data/raw/national_pilot/2026-10-05-recovery/`:

- `SE_FINE_05_02` completed in 6 minutes with 2,494.9551 EECU-seconds. Its
  13 expected rows have 13 unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels, no WorldCover class 0 or 80 values, and
  endpoint-vector identity within 1.64 × 10^-15. It does not overlap the
  earlier SE recovery outputs. File size is 5,934 bytes and SHA-256 is
  `fbec6536a9c10ad3eca3ec62b2e1476c09be5f4cc4fe68d6803acfe8969f3149`.
- `TAS_FINE_02_01` completed in 40 minutes with 8,049.9019 EECU-seconds. Its
  42 expected rows have 42 unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels or WorldCover class 0 values, and
  endpoint-vector identity within 1.92 × 10^-15. Three points have static
  WorldCover class 80; this context is retained and is not treated as a failed
  observation. It does not overlap the earlier Tasmania recovery outputs. File
  size is 18,727 bytes and SHA-256 is
  `e0694e22c0fc0b3d89f47324bfefc0e54f48bc099c808e6f15e606564f80aea4`.

Verified coverage is now 1,151 of 1,400 planned points. The 28 remaining
non-empty cells contain 249 points: 179 SE and 70 Tasmania. The next staged
allowlist is `SE_FINE_00_03` (13 points) and `TAS_FINE_02_00` (28 points), the
largest remaining point-count cell in each stratum.

The updated cloud script resolved those same planned counts and created only
the two allowlisted task definitions. Both were submitted on their first
attempts on 2026-10-05; no other recovery task was submitted:

- `AU_20260930_recovery_SE_FINE_00_03`, task
  `NX6XSAPDIDVU2HDQIHPIYSIR`, started at 13:08:34 +1100.
- `AU_20260930_recovery_TAS_FINE_02_00`, task
  `RFO7IWL3BYQ6GVHGAY4Q72KM`, started at 13:08:54 +1100.

Both completed on their first attempts and their original Drive CSVs were
retrieved into the ignored recovery directory:

- `SE_FINE_00_03` completed in 14 minutes with 3,159.3628 EECU-seconds. Its
  13 expected rows have unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels or WorldCover class 0 or 80 values, and
  endpoint-vector identity within 9.72 × 10^-16. It does not overlap any
  earlier SE output. File size is 5,965 bytes and SHA-256 is
  `2b82e8b6dd8dd44b320dc129877409e87fe73bcfd729ad88764619d253feb8f6`.
- `TAS_FINE_02_00` completed in about 1 hour with 5,408.2764 EECU-seconds. Its
  28 expected rows have unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels or WorldCover class 0 or 80 values, and
  endpoint-vector identity within 1.73 × 10^-15. It does not overlap any
  earlier Tasmania output. File size is 12,604 bytes and SHA-256 is
  `de8ac40525083e0d8fd2c2f75da6b86858bde1414d429030c34f733917b32cf3`.

Verified coverage is now 1,192 of 1,400 points. The remaining 26 non-empty
cells contain 208 points: 166 SE and 42 Tasmania. The next staged allowlist is
`SE_FINE_01_03` (12 points) and `TAS_FINE_01_02` (28 points).

The cloud script was updated to that allowlist and created exactly those two
task definitions. Both were submitted on their first attempts on 2026-10-07;
no other recovery task was submitted:

- `AU_20260930_recovery_SE_FINE_01_03`, task
  `FY6TKEJD2WSYWTVBPI4H6LHS`, started at 01:51:45 +1100.
- `AU_20260930_recovery_TAS_FINE_01_02`, task
  `7SMLZPTXJI3D7ZZDCV26DVWF`, started at 01:52:01 +1100.

Both tasks completed on their first attempts and their original Drive CSVs
were retrieved into the ignored recovery directory:

- `SE_FINE_01_03` completed in 5 minutes with 2,529.3005 EECU-seconds. Its
  12 expected rows have unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels or WorldCover class 0 or 80 values, and
  endpoint-vector identity within 1.56 × 10^-15. It does not overlap any
  earlier verified output. File size is 5,498 bytes and SHA-256 is
  `713da43cec32a6f2a8f22effaa5d50ff53437a8d7eb0dcbccbcf643beb1d5a55`.
- `TAS_FINE_01_02` completed in 18 minutes with 6,489.5771 EECU-seconds. Its
  28 expected rows have unique point IDs and sampled cells, finite distances,
  binary validity flags, no sentinels or WorldCover class 0 or 80 values, and
  endpoint-vector identity within 1.73 × 10^-15. It does not overlap any
  earlier verified output. File size is 12,626 bytes and SHA-256 is
  `4e9342ae623df78782f03dd0547e704988f87b2857c826afcac6ca7c57c690bd`.

Verified coverage is now 1,232 of 1,400 points, with 1,232 unique point IDs
and sampled cells. The remaining 24 non-empty cells contain 168 points: 154 SE
and 14 Tasmania. The next staged allowlist is `SE_FINE_04_02` (12 points) and
`TAS_FINE_03_01` (9 points), the largest remaining point-count cell in each
stratum (with the SE choice taken first among the tied 12-point cells).

On 2026-10-07 the saved allowlist was confirmed in the Earth Engine editor and
created exactly those two task definitions. No other recovery cell was
submitted:

- `AU_20260930_recovery_SE_FINE_04_02`, task
  `L4AEEWUPXNX2DI2TTXO5NBJH`, started at 02:33:06 +1100 and completed on its
  first attempt in 10 minutes using 2,573.6108 EECU-seconds. The original Drive
  CSV was retrieved and its 12 expected rows have unique point IDs and sampled
  cells, finite distances, binary validity flags, no sentinels or WorldCover
  class 0 or 80 values, correct stratum, recovery part and bounds, and
  endpoint-vector identity within 1.59 × 10^-15. It does not overlap any
  earlier verified output. File size is 5,485 bytes and SHA-256 is
  `0d8ef36c10e6c2ea819f121c4720271f675e683e52cdc11e2c2b6323da6fd9d7`.
- `AU_20260930_recovery_TAS_FINE_03_01`, task
  `MCZLLQTUONMLFG2QHNK23BFC`, submitted at 02:45:51 +1100 and started at
  02:45:55 +1100. It completed on its first attempt in 9 minutes using
  2,933.9912 EECU-seconds. The original Drive CSV was retrieved, but it failed
  the point-identity gate: it contains 10 rows rather than the inventoried 9,
  and `TAS_46` duplicates an earlier point ID while carrying a different
  original coordinate and sampled cell. The other numerical checks passed,
  including finite distances, binary validity flags, no sentinels or
  WorldCover class 0 or 80 values, correct bounds, and endpoint-vector identity
  within 1.99 × 10^-15. File size is 4,674 bytes and SHA-256 is
  `494ee140471469883e7dd8a4954fc4808943b9a0b11e82b914fcea39cb20f8c6`.

Verified coverage remains 1,244 of 1,400 points, with 1,244 unique point IDs
and sampled cells. The Tasmania output is quarantined and does not contribute
to those figures. No further recovery cell should be submitted until a frozen
point manifest establishes whether repeated `randomPoints` evaluation changed
the point identity-to-coordinate mapping.

The Tasmania point-manifest diagnostic was then saved and run as
`AusHabitat_recovery_point_stability_20261007`. It exported two independent
evaluations of the same 200-point definition, with the same frame, seed and
requested count, and no embedding calculation. Both exports contain 200
unique IDs and 200 unique coordinates, but they do not preserve the same
ID-to-coordinate mapping. `TAS_46` moves between `(147.992371, -42.497889)`
in realisation A and `(146.038148, -43.501251)` in realisation B, approximately
2.20 degrees apart. `TAS_6` also differs by about 3.81 x 10^-7 degrees, but
both coordinates fall in the same 10 m EPSG:3577 cell. All other differences
are below 10^-8 degrees.

Realisation B is the provisional canonical Tasmania manifest because it
preserves the coordinates of all 186 previously verified Tasmania IDs to the
10 m analysis support; realisation A conflicts materially at `TAS_46`.
The previously quarantined `TAS_FINE_03_01` output matches A exactly. Against
canonical B, nine of its rows are valid missing IDs and its `TAS_46` row is a
non-canonical duplicate that must be excluded. This raises reconciled verified
coverage to 1,253 of 1,400 points, leaving 142 SE points and five Tasmania
points (`TAS_25`, `TAS_39`, `TAS_55`, `TAS_103`, and `TAS_148`). The five
Tasmania coordinates must be recovered from the frozen manifest, not by
calling `randomPoints` again.

This diagnostic demonstrates instability in the observed mapping from Earth
Engine-generated feature IDs to random-point coordinates across separate
evaluations. It does not show a problem with the embedding-distance values.
The SE point collection must pass the same stability and reconciliation gate
before further SE recovery exports are submitted.

The equivalent SE diagnostic was saved and run as
`AusHabitat_recovery_se_point_stability_20261007`. The two tasks completed on
their first attempts:

- `AU_20260930_SE_POINT_STABILITY_A`, task
  `5LMA7637J6UV4LNKNNF3NGRN`, produced Drive file
  `1tESuezkCWctZxuhDtSRiMF2RK-6Z9WEK`;
- `AU_20260930_SE_POINT_STABILITY_B`, task
  `RDUPE6BNPH3ZYCH3B63ZREWU`, produced Drive file
  `1JGGaXjaWjLytMSxLVTjeX6wSGOkIh7ER`.

Each file contains 200 unique point IDs and 200 unique coordinates. A and B
are identical for every point ID and coordinate. All 58 previously verified
SE rows agree with the diagnostic manifest within 3.78 x 10^-10 degrees, with
no material identity conflict. SE realisation A is therefore the canonical SE
manifest. Its local CSV is 11,973 bytes with SHA-256
`f33c7e3e74ff09984f0d0d2d0d71242e0e4d726c1e369633cfc8bbb150a91516`;
realisation B is also 11,973 bytes with SHA-256
`92c85de2fc6dfba9d7666853ec0a7bf1e6d881f2aef274b517178320cdf38b7d`.
The hashes differ only because the `realisation` column is A versus B.

The canonical SE manifest has 58 verified and 142 missing IDs. The largest
remaining fine cell is `SE_FINE_03_03` with 12 points. The next recovery code
must construct its input features from the canonical exported coordinates;
it must not call `randomPoints` again.

`analysis/gee/national_frozen_manifest_recovery_20261007.js` is the prepared
first fixed-coordinate recovery batch. It embeds the 12 canonical coordinates
for `SE_FINE_03_03` and the three canonical coordinates for
`TAS_FINE_01_03`, records the manifest date and hashes in the source, and
creates exactly two Drive-export tasks. A local exact-string check confirmed
all 15 embedded IDs and coordinates match their canonical CSVs. The script was
saved in Earth Engine as `AusHabitat_frozen_manifest_recovery_20261007`, and
both tasks were submitted on 2026-10-07:

- `AU_20260930_frozen_recovery_SE_FINE_03_03`, task
  `DYZC24QKRRBVFQMMJBQLUI7T`, started at 12:52:52 +1100 and was running on
  its first attempt at this checkpoint;
- `AU_20260930_frozen_recovery_TAS_FINE_01_03`, task
  `5N3XQASGO25EWHNRFMZOXRWC`, started at 12:53:39 +1100 and was running on
  its first attempt at this checkpoint.

Neither export contributes to verified coverage until its original Drive CSV
has been retrieved and passes point-identity, bounds, validity, finite-value,
sentinel, land-cover and endpoint-vector QA.

### Frozen-manifest completion and 1,400-point reconciliation

Both first fixed-coordinate exports completed and passed their identity and
numerical gates. The complete frozen-manifest remainder was then exported as
20 spatial tasks from
`analysis/gee/national_frozen_manifest_remaining_20261007.js`. All 20 tasks
completed on their first attempt on 2026-10-07. Their original Drive CSVs were
retrieved to `data/raw/national_pilot/2026-10-07-frozen-remaining/`; the 132
rows have 132 unique IDs and sampled cells, exact frozen-manifest coordinates,
finite distances, binary validity flags, no sentinels, and endpoint-vector
identity within 2.35 x 10^-15.

`analysis/tools/national_pilot_completion.py` records the full accepted input
lineage and applies one explicit exclusion: the non-canonical `TAS_46` row from
the quarantined randomPoints realisation-A output. The reconciled result passes
all gates:

- 1,400 accepted rows, 1,400 unique point IDs and 1,400 unique sampled cells;
- 200 accepted points in each of the seven geographic strata;
- exact agreement with the canonical 1,400-ID set;
- all eight annual validity flags equal to one for all 1,400 rows;
- finite endpoint and annual distances with no sentinel values;
- maximum endpoint-vector identity error 2.35 x 10^-15;
- exact frozen-recovery coordinates within 10^-12 degrees; and
- one documented historical coordinate exception, `TAS_6`, differing from
  canonical realisation B by 3.49 x 10^-7 degrees while remaining in the same
  10 m analysis cell. This is below the explicit 10^-6-degree historical
  reconciliation tolerance and is not treated as a new identity conflict.

The ignored local outputs are under
`data/processed/national_pilot/2026-10-07/`. They include the accepted sample,
the completion QA record, the threshold-sensitivity table and its weighted
summary.

### First area-weighted threshold-sensitivity result

The first complete-sample calculation uses the seven stratum frame areas and
200 points per stratum. Uncertainty is represented by 10,000-replicate
stratified nonparametric percentile bootstrap intervals with fixed seed
20261007. These are design-based sampling uncertainty summaries; they do not
measure model accuracy, causal certainty, boundary uncertainty or embedding
product error.

All 1,400 points have common eight-year embedding support. ESA WorldCover 2021
labels 11 sampled cells as class 80 (permanent water); no point is class 0.
The WorldCover-known, non-water contextual subset contains 1,389 points and
represents 99.68% of the design-area weight. WorldCover is contextual evidence,
not a perfect land mask or validation label.

For all boundary sample points, the weighted sensitivity results are:

| Strict threshold | Endpoint 2017-2024 | Any annual interval |
| ---: | ---: | ---: |
| > 0.35 | 32.86% (29.98-35.78%) | 49.10% (46.06-52.06%) |
| > 0.40 | 17.98% (15.60-20.41%) | 34.06% (31.21-36.88%) |
| > 0.45 | 10.44% (8.60-12.35%) | 23.56% (21.08-26.12%) |
| > 0.50 | 5.13% (3.85-6.47%) | 15.76% (13.67-17.87%) |
| > 0.55 | 2.59% (1.69-3.56%) | 10.24% (8.50-12.01%) |

At the Bass Coast comparison rule of strict distance `> 0.45`, annual weighted
exceedance is 3.34%, 4.82%, 6.78%, 5.71%, 6.11%, 12.62% and 4.86% for the seven
intervals from 2017-2018 through 2023-2024. The larger 2022-2023 estimate is a
signal to investigate, not evidence of a confirmed national event or cause.
Removing WorldCover class 80 changes the `> 0.45` endpoint estimate only from
10.44% to 10.48% and the any-annual estimate from 23.56% to 23.55%.

The steep change across the tested thresholds is direct evidence that the Bass
Coast value must not be adopted nationally without further scientific review.
These estimates describe a bounded stratified sample over the provisional
candidate boundary, not wall-to-wall national hot-spot prevalence.

## Completed local measurements

`analysis/tools/national_pilot_file_qa.py` runs inside the existing `.venv`.
Inputs are under `data/raw/national_pilot/2026-09-30/`; outputs are under
`data/processed/national_pilot/2026-09-30/`. These data remain ignored by Git.
`file_qa.json` records hashes, dimensions, valid counts, transforms, and sizes.

### Lossless storage benchmark

The previous central-arid endpoint export was retrieved through Google Drive
as the original TIFF, not a preview. Exact size is **20,876,147 bytes**
(20.88 decimal MB; approximately 19.91 MiB). This explains the earlier rounded
Drive display of 19.9 MB. Grid: 1,847 × 2,048, Float32, EPSG:3577, 10 m,
`-9999` nodata, 3,651,993 valid values out of 3,782,656 positions.

| Encoding | Bytes | Saving relative to original |
| --- | ---: | ---: |
| Original GEE LZW COG | 20,876,147 | — |
| DEFLATE, floating-point predictor | 14,614,867 | 29.99% |
| ZSTD, floating-point predictor | 14,431,562 | 30.87% |

Both copies preserve base pixels bit-for-bit, CRS, transform, datatype, nodata,
and overview levels. Existing overviews were reused, not regenerated. GDAL
reports COG layout; a separate HTTP range-read/serving test has not been run.
This compares actual file encodings, not just codec algorithms: block/layout
settings can also affect size. One arid tile does not represent national
compressibility or storage performance.

The four 2026-09-30 eight-band tiles are now also measured. Original LZW sizes
range from 45,570,532 to 46,416,616 bytes. Lossless ZSTD copies range from
30,825,718 to 30,906,465 bytes, saving 32.36–33.57%; DEFLATE is similar. Base
pixels, CRS, transform, datatype, nodata and overviews were preserved in the
local comparisons. This is a useful multi-environment consistency result, but
four 100 km² locations are still not a national storage census.

All four files are **1,001 × 1,001 pixels**, not the 1,000 × 1,000 dimensions
recorded in `tile_manifest.geojson`; their transforms remain EPSG:3577 with
10 m pixels. Region-to-grid snapping admitted one extra row and column, with
the extra edge placement varying by tile. The manifest is therefore inaccurate
by one row and one column and its recorded bounds do not exactly match the
files. Before production tiling, define exports by a tested pixel-aligned
convention and verify dimensions, adjacency and duplicate edge pixels
automatically.

Using the old 365.656876 km² footprint and 7,670,738.755 km² candidate area,
naive extrapolation is **0.438 TB per band / 3.50 TB for eight bands** for the
original, or **0.303 TB / 2.42 TB** for ZSTD. These correct the rounded-byte
arithmetic in the historical September 21 record; they remain scenarios,
not a national capacity estimate. Additional metrics, contextual rasters,
imagery, temporary data, overviews, backups and retained versions are excluded.

### Coarse boundary screening

Downloaded a second outline from the [GA landmass reference layer](https://services.ga.gov.au/gis/rest/services/Oceanic_Shoals_Samples/MapServer/12).
Its metadata identifies a 1:1-million Global Map 2001 coastline source, with
© Commonwealth of Australia (Geoscience Australia) 2016, CC BY 4.0. This is
an older, coarse comparison source, **not** an adopted production boundary.
The largest polygon of each of eight state/territory features was retained;
Lord Howe was excluded. Selecting two globally largest polygons would be
incorrect because this dataset is split by state.

Pixel-centre rasterization on a shared EPSG:3577 1 km grid gave:

- Candidate GAUL area: 7,656,144 grid km².
- GA comparison: 7,657,560 grid km².
- Candidate-only: 2,299 km²; GA-only: 3,715 km²; symmetric disagreement: 6,014 km².

These are coarse rasterized areas, not replacements for geodesic area figures.
Similar totals can conceal local coastline differences. Neither source is
ground truth. Inspect disagreement locations and obtain a suitable licensed
coastline before a 10 m national land mask is frozen; also resolve inland-water
policy, tidal areas and static WorldCover masking.

## New source-data/storage finding

Google's [source COG documentation](https://developers.google.com/earth-engine/guides/aef_on_gcs_readme)
describes publicly available 64-band **signed 8-bit encoded** COGs in
`gs://alphaearth_foundations`, with nonlinear de-quantization and `-128` nodata.
The provider-pays statement is dated July 2026. Therefore the previous
**157 TB** calculation is specifically dense **Float32 expansion** for eight
years; it is not the native source download footprint. Dense one-byte storage
would be roughly 39.3 TB before compression, overviews, masks and tiled extent;
actual source-object sizes require an intersected inventory. Do not calculate
embedding distances directly on the encoded integers.

There is also a source-documentation discrepancy: the public-bucket guide
lists 2017–2025, while the [Earth Engine catalogue](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL)
still lists 2017–2024. The current pilot intentionally retains 2017–2024.
The catalogue reports dataset version 1.1 and a regenerated 2017 layer; actual
exported source properties must be checked before asserting version equality
with the frozen Bass Coast files. Do not silently extend the study period.

## Storage decision remains open

Prefer retaining source embeddings remotely and downloading only the necessary
derived products and active working tiles. Google supports exports to
[Drive and Cloud Storage](https://developers.google.com/earth-engine/guides/exporting_images).
A team SharePoint/OneDrive location may hold approved immutable deliverables or
archives, but sync is not a compute backend. Microsoft's [published limits](https://support.microsoft.com/en-us/onedrive/restrictions-and-limitations-in-onedrive-and-sharepoint)
include a 250 GB individual-file limit and warnings about large item counts.
Actual tenant quota, retention, ownership, download/hydration behaviour and
transfer reliability have not been tested here.

The laptop reported approximately 359 GiB available. It can support a bounded
working cache, not several TB of fully hydrated data. Analysis outputs can stay
under ignored project data directories while inputs live elsewhere, but local
scratch/cache demand must still be budgeted. Do not sync rapidly changing
temporary processing files. No OneDrive transfer, cloud bucket or infrastructure
was configured by this evidence pilot. A subsequent bounded RMIT
Teams/SharePoint test passed a 138 MB checksum-verified round trip on
2026-10-28; see `10_STORAGE_RETENTION_AND_TEAMS_TEST_2026-10-28.md`. That test
does not authorize national production or establish multi-terabyte performance.

## Validation and next action

Core Bass Coast transfer verification passed. Python is the project
`.venv/bin/python`, version 3.12.12; all 18 pinned requirements match, and
`pip check` reports no broken requirements. Its non-fatal cache-permission
warning did not affect validation. No packages were installed.
The new Python tool compiled, the GEE JavaScript parsed successfully, and
`git diff --check` passed. No commit or push was made.

The scientific equivalence, recovery, identity and complete-sample gates have
passed. The bounded evidence pilot now contains all 1,400 planned observations,
and the first area-weighted threshold-sensitivity summaries are complete. No
national threshold has been selected. The next decision gate is scientific
review of the sensitivity pattern, especially the 2022-2023 interval, together
with the boundary/mask policy and revised source-object/storage scenarios.
Discuss those findings before selecting a threshold, storage platform or full
national-processing milestone. Hot spots remain embedding-change signals; DEA
and NDVI provide supporting context, not causal event labels or perfect ground
truth.
