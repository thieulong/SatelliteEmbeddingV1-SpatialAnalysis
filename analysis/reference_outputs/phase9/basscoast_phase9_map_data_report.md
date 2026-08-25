# Bass Coast Phase 9 Map Data Preparation

## Purpose

This package preserves the complete embedding hot-to-cold raster surface and creates a lighter 30 m common-support layer for DEA, NDVI and future web-map interaction.
The source rectangle contains 191,224,634 grid cells, of which 83,045,578 contain finite endpoint embedding values.

## Spatial sensitivity

The strongest 900-point NDVI association used `embedding_3x3_mean` with Spearman correlation 0.576.
The three methods are retained in the sensitivity table so the 10 m-to-30 m decision remains auditable.

## Complete common-support grid

- no_data: 11,983,924 cells (56.4% of the complete rectangle)
- cold: 379,956 cells (4.1% of finite common-support cells)
- background: 7,706,057 cells (83.1% of finite common-support cells)
- episodic_hotspot: 853,175 cells (9.2% of finite common-support cells)
- persistent_hotspot: 328,528 cells (3.5% of finite common-support cells)

## Interaction features

- hotspot_patch: 13,477 polygons; retained 93.0% of source-state cells at the default interaction threshold.
- coldspot_patch: 307 polygons; retained 38.8% of source-state cells at the default interaction threshold.

Small hotspot and cold cells excluded from polygons remain present in `basscoast_change_state_30m.tif` and in the authoritative 10 m rasters.

## External enrichment test

- Test features: 90
- context_cold: 36
- tier_1_multi_signal: 28
- tier_2_supported: 15
- tier_3_single_signal: 11

The attention tier is a transparent filter assembled from separate embedding, DEA Level 3 change and NDVI-change flags. It is not an accuracy or confidence score.

## Warnings

- None.
