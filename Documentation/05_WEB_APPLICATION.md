# Web Application

## Product state

The current application is a static Bass Coast prototype published at:

`https://thieulong.github.io/SatelliteEmbeddingV1-SpatialAnalysis/`

It uses plain HTML, CSS, JavaScript, and MapLibre GL JS. GitHub Pages serves the
files directly; there is no production backend, authentication layer, or
database.

## Source layout

- `index.html`: application structure and accessible controls.
- `src/app.js`: map setup, filtering, search, detail views, imagery selection,
  and data loading.
- `src/styles.css`: responsive visual system.
- `public/assets/`: CNPS logo.
- `public/data/features.geojson`: compact interaction-region geometry and
  filter properties.
- `public/data/details/regions_000.json` through `regions_013.json`: detailed
  histories, at most 1,000 regions per shard.
- `public/data/app_metadata.json`: counts, years, thresholds, bounds, and raster
  overlay metadata.
- `public/data/*.png`: annual hot-spot and state overlays.
- `public/data/imagery_sources.json`: Esri Wayback release candidates and
  metadata endpoints.

The fourteen detail files prevent every region's complete annual history from
being loaded at startup. The browser loads only the shard containing the
selected region and caches it for the session.

## Region model

The common approximately 30 m grid contains hot, low-change, background, and
no-data states. Edge-touching cells belonging to the same interaction-state
mask are connected into polygons. The resulting region is a practical map
interaction unit, not proof of a single ecological or development event.

Area is calculated after projecting geometry to Australian Albers, an
equal-area coordinate system. In simple terms, the geometry is temporarily
placed on a metre-based Australian map, measured in square metres, and divided
by 10,000 to report hectares.

## Main controls

- Search by known Bass Coast place, postcode, coordinate, or region ID.
- Show/hide change areas and low-change references.
- Filter by behavioural pattern and minimum region area.
- Show regions active in the selected annual interval.
- Require DEA land-cover transition and/or NDVI vegetation-change evidence.
- Filter vegetation direction.
- Select endpoint overview or one of seven annual intervals.
- Open region summary, timeline, and land-context tabs.

Detection is always embedding-defined. DEA and NDVI controls filter supporting
evidence; disabling them does not redefine the original hot/cold surface.

## Displayed evidence

Region details include:

- endpoint embedding distance;
- strongest annual interval;
- region area;
- relative change activity;
- repeated annual change share;
- endpoint strong-change share;
- variance and change-intensity trend;
- annual embedding magnitude and strong-change area;
- dominant DEA Level 3 and Level 4 classes by year;
- annual mean NDVI and vegetation direction; and
- first broad DEA class change where one occurred.

User-facing descriptions are deliberately cautious. “Pattern suggests” text is
rule-based summarization of measured region properties, not an ML prediction.

## Basemap modes

1. **Map:** OpenStreetMap roads and places; default mode.
2. **Satellite reference:** current high-detail Esri World Imagery.
3. **Annual satellite:** searches configured Esri Wayback releases for the
   capture nearest the selected year at the current map location.

For annual imagery, the app queries Esri metadata, ranks local capture dates by
distance from the selected year's midpoint, and accepts imagery only within
approximately 548 days. It displays the actual capture date and source
resolution. If no acceptable image is available, it falls back to the normal
map instead of presenting a misleading old image as the selected year.

Annual imagery is visual context only. It is not the imagery used to calculate
the embedding, DEA, or NDVI values.

## Local use

Browsers restrict local file loading, so serve the repository root:

```bash
python -m http.server 8093
```

Then open `http://127.0.0.1:8093/`.

## Rebuilding app data

After Stage 6 and Stage 7 outputs have been verified:

```bash
python analysis/pipeline/stage08_package_web_data.py
```

This rewrites committed files under `public/data/`. Review counts, file sizes,
visual output, and browser behaviour before publishing.

## Required browser checks

- Initial map and all three basemaps render.
- Hot and low-change overlays disappear when their checkboxes are cleared.
- Search, region selection, filters, and reset work.
- Endpoint and all annual timeline states update the map and details.
- DEA/NDVI evidence filters behave for “all” and “any”.
- Detail shards load for early, middle, and final region IDs.
- Annual imagery reports capture date or a clear unavailable state.
- Desktop and mobile layouts contain no overlap or clipped controls.

## National production direction

The static package is appropriate for Bass Coast but not for millions of
national features. Australia-wide delivery should use vector/raster tiles,
object storage and CDN caching, server-side spatial queries, stable region IDs,
and an API returning only the selected region's history. A mobile client should
consume the same API rather than duplicating analytical logic.
