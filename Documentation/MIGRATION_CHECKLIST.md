# Migration Checklist

## On the old computer

- [ ] Confirm all long-running processes have finished.
- [ ] Push the latest Git branch and record the commit hash.
- [ ] Copy the essential local data directories listed in
  `04_DATA_AND_REPRODUCTION.md` to an external drive or object storage.
- [ ] Copy presentations, LaTeX report sources and any unpublished figures if
  they are needed; they are not all part of the deployed branch.
- [ ] Export the original Earth Engine embedding script from the GEE Code Editor.
- [ ] Record any credentials or cloud configuration separately. Never commit
  secret tokens.
- [ ] Keep the old computer unchanged until the new-machine verification passes.

## On the new computer

- [ ] Clone the GitHub repository.
- [ ] Ask the new Codex instance to read `CODEX_HANDOVER.md` and all files under
  `Documentation/` before proposing changes.
- [ ] Copy the large data directories into the repository root.
- [ ] Recreate `.venv`; do not copy the old virtual environment.
- [ ] Install `analysis/requirements.txt`.
- [ ] Run `analysis/scripts/verify_transfer.py --project-root .`.
- [ ] Compile all scripts.
- [ ] Run Phase 5 and Phase 10 self-tests.
- [ ] Run a 10-point Phase 3 network smoke test.
- [ ] Compare smoke-test results and warnings with `analysis/reference_outputs/`.
- [ ] Serve the static app locally and test search, filters, region selection,
  timeline, DEA/NDVI context and all three basemap modes.
- [ ] Confirm the published GitHub Pages URL still works.

## Validation record to create

Create a dated migration note containing:

- operating system and architecture;
- Python, Rasterio and GDAL versions;
- Git commit hash;
- available local data folders and sizes;
- self-test outcomes;
- Phase 3 coordinate-smoke coverage and warnings; and
- web-app browser/viewport checks.

Do not start Australia-wide processing until this record is complete.
