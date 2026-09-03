# Glossary

**Annual change**
Embedding distance between the same mapped location in consecutive years.

**Annual hot spot**
A valid pixel whose annual embedding distance is strictly greater than `0.45`,
matching the comparison implemented in the Earth Engine source.

**Australian Albers (`EPSG:3577`)**
An Australia-centred equal-area coordinate system measured in metres. It is
used for raster alignment and area calculations.

**Behavioural category**
A rule-based temporal signal pattern such as high variance, persistent change,
or stable control. Categories overlap and are not real-world land-use labels.

**Cloud-Optimized GeoTIFF (COG)**
A GeoTIFF arranged so software can request only the required remote blocks.

**Cold / low-change reference**
A selected location with low endpoint change, no annual hot intervals, low
variance, and slope near zero. It is a comparison reference, not proof that
nothing changed.

**Common-support grid**
The approximately 30 m aggregation/resampling grid used to combine 10 m
embedding metrics with 30 m DEA and NDVI context. Its target grid uses a factor
of three, but masks and alignment mean a cell does not necessarily contain
exactly nine valid embedding cells.

**Cumulative change**
Sum of the seven annual embedding distances.

**DEA Land Cover Level 3**
Broad annual land-cover class, for example natural terrestrial vegetation,
cultivated terrestrial vegetation, artificial surface, bare surface, aquatic
vegetation, or water.

**DEA Land Cover Level 4**
More detailed annual class including vegetation form and cover ranges.

**Embedding**
A learned 64-number vector summarizing satellite-observed characteristics of a
10 m location for one year. Individual dimensions are not named land classes.

**Endpoint change**
Embedding distance directly between 2017 and 2024.

**Endpoint hot spot**
A valid endpoint-change pixel at or above the endpoint 95th percentile.

**Hot spot**
A location with strong embedding change under a defined annual or endpoint
threshold. It indicates where to investigate, not why the change occurred.

**NDVI**
Normalized Difference Vegetation Index, `(NIR - Red)/(NIR + Red)`, usually
between -1 and 1. Higher values generally indicate more photosynthetically
active vegetation, but interpretation depends on context and season.

**Persistence count**
Number of the seven annual intervals whose embedding distance met the annual
hot-spot threshold. It is not necessarily a consecutive run.

**Pixel / raster cell**
One grid location in a raster. A raster is the complete rectangular grid of
cells plus geospatial metadata.

**Region**
Connected common-grid cells grouped for efficient interaction in the app. A
region is not automatically one real-world event.

**Slope**
Linear-regression trend in the seven annual embedding distances. Positive means
later intervals tend to be stronger; negative means earlier intervals tend to
be stronger.

**Variance**
Average squared deviation of annual embedding distances from their mean. High
variance indicates uneven or spike-like annual change.

**Wall-to-wall**
Processing the complete valid mapped surface rather than only sampled points.

**Windowed processing**
Reading a raster in manageable blocks so the full surface does not need to fit
in memory.
