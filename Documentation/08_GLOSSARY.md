# Glossary

## Analytical terms

**Annual change**
Euclidean distance between the 64-D embedding at the same location in adjacent
years.

**Annual hotspot**
An annual-change cell whose distance is at least 0.45.

**Behavioural category**
A rule-based temporal signal group such as persistent, high variance or stable
control. It is not a land-cover class.

**Cold spot / low-change area**
A strict stable-reference cell or connected region with low endpoint change, no
hot intervals, low variance and near-zero slope.

**Cumulative change**
Sum of the seven annual embedding distances. It measures total movement through
embedding space, not net physical area.

**DEA Land Cover Level 3**
Broad annual class, for example Natural Terrestrial Vegetation, Cultivated
Terrestrial Vegetation, Artificial Surface, Bare Surface or Water.

**DEA Land Cover Level 4**
More detailed annual class that adds vegetation type/form and cover-density
information.

**Embedding**
A learned numerical vector that summarizes satellite-observed characteristics.
Its 64 dimensions are not individually assigned human labels.

**Endpoint change**
Embedding distance between 2017 and 2024.

**Endpoint hotspot**
Endpoint-change cell in approximately the top 5% of the endpoint distribution.

**Hot spot / change area**
A location or connected region with a strong embedding-change signal. It is not
automatically a confirmed ecological or land-use event.

**NDVI**
Normalized Difference Vegetation Index, commonly `(NIR - Red)/(NIR + Red)`.
Higher values generally indicate more photosynthetically active vegetation;
signed changes can indicate greening or browning.

**Persistence count**
Number of the seven annual intervals above the 0.45 hotspot threshold. Intervals
do not have to be consecutive.

**Raster**
A grid dataset. Each cell stores a value such as change distance, class code or
NDVI.

**Slope**
Linear trend of annual embedding-change magnitude over the seven intervals.
Positive/negative refers to increasing/decreasing magnitude, not ecological
direction.

**Variance**
Average squared deviation of the seven annual distances from their mean. High
variance indicates uneven or spike-like timing.

**Wall-to-wall**
Processing every valid cell across the study surface in windows, rather than
only selected sample coordinates.

## Spatial terms

**10 m embedding grid**
Original analytical support of the exported embedding products.

**30 m common-support grid**
Integrated grid used to compare aggregated embedding metrics with DEA Land
Cover and Landsat GeoMAD NDVI.

**Eight-neighbour connectivity**
Cells belong to the same region when they touch by an edge or a corner.

**Australian Albers / EPSG:3577**
An Australia-focused projected coordinate system used to calculate polygon area
in metres rather than degrees.

**Cloud Optimized GeoTIFF (COG)**
A GeoTIFF organized so software can retrieve only the required spatial windows
over HTTP.

**Interaction polygon**
A connected region large enough to be clickable in the app. It is a delivery
object derived from the complete raster surface.

## Validation terms

**Agreement/enrichment**
Evidence that embedding-defined change groups contain more external-dataset
change than stable controls. It is not model accuracy.

**Pearson correlation**
Linear association between two numerical variables.

**Spearman correlation**
Monotonic rank association; it tests whether larger values of one variable tend
to accompany larger values of another without requiring a linear relationship.

**Supporting evidence**
DEA class transition or NDVI change associated with an embedding-defined region.
It adds context but does not prove causality.

## Delivery terms

**Annual satellite**
Nearest acceptable, metadata-verified Esri Wayback image around the chosen year.
It is a visual layer, not an analytical input.

**Satellite reference**
Latest high-detail Esri imagery used for present-day visual orientation.

**JSON shard**
One of fourteen smaller region-history files loaded on demand by the browser.
