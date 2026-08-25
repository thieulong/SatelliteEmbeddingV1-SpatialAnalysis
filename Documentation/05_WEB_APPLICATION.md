# Web Application

## Current deployment

Published URL:
`https://thieulong.github.io/SatelliteEmbeddingV1-SpatialAnalysis/`

The GitHub `main` branch is the deployed static site. GitHub Pages serves:

- `index.html`;
- `src/app.js` and `src/styles.css`;
- `public/data/features.geojson`;
- `public/data/app_metadata.json`;
- `public/data/details/regions_000.json` through `regions_013.json`;
- raster overlay PNGs; and
- imagery configuration.

## Technology

- Plain HTML, CSS and JavaScript.
- MapLibre GL JS for map rendering.
- Lucide icons.
- OpenStreetMap raster map and Nominatim search/reverse geocoding.
- Esri World Imagery for current high-detail reference.
- Esri World Imagery Wayback for historical visual context.
- GitHub Pages for static hosting.

There is no application database or backend API in the published prototype.

The browser package can be rebuilt from Phase 9 and Phase 10 outputs with
`analysis/scripts/prepare_app_data.py`. That script generates features, detail
shards, overlays and metadata; the separately curated Wayback imagery
configuration remains under `public/data/imagery_sources.json`.

## Browser data loading

The overview geometry and compact properties load at startup. Detailed histories
are split into fourteen JSON shards, each containing at most 1,000 regions. A
shard is fetched only when a selected region needs it, then cached in memory.

This keeps the initial payload and parsing cost smaller than one monolithic
history file. It is a Bass Coast optimization, not a national architecture.

## Interaction regions and raster surfaces

The application distinguishes:

- **Change areas (hot spots):** connected 30 m cells with episodic or persistent
  embedding hotspots, after the interaction-size threshold.
- **Low-change areas (cold spots):** connected stable-reference cells after a
  larger interaction-size threshold.
- **Raster overlays:** preserve the broader hot/cold surface, including cells
  too small for interactive polygons.

When both region checkboxes are off, no coloured hot/cold overlay should remain
visible. Basemap choice is independent of these overlays.

## Filters

- Hot/cold region type.
- Change pattern: mainly once, some repeated, widespread repeated or mostly
  unchanged.
- Minimum region area.
- Active in selected annual period: at least 5% of region cells exceeded the
  annual 0.45 hotspot threshold in that period.
- DEA Level 3 land-cover-transition evidence.
- NDVI substantial-change evidence.
- NDVI net direction: greening, browning or no clear endpoint change.

DEA and NDVI filters do not define the hot spots. They filter embedding-defined
regions by additional evidence.

## Region detail panel

The panel provides:

- endpoint embedding distance;
- region area;
- strongest annual change period;
- relative total change activity;
- repeated-change coverage;
- strong endpoint-change coverage;
- year-to-year variability label;
- change-intensity trend;
- annual embedding change and strong-change area;
- DEA Level 3 and Level 4 classes and transitions;
- annual NDVI and greening/browning context; and
- advanced numerical values behind plain-language labels.

Interpret these as region summaries. A region can contain heterogeneous cells,
so dominant DEA class labels include shares and secondary classes where useful.

## Basemap modes

### Map

OpenStreetMap places and roads. This is the default because it is stable and
provides clear orientation.

### Satellite reference

Latest high-detail Esri World Imagery. It provides current context but does not
follow the analytical timeline.

### Annual satellite

Esri Wayback releases are searched near the selected year and current map
centre. The application queries local metadata for several candidate releases,
chooses the closest verified source capture and reports:

- actual capture date;
- source resolution; and
- provider.

The image is accepted only within 548 days of the requested year. If none is
available, the normal map remains visible with a warning. A first uncached
metadata lookup can take several seconds. This is visual evidence only and can
vary spatially within the viewport.

## Local run

From the repository root:

```bash
python3 -m http.server 8080
```

Open `http://127.0.0.1:8080/`.

Do not open `index.html` directly because browser fetches for JSON/GeoJSON need
an HTTP origin.

## Minimum regression checks

Desktop and mobile:

1. App loads with normal map as default.
2. Hot and cold regions can be independently shown/hidden.
3. Turning both off removes all coloured change overlays.
4. Search accepts place, postcode, coordinate and region ID.
5. Timeline changes annual overlays and selected imagery year.
6. Active-period filter is disabled for overview and works for annual periods.
7. Region selection opens summary, timeline and land-context tabs.
8. Help popovers open and close correctly.
9. DEA and NDVI evidence filters update counts and geometry.
10. Annual satellite reports actual date/resolution or a clear no-image message.
11. No text overlaps panels or timeline at common viewport sizes.

## Scaling limitations

The current site ships about 109 MB of static files and 13,784 region features.
Do not extend the same monolithic static approach to Australia.

National delivery should use:

- COGs or cloud-native Zarr/Parquet in object storage;
- vector tiles for interaction geometry;
- raster tiles for change surfaces;
- a spatial database/API for detail queries;
- CDN caching;
- region/tile indexing and stable IDs; and
- asynchronous processing for AOI/year updates.

The web frontend can remain MapLibre-based while data delivery changes behind
it.
