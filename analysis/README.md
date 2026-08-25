# AusHabitat Analysis Source

This directory contains the analysis code retained for project handover.

## Contents

- `notebooks/`: Phase 1 raster inspection and Phase 2 pixel sampling notebooks.
- `scripts/`: local Python pipelines for DEA, NDVI, map preparation and reports.
- `gee/`: retained optional Sentinel-2 visual export and its provenance note.
- `reference_outputs/`: small summaries from verified runs; bulk outputs and
  rasters are intentionally excluded.
- `study_design/`: retained NDVI comparison design.

Read `../CODEX_HANDOVER.md` and `../Documentation/04_DATA_AND_REPRODUCTION.md`
before running these files. Most scripts expect transferred local data folders
at the repository root.

## Environment

The last verified local environment used Python 3.12 with the versions recorded
in `requirements.txt`. A clean virtual environment is recommended; do not copy
the old `.venv` between computers.

## Source status

The scripts are snapshots of the working Bass Coast implementation. Phase 3,
Phase 5, Phase 9 and Phase 10 support checkpointing or self-tests. The notebooks
retain their Colab/Drive-oriented paths and may need a project-path edit for a
fully local rerun.

`scripts/prepare_app_data.py` rebuilds the browser-ready `public/data` package
from transferred Phase 9 and Phase 10 outputs. It rewrites generated browser
assets, so commit or back up the current package before using it.
