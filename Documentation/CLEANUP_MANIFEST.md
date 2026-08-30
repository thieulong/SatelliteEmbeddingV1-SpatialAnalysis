# Consolidation and Cleanup Manifest

Consolidation date: 2026-08-30

## Objective

Replace the mixed experimental workspace with a migration-ready repository that
contains one canonical pipeline, one data layout, the current application, and
the latest deliverables.

## Retained in the canonical project

- Current GitHub Pages application and browser-ready map package.
- Two verified notebooks and their builders.
- Canonical and predecessor Earth Engine embedding workflows plus the optional
  Sentinel-2 visual export.
- Eight-stage local analysis pipeline.
- Compact reference outputs supporting reported results.
- Authoritative embedding metric rasters.
- Full and review sampling tables.
- Final sampled DEA history and enriched-point products.
- Final DEA wall-to-wall summary tables.
- Final NDVI pilot products.
- Final 30 m map-grid and region-context products.
- Optional annual Sentinel-2 visual exports.
- Latest peer-facing and client-facing PowerPoint files.
- Technical LaTeX report source, figures, and PDF.
- Optional Esri/external-stack source under `research/`.

## Deliberately excluded from the canonical project

- Python virtual environment and package caches.
- `.DS_Store`, `__pycache__`, Matplotlib caches, temporary directories, and
  Office lock files.
- Notebook and script copies formerly scattered at repository root.
- The superseded nested `bass-coast-change-map/` working copy. The deployed
  root application is authoritative.
- Phase 3 small review-run output duplicated by the completed full-sample run.
- Phase 3 completed checkpoints and redundant raw probe table.
- Phase 4 and Phase 6 generated report working folders; final deliverables and
  compact reference results are retained.
- Phase 5, Phase 8, and Phase 10 completed checkpoints.
- Phase 7 Esri batch, concurrency, smoke-test, and full generated output
  folders. Source and compact reference results remain under `research/` and
  `analysis/reference_outputs/`.
- Phase 9 self-test, external-smoke-test, and test-enrichment tables.
- Rendered slide inspection folders and `.inspect.ndjson` logs.
- External-stack benchmark generated outputs.
- The old 6+ GB divergent Git object database.

## Safety strategy

The pre-consolidation workspace is moved to a dated sibling archive rather than
immediately erased. Required data are moved from that archive into the new
`data/` structure. The remaining archive is rollback-only and may be deleted
after the new computer passes `MIGRATION_CHECKLIST.md`.

No file in the archive should be copied back merely because its old phase name
looks newer. Compare it against this manifest and the canonical source first.
