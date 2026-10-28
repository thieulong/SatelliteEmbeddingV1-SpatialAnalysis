# Storage retention and RMIT Teams test — 2026-10-28

## Decision boundary

This record defines what should be retained and reports a bounded storage
round trip. It does not authorize wall-to-wall national exports, designate
SharePoint as an active compute filesystem, or select a national threshold.

The Team is intentionally RMIT-public. Its SharePoint site is
`GoogleEarthSatelliteDATA`, library `Shared Documents`, channel folder
`General`. SharePoint Storage Metrics reported 25,600 GB free of 25,600 GB at
the start of the test. This is the site's configured maximum; RMIT's tenant
pool, retention policy and permission to consume multiple terabytes remain
administrative constraints.

## Retention matrix

| Product | Authoritative/working location | Teams retention | Reason |
| --- | --- | --- | --- |
| Google Satellite Embedding source bands | Earth Engine/provider cloud | Do not duplicate by default | Largest input; retain remotely and preserve source/version provenance |
| Bass Coast 10 m embedding metrics | Local working copy plus verified Team release | Required | Authoritative detection inputs for the frozen regression baseline |
| Approximately 30 m common-support rasters and sampling tables | Local working copy plus verified Team release | Required | Reproduction of integration, regions and summaries |
| DEA Level 3/4 and GeoMAD NDVI derived context | Local working copy plus verified Team release | Required | Supporting contextual evidence; not validation labels |
| National 1,400-point raw and processed pilot outputs | Local ignored data plus verified Team release | Required | Reproduce the bounded national evidence result |
| Sentinel-2 annual display imagery | Local optional data; separate Team archive if retained | Optional, separate from core | Visual context only; not an input to embedding detection |
| National wall-to-wall derived rasters | Not yet produced | Pending a production decision | Requires final grid, masks, tiling, threshold policy and capacity test |
| Web-ready tiles and compact application data | Web/object-serving location plus Team release | Required per published version | Reproduce the public product without storing compute scratch |
| Temporary exports, caches, virtual environments and recomputable scratch | Local/cloud scratch | Do not retain | High churn, no archival value |
| Code, documentation and small manifests | Git | Git is authoritative; Team copy optional | Versioned review and reproducibility |

Teams/SharePoint is initially an institutional archive for completed,
immutable, checksum-verified products. Do not run raster processing directly
against the synced folder. Do not move the Git checkout or `.venv` into it.

## Folder structure

The following folders were created under `General`:

```text
00_Admin/
01_Manifests/
02_Verified_Releases/
  Bass_Coast/
  National_Pilot/
  National_Production/
03_Contextual_Data/
04_Web_Products/
90_Transfer_Staging/
```

## Initial round-trip test

`90_Transfer_Staging/AusHabitat_Storage_Readiness_Test_2026-10-28`
contains five bounded-pilot lossless ZSTD COGs, five QA/summary files, a README
and a TSV manifest. The ten manifested data files total 137,889,862 bytes.

All source byte counts and SHA-256 values passed before upload. The complete
folder structure, all five rasters and all five QA files were then observed in
the SharePoint web interface. The representative file
`central_arid_endpoint_2017_2024_10m_epsg3577_cog_zstd.tif` was downloaded
through SharePoint and matched the original exactly:

- bytes: 14,431,562;
- SHA-256:
  `78be56e2e0e94cbdc7433761e0fec621f536dcb8d7ac522c8783986fceb82aef`.

The round trip therefore passed. A durable copy of the result is in the Team's
`00_Admin/Storage_Readiness_Test_2026-10-28.md`.

## Medium-volume retained-product test

The genuine retained-product test used 201 Bass Coast files totalling
6,830,452,076 bytes (6.36 GiB). It included the source embedding metrics and
the processed DEA sample, common-grid, regional-context, sampling, raster-QA,
DEA wall-to-wall and NDVI-pilot trees. Optional Sentinel-2 annual display
imagery was deliberately excluded because it is contextual imagery rather
than a detection input and requires a separate retention decision.

The local copy into the OneDrive File Provider took 31.28 seconds. Cloud
convergence was checked separately: SharePoint displayed the release README,
manifest and data hierarchy, including all 17 files in the largest DEA sample
folder after the final two large CSVs completed upload. A 333,588,134-byte
GeoTIFF was then downloaded through the SharePoint interface and matched the
pre-transfer manifest exactly:

- file: `data/raw/embedding_metrics/basscoast_annual_change_2017_2018.tif`;
- SHA-256:
  `35446bc24a0dc87814df27cfed64422a812e0517e24ce3f40ed1310316b9bd2c`.

The medium-volume round trip therefore passed. The immutable package was
promoted from transfer staging to
`02_Verified_Releases/Bass_Coast/Bass_Coast_Regression_2026-09-03`.

## National evidence-pilot archive

The completed national evidence pilot was packaged separately at
`02_Verified_Releases/National_Pilot/National_Evidence_Pilot_2026-10-28`.
It contains the raw and processed national-pilot trees, comprising 72
manifested files and 531,386,460 bytes, plus its README and manifest. Both the
staging copy and the OneDrive copy passed byte-count and SHA-256 verification.
macOS File Provider checks then confirmed that all 74 package objects had
settled with no items still syncing.

This archive supports the bounded 1,400-point evidence result. It is not a
wall-to-wall national raster release and does not select a national hot-spot
threshold.

After final SharePoint inspection, the Bass Coast release, national-pilot
release and initial readiness-test package were returned to online-only status
with OneDrive **Free Up Space**. Finder reported each folder as `Not
Downloaded`, and each package reported 0 B local disk usage while remaining
available in SharePoint.

## Remaining storage gates

The tests do not establish sustained multi-terabyte transfer performance, very
large item-count behaviour, version-history overhead, retention/restore policy,
or RMIT tenant-pool availability. Those administrative and production-scale
gates remain unresolved. Do not manufacture bulk by duplicating files merely
to reach a target size.
