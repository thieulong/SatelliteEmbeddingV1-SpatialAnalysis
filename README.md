# AusHabitat

Interactive Bass Coast landscape-change explorer combining satellite-embedding change signals with DEA Land Cover and NDVI context.

## Project handover and analysis source

New developers and Codex instances should start with
[`CODEX_HANDOVER.md`](CODEX_HANDOVER.md), then read the numbered files in
[`Documentation/`](Documentation/README.md). Core notebooks, Python pipelines
and small reference outputs from verified runs are retained under
[`analysis/`](analysis/README.md).

The multi-gigabyte authoritative rasters and complete generated outputs are not
stored in GitHub. Follow the migration checklist before attempting to reproduce
or scale the analysis.

The published site is a static demonstration covering 2017 to 2024. Hot spots and low-change reference regions are derived from the project analysis outputs; supporting datasets provide contextual evidence rather than causal attribution.

The three map views are:

- **Annual satellite:** the closest verified Esri World Imagery Wayback capture found among several nearby archive releases, with the actual date and source resolution reported.
- **Satellite reference:** the latest Esri World Imagery basemap.
- **Map:** OpenStreetMap places and roads.

Wayback does not provide uniform annual photography. AusHabitat checks multiple nearby archive releases and displays imagery only when a verified local capture falls within approximately 18 months of the selected year. Otherwise, the normal map remains visible and the interface reports that no suitable nearby-year image is available.

## Interpretation boundary

Hot spots are embedding-defined change signals. DEA Land Cover and NDVI provide
supporting context; they do not turn the result into a causal land-change label
or a validated accuracy score.
