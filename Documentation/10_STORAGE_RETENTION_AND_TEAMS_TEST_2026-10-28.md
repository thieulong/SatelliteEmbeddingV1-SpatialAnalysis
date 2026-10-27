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

## Remaining storage gates

The small test does not establish sustained multi-terabyte transfer
performance, very large item-count behaviour, version-history overhead,
retention/restore policy, or RMIT tenant-pool availability. The next storage
test must use a genuine 5–10 GB retained-product package, preserve checksums,
measure transfer time, download at least one representative large object, and
return the verified Team folder to online-only status. Do not manufacture bulk
by duplicating files merely to reach a target size.
