# Migration Checklist

## Old computer

- [ ] Confirm no pipeline or file-transfer process is running.
- [ ] Confirm GitHub `main` contains the consolidation commit.
- [ ] Copy the complete ignored `data/` directory to external storage.
- [ ] Generate and retain checksums for `data/raw/` and required completed
      products under `data/processed/`.
- [ ] Confirm both PowerPoint files and the technical report exist under
      `deliverables/`.
- [ ] Confirm all three project-owned scripts exist under `analysis/gee/`.
- [ ] Store credentials separately; never place secrets in the repository.
- [ ] Retain the dated pre-consolidation archive until the new computer passes
      all checks.

## New computer

- [ ] Clone the GitHub repository.
- [ ] Ask Codex to read `CODEX_HANDOVER.md` and all `Documentation/` files
      before proposing work.
- [ ] Copy the transferred `data/` directory into the repository root.
- [ ] Create a fresh Python 3.12 `.venv` and install
      `analysis/requirements.txt`.
- [ ] Run `python analysis/tools/verify_transfer.py --project-root .`.
- [ ] If transferred, verify optional imagery with
      `--include-optional-imagery`.
- [ ] Compile all Python and notebook code cells.
- [ ] Run Stage 4 and Stage 7 self-tests.
- [ ] Run a 10-point Stage 3 network smoke test.
- [ ] Compare smoke outputs with `analysis/reference_outputs/`.
- [ ] Serve the app locally and test filters, details, timeline, and basemaps.
- [ ] Confirm the published GitHub Pages application still works.

## Migration verification record

Create a dated text file containing:

- operating system and architecture;
- Python, Rasterio, and GDAL versions;
- Git commit hash;
- transferred directory sizes and checksums;
- transfer-check and self-test results;
- Stage 3 smoke-test coverage and warnings;
- browser and viewport checks; and
- any differences from the retained reference outputs.

Do not begin Australia-wide processing until this record is complete.
