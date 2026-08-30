# AusHabitat

AusHabitat is a Bass Coast landscape-change prototype combining annual Google
Satellite Embedding signals with DEA Land Cover and DEA GeoMAD NDVI context.

**Published application:**
https://thieulong.github.io/SatelliteEmbeddingV1-SpatialAnalysis/

## Start here

New developers and Codex instances must read [`CODEX_HANDOVER.md`](CODEX_HANDOVER.md)
and the numbered [`Documentation/`](Documentation/README.md) files before
changing analysis or application logic.

## Python setup

Use Python 3.12 and create a fresh repository-local virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r analysis/requirements.txt
python analysis/tools/verify_transfer.py --project-root .
```

The dependency versions are pinned in `analysis/requirements.txt`. Large local
scientific data is not downloaded by Git and must be copied separately into
`data/` as described in `Documentation/MIGRATION_CHECKLIST.md`.

## Repository structure

```text
analysis/       Eight-stage pipeline, notebooks, tools, reference evidence
data/           Ignored local-only raw and processed scientific data
deliverables/   Latest presentations and technical report
Documentation/  Methods, results, decisions, boundaries, and migration
public/         Browser-ready map data and assets
research/       Optional external-dataset experiments
src/            Web application JavaScript and CSS
index.html      Static application entry point
```

## Application views

- **Map:** OpenStreetMap roads and places.
- **Satellite reference:** current Esri World Imagery.
- **Annual satellite:** nearest date-verified Esri Wayback capture within the
  configured tolerance, with actual capture date and resolution shown.

## Local run

```bash
python -m http.server 8093
```

Open `http://127.0.0.1:8093/`.

## Scientific boundary

Hot spots are strong embedding-change signals. DEA and NDVI provide supporting
land-cover and vegetation context; they do not establish cause or constitute a
validated accuracy score.

Large rasters and completed analytical products are intentionally excluded
from Git. Follow [`data/README.md`](data/README.md) and the
[`MIGRATION_CHECKLIST`](Documentation/MIGRATION_CHECKLIST.md).
