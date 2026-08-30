# AusHabitat Analysis

The retained implementation is organized by purpose rather than by the old,
non-contiguous phase numbers.

## Canonical pipeline

| Stage | Source | Purpose |
| --- | --- | --- |
| 1 | `notebooks/BassCoast_Phase1_Raster_Inspection.ipynb` | Memory-safe raster QA |
| 2 | `notebooks/BassCoast_Phase2_Pixel_Sampling.ipynb` | Reproducible behavioural sampling |
| 3 | `pipeline/stage03_dea_enrichment.py` | Annual DEA histories for sampled points |
| 4 | `pipeline/stage04_dea_wall_to_wall.py` | Wall-to-wall DEA comparison summaries |
| 5 | `pipeline/stage05_ndvi_pilot.py` | NDVI threshold and association pilot |
| 6 | `pipeline/stage06_map_grid.py` | Common 30 m map grid and regions |
| 7 | `pipeline/stage07_region_context.py` | Complete DEA and NDVI region histories |
| 8 | `pipeline/stage08_package_web_data.py` | Browser-ready map package |

`notebooks/builders/` contains the notebook constructors. `reporting/` contains
optional report-generation scripts. `tools/` contains migration and imagery
checks. `reference_outputs/` contains compact evidence from completed runs;
the large working datasets live under the ignored `../data/` directory.

The output filenames still contain historical `phaseN` identifiers. They are
retained to preserve provenance and avoid silently invalidating completed-run
manifests.

Create a fresh Python 3.12 virtual environment and install
`analysis/requirements.txt`. Do not migrate `.venv` or Python caches.
