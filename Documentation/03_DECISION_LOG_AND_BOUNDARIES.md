# Decision Log and Interpretation Boundaries

## Decisions retained

### Use Euclidean embedding distance as the primary change magnitude

Reason: it provides a simple, consistent magnitude between the same 64-D
location vectors through time and was already implemented in Earth Engine.

Boundary: dimensions are latent, and distance is not a semantic class. Future
method comparison should test cosine/dot-product alternatives before claiming
Euclidean distance is universally optimal.

### Use annual 0.45 and endpoint p95 as different hotspot thresholds

Reason: annual intervals need a consistent threshold for persistence counts;
endpoint change has a different temporal span and distribution, so its upper
tail was selected using p95.

Boundary: thresholds are calibrated to this study configuration. Recalculate
or validate them when the AOI, embedding version, period or mosaic method
changes.

### Do not flatten the complete raster stack

Reason: the 10 m rectangle has 191 million positions and about 83 million finite
endpoint values. A huge per-pixel CSV would waste memory and storage, duplicate
raster structure and perform poorly.

Implementation: windowed processing, fixed-size reservoirs, checkpointed
summaries and tiled/browser derivatives.

### Sample by behavioural category before external enrichment

Reason: balanced sampling gives enough examples of rare temporal behaviours and
allows methods to be debugged before expensive wall-to-wall processing.

Boundary: it is not area-weighted. Category proportions in the sample do not
represent landscape prevalence.

### Keep a 900-point review subset

Reason: 89,707 points are useful statistically but impractical for manual
inspection. The representative/high-signal/random mixture provides a stable
review package.

Boundary: 900 points validate access and interpretation, not the whole map.

### Run DEA enrichment locally rather than in Colab

Reason: local Rasterio/GDAL remote COG reading was more stable and diagnostic.
Colab had partial/masked remote reads and suppressed warnings, and notebook
versions could drift.

Implementation: local Python, explicit warnings, coordinate diagnostics,
3x3/5x5 fallbacks, chunk checkpoints and resume.

### Use DEA Land Cover as the primary categorical context

Reason: annual Australian coverage, public COG access, documented Level 3/4
hierarchy and strong fit with the 2017-2024 period.

Boundary: DEA is Australia-specific, 30 m, Landsat-derived and categorical. It
cannot identify every condition change or serve as absolute ground truth.

### Do not make Esri a required final layer

Reason: high broad-family agreement was encouraging, but native-class changed
status and timing agreement were much lower. Esri labels did not consistently
add more detail than DEA Level 4.

Status: retain scripts and results for research/audit; do not add the layer to
the main analytical interpretation unless a concrete user need is identified.

### Do not add Dynamic World at this checkpoint

Reason: it would add Earth Engine authentication and more class instability
without enough additional decision value after DEA and Esri evaluation.

Status: reconsider only for a clearly defined 10 m or sub-annual research
question.

### Add NDVI as complementary signed vegetation evidence

Reason: embedding distance is unsigned and can respond to many landscape
changes. NDVI adds an interpretable greening/browning response and a traditional
baseline requested by stakeholders.

Boundary: NDVI does not identify land cover, cannot separate canopy from forest
floor in dense vegetation, and shares Landsat lineage with DEA. Correlation is
association, not validation accuracy.

### Move integrated analysis and web interaction to 30 m

Reason: DEA Land Cover and annual GeoMAD NDVI are approximately 30 m. A common
grid avoids pretending one DEA/NDVI observation supplies independent evidence
for each of nine 10 m embedding cells.

Trade-off: spatial interaction becomes coarser. The original 10 m rasters are
retained for fine-scale embedding inspection.

### Group neighbouring cells into regions

Reason: displaying millions of individual cells is visually noisy and expensive
for browsers. Connected components better approximate landscape events and
support region summaries.

Implementation: separate hot and cold masks, eight-neighbour connectivity,
minimum 9 hot cells and 100 cold cells.

Trade-off: corner-touching cells can merge, and large components may combine
several real events. National scaling should test morphology, tile-edge dissolve
and segmentation sensitivity.

### Preserve both hot and cold surfaces

Reason: cold areas provide reference behaviour, NDVI threshold calibration and
context for comparison. The product should not show only dramatic change.

Implementation: full change-state raster plus interaction polygons. Small cells
removed from polygon interaction remain in the raster surface.

### Treat evidence tiers as transparent combinations, not confidence

The initial prototype used evidence tiers based on embedding, DEA and NDVI
flags. The UI was simplified to direct evidence filters because tiers were
confusing and could be misread as model confidence.

### Keep the application beginner-facing

Complex metrics remain available but primary labels use plain language. Help
text should explain persistence, variance, slope, strong-change area and NDVI
direction. Do not introduce specialist labels without an explanation.

### Use Esri Wayback for visual historical context only

Reason: it can provide high-detail imagery for demonstrations without shipping
large local imagery files.

Boundary: releases can reuse older source imagery. The app checks actual local
capture metadata and accepts an image only within 548 days of the selected
year. It reports capture date and resolution. This layer is not used in
analysis.

### Keep default map mode as a normal map

Reason: Wayback coverage and lookup latency vary. The normal map is stable and
prevents a blank initial state. Users choose satellite modes when needed.

## Claims that must not be made

- "All hot spots have been correctly classified."
- "DEA proves the embedding method is X percent accurate."
- "A Natural -> Artificial transition proves construction occurred."
- "Positive embedding slope means vegetation grew."
- "A 10 m satellite basemap makes the 30 m analysis 10 m accurate."
- "The 89,707 points are all Bass Coast pixels."
- "The 13,784 polygons contain every hot/cold cell."
- "Wayback imagery is captured in the exact selected year everywhere."

## Preferred wording

- "Embedding-defined change region" rather than confirmed disturbance.
- "DEA-observed land-cover transition" rather than ground-truth event.
- "NDVI vegetation-change evidence" rather than ecological diagnosis.
- "Agreement/enrichment signal" rather than accuracy.
- "Nearest verified historical image" with the actual capture date.
