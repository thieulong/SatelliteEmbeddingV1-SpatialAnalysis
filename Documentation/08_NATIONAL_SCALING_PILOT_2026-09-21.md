# Australia mainland-and-Tasmania scaling pilot — 2026-09-21

This is an exploratory run record, **not** a national analysis, validated
threshold, storage design, or change to the frozen Bass Coast regression
baseline. The user-approved scope was boundary inspection, seven annual
intervals in contrasting small windows, and one derived raster export.

## Provenance and scope

- Repository `main` at run start: `4fb9f9e951129a663261b8e742b3aa85231ddecb`.
  These pilot files are new working-tree additions; the run-start commit does
  not contain them. Future reruns must record their actual code commit.
- Earth Engine project: `satellite-embedding-analysis`.
- Google Satellite Embedding V1 annual collection:
  `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, years 2017–2024; 64 bands at 10 m.
- Water exclusion follows the Bass Coast prototype's
  `ESA/WorldCover/v200` class `Map != 80`. This is not a complete national
  land/water or coastline validation.
- Annual distance is Euclidean distance between consecutive 64-dimensional
  mosaics. The exploratory hot comparison is strictly `distance > 0.45`, as in
  Bass Coast. Endpoint distance compares 2017 with 2024.
- Reproducible scripts are under `analysis/gee/national_*_pilot.js`;
  corresponding interactive scripts were saved in the user's Earth Engine
  script repository as
  `AusHabitat_mainland_tasmania_boundary_diagnostic`,
  `AusHabitat_seven_interval_site_pilot`, and
  `AusHabitat_single_tile_export_pilot`.

## Candidate boundary

`FAO/GAUL/2015/level0` filtered to `ADM0_NAME = Australia` had three country
features. Its merged geometry exposed 6,687 polygon components. Ranking by
area and retaining the four largest produced three mainland components and
Tasmania, totalling approximately **7,670,739 km²**. Named-point checks
included Perth, Darwin, Alice Springs, Sydney, Melbourne, and Hobart, and
excluded tested points on Kangaroo Island, Flinders Island, and Norfolk Island.
The exported four-feature pilot asset is
`projects/satellite-embedding-analysis/assets/AusHabitat_mainland_Tas_GAUL2015_pilot_v1`.
Earth Engine task `LUES6OW657KGM45TO6PYH3OU` completed in about 2 minutes
with 12.4664 EECU-seconds.

This is a **candidate** mainland-and-Tasmania mask. Named points and four
largest polygons do not prove a correct coastline, exhaustive island
exclusion, water exclusion, or an appropriate redistribution licence. Review
the [GAUL 2015 catalogue and licence](https://developers.google.com/earth-engine/datasets/catalog/FAO_GAUL_2015_level0)
before adopting or publishing this boundary.

## Seven-interval site diagnostic

Seven approximately 0.1° × 0.1° windows were processed **separately**. For
each window, one approximate 100-point, seed-2026 sample was taken from the
common valid mask of the endpoint and all seven annual distances. Thus each
reported annual fraction uses the same retained sample within a site; it is
not an area-weighted rate. WorldCover water exclusion was applied; the pilot
boundary was not used as the sampling mask, although all windows were chosen
on mainland or Tasmania. The [full interval statistics](national_pilot_site_stats_2026-09-21.csv)
include sample sizes, source tile counts, endpoint p95, annual p95, and each
annual fraction exceeding 0.45.

| Exploratory window | Valid sample | Endpoint p95 | Annual p95 range | Annual `>0.45` fraction range |
| --- | ---: | ---: | ---: | ---: |
| Bass Coast | 100 | 0.479 | 0.326–0.409 | 0–4% |
| Tasmania | 97 | 0.371 | 0.243–0.307 | 0–1.0% |
| Central arid | 100 | 0.518 | 0.245–0.466 | 0–5% |
| Tropical north | 92 | 0.358 | 0.265–0.407 | 0–2.2% |
| Western Sydney | 100 | 0.485 | 0.326–0.487 | 0–8% |
| Southwest WA | 100 | 0.506 | 0.466–0.609 | 11–33% |
| Murray valley | 100 | 0.732 | 0.482–0.661 | 11–48% |

The first attempt to compute all seven windows in one interactive script
returned `Earth Engine capacity exceeded`. Running each separately with
`numPixels: 100` completed. A transient `Cannot perform analysis without auth
token` error during the Southwest WA run resolved after refreshing the Code
Editor and rerunning the saved script. The saved selector-based script now
retains all seven windows but runs one selected window at a time.

The range differences demonstrate why the Bass Coast cutoff must not be
promoted to a national decision threshold without a designed sampling and
validation study. These small convenience samples cannot quantify national
prevalence, determine an optimal threshold, or establish model accuracy.
Embedding hot spots are change signals, **not** confirmed construction,
clearing, degradation, restoration, or other causal events. DEA Land Cover and
GeoMAD NDVI remain contextual evidence, not ground-truth labels.

## One derived raster transfer benchmark

A single central-arid rectangle, `[134.20, -24.20, 134.38, -24.02]`, covered
**365.657 km²**. The exported product is a one-band Float32 2017–2024 endpoint
distance at 10 m, EPSG:3577, cloud-optimized GeoTIFF, with `-9999` nodata.
Both endpoint years had one source tile over this rectangle. The output is in
the [separate pilot Drive folder](https://drive.google.com/drive/folders/1LzcZNoXORGumhpcFQuZPzZoIof5pVji4)
as `central_arid_endpoint_2017_2024_10m_epsg3577_cog.tif`. Drive reported
**19.9 MB**. Earth Engine task `OPY2I7MS2H4J77EFOKBR2GJ3` completed on the
first attempt, starting 2026-09-21 10:47:48 AEST, with approximately **3 min**
runtime and **436.1729 EECU-seconds**. This is a Drive benchmark, not a
OneDrive transfer test.

Naïvely multiplying that one tile's MB/km² by the candidate boundary area
gives **approximately 0.42 TB per one-band layer** or **3.34 TB for eight
layers** (seven annual distances plus endpoint). These are deliberately rough
order-of-magnitude planning figures, **not** a national quote: tile content,
masks, compression, overviews, shoreline overhead, tiling, additional products,
and transfer retries can alter size substantially. If all 64 source bands
were materialized as dense Float32 at 10 m, theoretical storage would be about
**19.6 TB per year**
or **157 TB for eight years before compression and overhead**. Therefore a
10–20 TB allowance is not a safe assumption for local copies of all source
embedding years. The source collection can remain in Earth Engine while only
necessary derived outputs are exported.

## Next technical decision gate

Before any broad export: verify a legally usable and geographically correct
mainland/Tasmania boundary and the land/water mask; define a probability-based
sampling frame stratified by geography and land-cover context; check temporal
coverage, projection and grid alignment; and set explicit tile sizes, retry
rules, output manifests, checksums, storage destination, and spend/stop limits.
Then run a small multi-tile benchmark across contrasting environments.
National threshold estimation, wall-to-wall processing, and web expansion are
separate milestones requiring their own validation and approval.
