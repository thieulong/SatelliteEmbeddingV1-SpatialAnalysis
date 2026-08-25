# AusHabitat Project Documentation

## Purpose

This folder records the technical and product knowledge accumulated while
building AusHabitat. It is intended to let a new Codex instance, developer or
research collaborator continue the work without reconstructing earlier
decisions from chat history.

## Document map

| File | Purpose |
| --- | --- |
| `00_CURRENT_STATE.md` | What exists now, what is complete and what is not. |
| `01_METHODS_AND_PIPELINE.md` | End-to-end analytical methods and algorithms. |
| `02_VERIFIED_RESULTS.md` | Confirmed numerical results and their meaning. |
| `03_DECISION_LOG_AND_BOUNDARIES.md` | Why major technical choices were made. |
| `04_DATA_AND_REPRODUCTION.md` | Data inventory, commands and environment setup. |
| `05_WEB_APPLICATION.md` | Current application architecture and behaviour. |
| `06_STAKEHOLDER_DIRECTION.md` | Supervisor, manager and presentation direction. |
| `07_FUTURE_ROADMAP.md` | Recommended path from Bass Coast to Australia. |
| `08_GLOSSARY.md` | Plain-language definitions of project terminology. |
| `09_DATA_SOURCES_AND_PROVENANCE.md` | Official products, access routes and version risks. |
| `MIGRATION_CHECKLIST.md` | Practical new-computer transfer and validation steps. |

## Repository map

The GitHub `main` branch serves the static web application from the repository
root. The analysis source added for handover is isolated under `analysis/` so it
does not interfere with GitHub Pages.

```text
/
|-- index.html                 # deployed application
|-- src/                       # application JavaScript and CSS
|-- public/                    # browser-ready map assets
|-- analysis/
|   |-- notebooks/             # Phase 1 and Phase 2 notebooks
|   |-- scripts/               # core local analysis scripts
|   |-- reference_outputs/     # small, auditable result summaries
|   `-- study_design/          # NDVI study design
|-- Documentation/             # this handover
`-- CODEX_HANDOVER.md          # first file for a new Codex instance
```

## Evidence hierarchy

1. GeoTIFF rasters are the authoritative spatial analytical products.
2. Phase reports, manifests and summary CSVs record validated runs.
3. The 89,707-point sample supports category-level diagnostic analysis.
4. The 900-point review subset supports manual review and external-data pilots.
5. Browser assets are delivery derivatives, not the authoritative analysis.
6. Historical basemap imagery is visual context only.

## How to use this handover

A new Codex instance should first read `CODEX_HANDOVER.md`, then this file and
the numbered documents. It should verify the local data inventory before making
claims about reproducibility or starting expensive processing.
