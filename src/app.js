const DATA_ROOT = "public/data";
const INTERVALS = ["endpoint", "2017_2018", "2018_2019", "2019_2020", "2020_2021", "2021_2022", "2022_2023", "2023_2024"];
const IMAGERY_YEARS = Array.from({ length: 9 }, (_, index) => 2017 + index);
const INTERVAL_LABELS = {
  endpoint: "2017–2024 overview",
  "2017_2018": "2017 → 2018",
  "2018_2019": "2018 → 2019",
  "2019_2020": "2019 → 2020",
  "2020_2021": "2020 → 2021",
  "2021_2022": "2021 → 2022",
  "2022_2023": "2022 → 2023",
  "2023_2024": "2023 → 2024",
};
const BEHAVIOURS = {
  repeated_change: { label: "Widespread repeated change", short: "Widespread repeated", className: "repeat", color: "#b73143" },
  mixed_change: { label: "Some repeated change", short: "Some repeated", className: "mixed", color: "#dc7927" },
  mostly_single_period_change: { label: "Change mainly once", short: "Mainly once", className: "single", color: "#e7ad3b" },
  low_change_reference: { label: "Mostly unchanged", short: "Mostly unchanged", className: "cold", color: "#2c70a5" },
};
const DEA_CLASS = {
  natural: "n",
  cultivated: "c",
  artificial: "a",
  water: "w",
  bare: "b",
};
const BASEMAPS = {
  annual: { label: "Annual satellite", layer: "annual-satellite" },
  reference: { label: "Satellite reference", layer: "reference-satellite" },
  streets: { label: "Map", layer: "osm" },
};
const LOCAL_PLACES = [
  { name: "Wonthaggi", detail: "VIC 3995", center: [145.591, -38.606] },
  { name: "Inverloch", detail: "VIC 3996", center: [145.729, -38.633] },
  { name: "Cowes", detail: "VIC 3922", center: [145.239, -38.452] },
  { name: "San Remo", detail: "VIC 3925", center: [145.377, -38.521] },
  { name: "Phillip Island", detail: "Bass Coast, VIC", center: [145.231, -38.487] },
  { name: "Grantville", detail: "VIC 3984", center: [145.531, -38.407] },
  { name: "Corinella", detail: "VIC 3984", center: [145.428, -38.414] },
  { name: "Cape Paterson", detail: "VIC 3995", center: [145.616, -38.672] },
  { name: "Rhyll", detail: "VIC 3923", center: [145.299, -38.463] },
  { name: "Bass Coast", detail: "Victoria, Australia", center: [145.56, -38.51] },
];

const app = {
  map: null,
  metadata: null,
  features: null,
  featureLookup: new Map(),
  shardCache: new Map(),
  selectedId: null,
  selectedDetail: null,
  selectedTab: "overview",
  interval: "endpoint",
  evidenceMatch: "all",
  searchMarker: null,
  searchRequest: 0,
  helpAnchor: null,
  helpPinned: false,
  helpTimer: null,
  basemap: "annual",
  imageryYear: 2024,
};

const $ = (id) => document.getElementById(id);
const formatNumber = (value, digits = 2) => value === null || value === undefined || Number.isNaN(Number(value))
  ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
const formatPercent = (value, digits = 0) => value === null || value === undefined || Number.isNaN(Number(value))
  ? "—" : `${(Number(value) * 100).toFixed(digits)}%`;
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

function plainLabel(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function behaviourInfo(value) {
  return BEHAVIOURS[value] || BEHAVIOURS.mixed_change;
}

function directionLabel(value) {
  return { greening: "Greener than at study start", browning: "Less green than at study start", stable: "Similar greenness to study start" }[value] || "Not available";
}

function trendLabel(value) {
  return { increasing: "Increasing", decreasing: "Decreasing", no_clear_trend: "No clear trend" }[value] || "Not available";
}

function patternLabel(value) {
  return { fairly_consistent: "Similar each year", mixed: "Some years stand out", highly_uneven: "A few years dominate" }[value] || "Not available";
}

function help(text) {
  return `<button type="button" class="inline-help" data-help="${escapeHtml(text)}" aria-label="${escapeHtml(text)}"><i data-lucide="circle-help"></i></button>`;
}

function showHelpPopover(button, pinned = false) {
  const message = button.dataset.help;
  if (!message) return;
  const popover = $("helpPopover");
  if (app.helpAnchor && app.helpAnchor !== button) app.helpAnchor.setAttribute("aria-expanded", "false");
  app.helpAnchor = button;
  app.helpPinned = pinned;
  if (app.helpTimer) window.clearTimeout(app.helpTimer);
  button.setAttribute("aria-expanded", "true");
  popover.textContent = message;
  popover.hidden = false;
  const anchor = button.getBoundingClientRect();
  const box = popover.getBoundingClientRect();
  const left = Math.max(8, Math.min(window.innerWidth - box.width - 8, anchor.right - box.width));
  const below = anchor.bottom + 7;
  const top = below + box.height <= window.innerHeight - 8 ? below : Math.max(8, anchor.top - box.height - 7);
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
  if (pinned) app.helpTimer = window.setTimeout(() => hideHelpPopover(true), 3000);
}

function hideHelpPopover(force = false) {
  if (app.helpPinned && !force) return;
  if (app.helpTimer) window.clearTimeout(app.helpTimer);
  app.helpTimer = null;
  if (app.helpAnchor) app.helpAnchor.setAttribute("aria-expanded", "false");
  app.helpAnchor = null;
  app.helpPinned = false;
  $("helpPopover").hidden = true;
}

async function loadData() {
  const [metadataResponse, featureResponse] = await Promise.all([
    fetch(`${DATA_ROOT}/app_metadata.json`),
    fetch(`${DATA_ROOT}/features.geojson`),
  ]);
  if (!metadataResponse.ok || !featureResponse.ok) throw new Error("The AusHabitat map package could not be loaded.");
  [app.metadata, app.features] = await Promise.all([metadataResponse.json(), featureResponse.json()]);
  app.featureLookup = new Map(app.features.features.map((feature) => [feature.properties.feature_id, feature.properties]));
}

async function getDetail(featureId) {
  const number = Number(featureId.replace(/\D/g, ""));
  const shard = Math.floor((number - 1) / app.metadata.detail_shard_size);
  if (!app.shardCache.has(shard)) {
    const response = await fetch(`${DATA_ROOT}/details/regions_${String(shard).padStart(3, "0")}.json`);
    if (!response.ok) throw new Error(`Region detail package ${shard} could not be loaded.`);
    app.shardCache.set(shard, await response.json());
  }
  return app.shardCache.get(shard)[featureId];
}

function annualSatelliteSource(year) {
  const base = "https://ows.dea.ga.gov.au/wms";
  const query = [
    "service=WMS",
    "version=1.1.1",
    "request=GetMap",
    "layers=ga_ls8cls9c_gm_cyear_3",
    "styles=simple_rgb",
    "format=image%2Fpng",
    "transparent=false",
    "height=256",
    "width=256",
    "srs=EPSG%3A3857",
    `time=${year}-01-01`,
    "bbox={bbox-epsg-3857}",
  ].join("&");
  return {
    type: "raster",
    tiles: [`${base}?${query}`],
    tileSize: 256,
    maxzoom: 14,
    attribution: '<a href="https://knowledge.dea.ga.gov.au/data/product/dea-geometric-median-and-median-absolute-deviation-landsat/" target="_blank" rel="noopener">DEA GeoMAD</a> · Geoscience Australia',
  };
}

function updateMapStatus() {
  const analysis = app.interval === "endpoint" ? "2017–2024 overview" : `Change during ${INTERVAL_LABELS[app.interval]}`;
  const imagery = app.basemap === "annual" ? `annual satellite ${app.imageryYear}`
    : app.basemap === "reference" ? "satellite reference" : "street map";
  $("mapStatus").textContent = `${analysis} · ${imagery}`;
}

function updateImageryYearControl() {
  $("imageryYearValue").textContent = app.imageryYear;
  $("previousImageryYear").disabled = app.imageryYear === IMAGERY_YEARS[0];
  $("nextImageryYear").disabled = app.imageryYear === IMAGERY_YEARS.at(-1);
  $("imageryYearControl").setAttribute("aria-label", `Annual satellite imagery for ${app.imageryYear}`);
}

function setImageryYear(year) {
  const nextYear = Math.max(IMAGERY_YEARS[0], Math.min(IMAGERY_YEARS.at(-1), Number(year)));
  if (!IMAGERY_YEARS.includes(nextYear)) return;
  const changed = nextYear !== app.imageryYear;
  app.imageryYear = nextYear;
  updateImageryYearControl();
  updateMapStatus();
  if (!changed || !app.map?.isStyleLoaded()) return;

  if (app.map.getLayer("annual-satellite")) app.map.removeLayer("annual-satellite");
  if (app.map.getSource("annual-satellite")) app.map.removeSource("annual-satellite");
  app.map.addSource("annual-satellite", annualSatelliteSource(nextYear));
  const beforeLayer = ["surface-cold-overlay", "surface-hotspot-overlay", "regions-fill"]
    .find((layerId) => app.map.getLayer(layerId));
  app.map.addLayer({
    id: "annual-satellite",
    type: "raster",
    source: "annual-satellite",
    minzoom: 0,
    maxzoom: 20,
    layout: { visibility: app.basemap === "annual" ? "visible" : "none" },
  }, beforeLayer);
}

function shiftImageryYear(direction) {
  const current = IMAGERY_YEARS.indexOf(app.imageryYear);
  setImageryYear(IMAGERY_YEARS[Math.max(0, Math.min(IMAGERY_YEARS.length - 1, current + direction))]);
}

function createMap() {
  const [west, south, east, north] = app.metadata.bounds;
  app.map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        "annual-satellite": annualSatelliteSource(app.imageryYear),
        "reference-satellite": {
          type: "raster",
          tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          attribution: "Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community",
        },
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors",
        },
      },
      layers: [
        { id: "annual-satellite", type: "raster", source: "annual-satellite", minzoom: 0, maxzoom: 20 },
        { id: "reference-satellite", type: "raster", source: "reference-satellite", minzoom: 0, maxzoom: 20, layout: { visibility: "none" } },
        { id: "osm", type: "raster", source: "osm", minzoom: 0, maxzoom: 19, layout: { visibility: "none" } },
      ],
    },
    center: [(west + east) / 2, (south + north) / 2],
    zoom: 8.7,
    minZoom: 7.7,
    maxZoom: 17,
    attributionControl: false,
  });
  app.map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  app.map.on("load", () => {
    setSurfaceLayers(app.metadata.hotspot_surface_overlay);
    app.map.addSource("regions", { type: "geojson", data: app.features });
    app.map.addLayer({
      id: "regions-fill", type: "fill", source: "regions",
      paint: {
        "fill-color": behaviourColourExpression(),
        "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.82, 0.57],
      },
    });
    app.map.addLayer({
      id: "regions-outline", type: "line", source: "regions",
      paint: { "line-color": "#4c555a", "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 12, 0.8, 16, 1.6], "line-opacity": 0.72 },
    });
    app.map.addLayer({
      id: "selected-outline", type: "line", source: "regions",
      filter: ["==", ["get", "feature_id"], ""],
      paint: { "line-color": "#10181c", "line-width": 3, "line-opacity": 1 },
    });

    let hoveredId = null;
    app.map.on("mousemove", "regions-fill", (event) => {
      app.map.getCanvas().style.cursor = "pointer";
      const feature = event.features?.[0];
      if (!feature) return;
      if (hoveredId !== null) app.map.setFeatureState({ source: "regions", id: hoveredId }, { hover: false });
      hoveredId = feature.id;
      app.map.setFeatureState({ source: "regions", id: hoveredId }, { hover: true });
    });
    app.map.on("mouseleave", "regions-fill", () => {
      app.map.getCanvas().style.cursor = "";
      if (hoveredId !== null) app.map.setFeatureState({ source: "regions", id: hoveredId }, { hover: false });
      hoveredId = null;
    });
    app.map.on("click", "regions-fill", (event) => {
      const featureId = event.features?.[0]?.properties?.feature_id;
      if (featureId) selectFeature(featureId, true);
    });
    fitBounds();
    applyFilters();
    $("mapLoading").classList.add("hidden");
  });
}

function setBasemap(name) {
  const selected = BASEMAPS[name];
  if (!selected || !app.map) return;
  app.basemap = name;
  Object.entries(BASEMAPS).forEach(([key, item]) => {
    app.map.setLayoutProperty(item.layer, "visibility", key === name ? "visible" : "none");
  });
  document.querySelectorAll(".basemap-option").forEach((button) => {
    const active = button.dataset.basemap === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-checked", String(active));
  });
  const toggle = $("basemapToggle");
  toggle.setAttribute("aria-label", `Choose map view. ${selected.label} selected`);
  $("imageryYearControl").hidden = name !== "annual";
  updateMapStatus();
  closeBasemapMenu();
}

function closeBasemapMenu() {
  $("basemapMenu").hidden = true;
  $("basemapToggle").setAttribute("aria-expanded", "false");
}

function toggleBasemapMenu() {
  const menu = $("basemapMenu");
  const opening = menu.hidden;
  menu.hidden = !opening;
  $("basemapToggle").setAttribute("aria-expanded", String(opening));
  if (opening) menu.querySelector(".basemap-option.active")?.focus();
}

function behaviourColourExpression() {
  return ["match", ["get", "behaviour"],
    "repeated_change", BEHAVIOURS.repeated_change.color,
    "mixed_change", BEHAVIOURS.mixed_change.color,
    "mostly_single_period_change", BEHAVIOURS.mostly_single_period_change.color,
    "low_change_reference", BEHAVIOURS.low_change_reference.color,
    "#7b858a"];
}

function surfaceCoordinates() {
  const [west, south, east, north] = app.metadata.bounds;
  return [[west, north], [east, north], [east, south], [west, south]];
}

function transitionYears() {
  return app.interval === "endpoint" ? [2017, 2024] : app.interval.split("_").map(Number);
}

function deaYearProperty(year) {
  return `d${String(year).slice(-2)}`;
}

function landTransitionMatches(fromClass, toClass, transition) {
  if (transition === "all") return true;
  if (transition === "any_change") return fromClass !== toClass;
  if (transition === "no_change") return fromClass === toClass;
  if (transition === "natural_to_cultivated") return fromClass === DEA_CLASS.natural && toClass === DEA_CLASS.cultivated;
  if (transition === "natural_to_artificial") return fromClass === DEA_CLASS.natural && toClass === DEA_CLASS.artificial;
  if (transition === "cultivated_to_natural") return fromClass === DEA_CLASS.cultivated && toClass === DEA_CLASS.natural;
  if (transition === "cultivated_to_artificial") return fromClass === DEA_CLASS.cultivated && toClass === DEA_CLASS.artificial;
  if (transition === "artificial_to_vegetation") {
    return fromClass === DEA_CLASS.artificial && [DEA_CLASS.natural, DEA_CLASS.cultivated].includes(toClass);
  }
  if (transition === "to_water_or_bare") {
    return fromClass !== toClass && [DEA_CLASS.water, DEA_CLASS.bare].includes(toClass);
  }
  return true;
}

function landTransitionExpression(transition) {
  const [startYear, endYear] = transitionYears();
  const from = ["get", deaYearProperty(startYear)];
  const to = ["get", deaYearProperty(endYear)];
  if (transition === "any_change") return ["!=", from, to];
  if (transition === "no_change") return ["==", from, to];
  if (transition === "natural_to_cultivated") return ["all", ["==", from, DEA_CLASS.natural], ["==", to, DEA_CLASS.cultivated]];
  if (transition === "natural_to_artificial") return ["all", ["==", from, DEA_CLASS.natural], ["==", to, DEA_CLASS.artificial]];
  if (transition === "cultivated_to_natural") return ["all", ["==", from, DEA_CLASS.cultivated], ["==", to, DEA_CLASS.natural]];
  if (transition === "cultivated_to_artificial") return ["all", ["==", from, DEA_CLASS.cultivated], ["==", to, DEA_CLASS.artificial]];
  if (transition === "artificial_to_vegetation") {
    return ["all", ["==", from, DEA_CLASS.artificial], ["match", to, [DEA_CLASS.natural, DEA_CLASS.cultivated], true, false]];
  }
  if (transition === "to_water_or_bare") {
    return ["all", ["!=", from, to], ["match", to, [DEA_CLASS.water, DEA_CLASS.bare], true, false]];
  }
  return null;
}

function updateTransitionPeriod() {
  const [startYear, endYear] = transitionYears();
  $("landTransitionPeriod").textContent = `${startYear} → ${endYear}`;
}

function addSurfaceLayer(layerId, relativeUrl) {
  if (app.map.getLayer(layerId)) app.map.removeLayer(layerId);
  if (app.map.getSource(layerId)) app.map.removeSource(layerId);
  app.map.addSource(layerId, { type: "image", url: `public/${relativeUrl}`, coordinates: surfaceCoordinates() });
  app.map.addLayer({
    id: layerId,
    type: "raster",
    source: layerId,
    paint: { "raster-opacity": 0.82 },
  }, app.map.getLayer("regions-fill") ? "regions-fill" : undefined);
}

function setSurfaceLayers(hotspotRelativeUrl) {
  addSurfaceLayer("surface-cold-overlay", app.metadata.coldspot_surface_overlay);
  addSurfaceLayer("surface-hotspot-overlay", hotspotRelativeUrl);
  updateSurfaceVisibility(currentFilters());
}

function updateSurfaceVisibility(filters) {
  const regionFilterActive = filters.pattern !== "all"
    || filters.landTransition !== "all"
    || filters.minArea > 0
    || filters.annualOnly
    || filters.evidence.length > 0
    || filters.vegetation !== "all";
  if (app.map?.getLayer("surface-hotspot-overlay")) {
    app.map.setLayoutProperty("surface-hotspot-overlay", "visibility", filters.hotspots && !regionFilterActive ? "visible" : "none");
  }
  if (app.map?.getLayer("surface-cold-overlay")) {
    app.map.setLayoutProperty("surface-cold-overlay", "visibility", filters.coldspots && !regionFilterActive ? "visible" : "none");
  }
}

function fitBounds() {
  if (!app.map || !app.metadata) return;
  const [west, south, east, north] = app.metadata.bounds;
  const compact = window.innerWidth <= 900;
  const detailsOpen = !$('detailPanel').hidden && !compact;
  app.map.fitBounds([[west, south], [east, north]], {
    padding: {
      top: 78,
      bottom: 78,
      left: compact ? 28 : 348,
      right: detailsOpen ? 468 : 28,
    },
    duration: 700,
  });
}

function currentFilters() {
  return {
    hotspots: $("showHotspots").checked,
    coldspots: $("showColdspots").checked,
    landTransition: $("landTransition").value,
    pattern: $("changePattern").value,
    minArea: Number($("minArea").value),
    annualOnly: $("annualHotspotsOnly").checked,
    evidence: [
      ["dea_signal", $("evidenceDea").checked],
      ["ndvi_signal", $("evidenceNdvi").checked],
    ].filter(([, selected]) => selected).map(([property]) => property),
    evidenceMatch: app.evidenceMatch,
    vegetation: $("vegetationDirection").value,
  };
}

function featurePasses(properties, filters) {
  const isCold = properties.feature_type === "coldspot_patch";
  if ((isCold && !filters.coldspots) || (!isCold && !filters.hotspots)) return false;
  const [startYear, endYear] = transitionYears();
  if (!landTransitionMatches(properties[deaYearProperty(startYear)], properties[deaYearProperty(endYear)], filters.landTransition)) return false;
  if (filters.pattern !== "all" && properties.behaviour !== filters.pattern) return false;
  if (Number(properties.area_ha) < filters.minArea) return false;
  if (filters.annualOnly && app.interval !== "endpoint" && Number(properties[`hotspot_${app.interval}`] || 0) < 0.05) return false;
  if (filters.vegetation !== "all" && properties.ndvi_direction !== filters.vegetation) return false;
  if (filters.evidence.length) {
    const matches = filters.evidence.map((property) => properties[property] === true);
    if (filters.evidenceMatch === "all" && !matches.every(Boolean)) return false;
    if (filters.evidenceMatch === "any" && !matches.some(Boolean)) return false;
  }
  return true;
}

function mapFilterExpression(filters) {
  const types = [];
  if (filters.hotspots) types.push("hotspot_patch");
  if (filters.coldspots) types.push("coldspot_patch");
  const conditions = [
    ["match", ["get", "feature_type"], types.length ? types : ["__none__"], true, false],
    [">=", ["get", "area_ha"], filters.minArea],
  ];
  if (filters.landTransition !== "all") conditions.push(landTransitionExpression(filters.landTransition));
  if (filters.pattern !== "all") conditions.push(["==", ["get", "behaviour"], filters.pattern]);
  if (filters.annualOnly && app.interval !== "endpoint") conditions.push([">=", ["get", `hotspot_${app.interval}`], 0.05]);
  if (filters.vegetation !== "all") conditions.push(["==", ["get", "ndvi_direction"], filters.vegetation]);
  if (filters.evidence.length) {
    const evidenceConditions = filters.evidence.map((property) => ["==", ["get", property], true]);
    conditions.push([filters.evidenceMatch === "all" ? "all" : "any", ...evidenceConditions]);
  }
  return ["all", ...conditions];
}

function applyFilters() {
  if (!app.features) return;
  const filters = currentFilters();
  const count = app.features.features.reduce((total, feature) => total + (featurePasses(feature.properties, filters) ? 1 : 0), 0);
  $("resultCount").textContent = `${count.toLocaleString()} shown`;
  $("minAreaValue").textContent = `${formatNumber(filters.minArea, 1)} ha`;
  $("evidenceMatchControl").hidden = filters.evidence.length < 2;
  $("legend").hidden = !filters.hotspots && !filters.coldspots;
  updateSurfaceVisibility(filters);
  if (app.map?.getLayer("regions-fill")) {
    const expression = mapFilterExpression(filters);
    app.map.setFilter("regions-fill", expression);
    app.map.setFilter("regions-outline", expression);
  }
}

function renderLegend(annual = false) {
  if (annual) {
    $("legend").innerHTML = `<div class="legend-title">Change during selected period</div>
      <div class="legend-row"><span class="legend-chip" style="background:#a5243c"></span><span>Higher change</span></div>
      <div class="legend-row"><span class="legend-chip" style="background:#e7a047"></span><span>Moderate change</span></div>
      <div class="legend-row"><span class="legend-chip cold"></span><span>Low-change area</span></div>`;
    return;
  }
  $("legend").innerHTML = `<div class="legend-title">Change pattern</div>
    <div class="legend-row"><span class="legend-chip repeat"></span><span>Widespread repeated</span></div>
    <div class="legend-row"><span class="legend-chip mixed"></span><span>Some repeated</span></div>
    <div class="legend-row"><span class="legend-chip single"></span><span>Change mainly once</span></div>
    <div class="legend-row"><span class="legend-chip cold"></span><span>Mostly unchanged</span></div>`;
}

function setInterval(interval) {
  app.interval = interval;
  updateTransitionPeriod();
  const periodFilter = $("annualHotspotsOnly");
  periodFilter.disabled = interval === "endpoint";
  if (interval === "endpoint") periodFilter.checked = false;
  document.querySelectorAll(".time-step").forEach((button) => button.classList.toggle("active", button.dataset.interval === interval));
  $("timeViewLabel").textContent = INTERVAL_LABELS[interval];
  const imageryYear = interval === "endpoint" ? 2024 : Number(interval.split("_")[1]);
  setImageryYear(imageryYear);
  if (app.map?.getLayer("regions-fill")) {
    if (interval === "endpoint") {
      app.map.setPaintProperty("regions-fill", "fill-color", behaviourColourExpression());
      app.map.setPaintProperty("regions-fill", "fill-opacity", ["case", ["boolean", ["feature-state", "hover"], false], 0.82, 0.57]);
      setSurfaceLayers(app.metadata.hotspot_surface_overlay);
      renderLegend(false);
    } else {
      const changeProperty = `change_${interval}`;
      const hotspotProperty = `hotspot_${interval}`;
      app.map.setPaintProperty("regions-fill", "fill-color", ["case",
        ["==", ["get", "feature_type"], "coldspot_patch"], "#2c70a5",
        ["interpolate", ["linear"], ["coalesce", ["get", changeProperty], 0], 0.1, "#f2dcae", 0.25, "#e7a047", 0.45, "#d26329", 0.7, "#a5243c"]]);
      app.map.setPaintProperty("regions-fill", "fill-opacity", ["case",
        ["boolean", ["feature-state", "hover"], false], 0.9,
        ["==", ["get", "feature_type"], "coldspot_patch"], 0.42,
        ["interpolate", ["linear"], ["coalesce", ["get", hotspotProperty], 0], 0, 0.2, 0.25, 0.52, 1, 0.82]]);
      setSurfaceLayers(app.metadata.annual_overlays[interval]);
      renderLegend(true);
    }
  }
  applyFilters();
  if (app.selectedDetail) renderDetail();
}

async function selectFeature(featureId, zoomTo = false) {
  const properties = app.featureLookup.get(featureId);
  if (!properties) return;
  app.selectedId = featureId;
  app.selectedDetail = null;
  app.selectedTab = "overview";
  $("detailPanel").hidden = false;
  $("detailState").textContent = behaviourInfo(properties.behaviour).label;
  $("detailTitle").textContent = properties.feature_type === "coldspot_patch" ? "Low-change area" : "Landscape change area";
  $("detailLocation").textContent = `${properties.lat.toFixed(5)}, ${properties.lon.toFixed(5)} · ${featureId}`;
  $("detailContent").innerHTML = `<div class="detail-loading"><span class="spinner"></span></div>`;
  document.querySelectorAll(".detail-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === "overview"));
  if (app.map?.getLayer("selected-outline")) app.map.setFilter("selected-outline", ["==", ["get", "feature_id"], featureId]);
  if (zoomTo) app.map.easeTo({ center: [properties.lon, properties.lat], zoom: Math.max(app.map.getZoom(), 13), duration: 650 });
  try {
    const detail = await getDetail(featureId);
    if (app.selectedId !== featureId) return;
    app.selectedDetail = detail;
    renderDetail();
    reverseGeocode(detail.lat, detail.lon, featureId);
  } catch (error) {
    $("detailContent").innerHTML = `<div class="plain-summary">${escapeHtml(error.message)}</div>`;
  }
}

function closeDetails() {
  app.selectedId = null;
  app.selectedDetail = null;
  $("detailPanel").hidden = true;
  if (app.map?.getLayer("selected-outline")) app.map.setFilter("selected-outline", ["==", ["get", "feature_id"], ""]);
}

async function reverseGeocode(lat, lon, featureId) {
  try {
    const url = new URL("https://nominatim.openstreetmap.org/reverse");
    url.searchParams.set("format", "jsonv2"); url.searchParams.set("lat", lat); url.searchParams.set("lon", lon); url.searchParams.set("zoom", "16");
    const response = await fetch(url, { headers: { "Accept-Language": "en-AU,en" } });
    if (!response.ok) return;
    const result = await response.json();
    if (app.selectedId !== featureId || !result.display_name) return;
    const locality = result.address?.town || result.address?.village || result.address?.city || result.address?.municipality || result.address?.county || result.display_name.split(",")[0];
    const prefix = app.selectedDetail?.feature_type === "coldspot_patch" ? "Low-change area near" : "Landscape change near";
    $("detailTitle").textContent = `${prefix} ${locality}`;
    $("detailLocation").textContent = `${result.display_name} · ${featureId}`;
  } catch (_) {
    // Coordinates and the stable region ID remain available offline.
  }
}

function metricCard(label, value, note = "", explanation = "") {
  return `<div class="metric"><span>${escapeHtml(label)}${explanation ? help(explanation) : ""}</span><strong>${escapeHtml(value)}</strong>${note ? `<small>${escapeHtml(note)}</small>` : ""}</div>`;
}

function behaviourSummary(detail) {
  const repeat = Math.round(Number(detail.repeat_change_coverage) * 100);
  if (detail.region_behaviour === "low_change_reference") return "Little or no strong embedding change was detected here across the study period.";
  if (detail.region_behaviour === "repeated_change") return `${repeat}% of this area changed strongly in at least two annual periods. Repeated change was therefore widespread across the area.`;
  if (detail.region_behaviour === "mixed_change") return `${repeat}% of this area changed strongly in at least two annual periods. Some parts changed repeatedly, while others changed once or not strongly.`;
  if (repeat === 0) return "Strong change was detected, but no part of this area crossed the annual strong-change threshold in more than one period.";
  return `Strong change was mostly isolated to one annual period at each location. ${repeat}% of the area changed strongly more than once.`;
}

function evidenceBadge(label, active, sourceClass) {
  return `<span class="evidence-badge ${active ? "active" : ""}"><span class="source-dot ${sourceClass}"></span>${escapeHtml(label)}: ${active ? "change detected" : "no change signal"}</span>`;
}

function renderDetail() {
  const detail = app.selectedDetail;
  if (!detail) return;
  $("detailState").textContent = behaviourInfo(detail.region_behaviour).label;
  if (app.selectedTab === "overview") renderOverview(detail);
  if (app.selectedTab === "timeline") renderTimeline(detail);
  if (app.selectedTab === "context") renderContext(detail);
  if (window.lucide) lucide.createIcons();
}

function renderOverview(detail) {
  const selectedChange = app.interval === "endpoint" ? detail.endpoint_change_mean : detail[`annual_change_${app.interval}`];
  const changeLabel = app.interval === "endpoint" ? "Start-to-end change" : `Change ${INTERVAL_LABELS[app.interval]}`;
  const selectedCoverage = app.interval === "endpoint" ? detail.endpoint_hotspot_fraction : detail[`annual_hotspot_${app.interval}_fraction`];
  const coverageLabel = app.interval === "endpoint" ? "Area with strong change" : "Area with strong change this period";
  const coverageHelp = app.interval === "endpoint"
    ? "Percentage of this area whose direct first-year-versus-last-year embedding distance exceeded the endpoint strong-change threshold. This is separate from counting strong annual periods."
    : `Percentage of this area whose embedding change exceeded the annual strong-change cut-off during ${INTERVAL_LABELS[app.interval]}.`;
  const behaviour = behaviourInfo(detail.region_behaviour);
  $("detailContent").innerHTML = `
    <div class="metric-grid">
      ${metricCard(changeLabel, formatNumber(selectedChange, 3), "embedding distance", "Average Euclidean distance between satellite-embedding vectors across this region. Larger values mean stronger landscape-signal change.")}
      ${metricCard("Region area", `${formatNumber(detail.area_m2 / 10000, 2)} ha`, "", "Area inside the connected region boundary, measured in hectares.")}
      ${metricCard("Strongest change period", String(detail.strongest_change_interval).replace("-", " → "), "", "The annual period with the largest average embedding change in this region.")}
      ${metricCard("Total change activity", plainLabel(detail.overall_activity), "compared with other hot spots", "The seven annual embedding distances are added together. Hot spots are then split into three equal-sized groups: low, moderate and high total activity.")}
    </div>
    <section class="content-section"><h3>Pattern summary</h3><div class="plain-summary">${escapeHtml(behaviourSummary(detail))}</div></section>
    <section class="content-section">
      <h3>Region evidence</h3>
      <div class="status-line"><span>Overall change pattern ${help("Whole-period description based on the percentage of this area that changed strongly in at least two annual periods.")}</span><strong class="badge ${behaviour.className}">${escapeHtml(behaviour.label)}</strong></div>
      <div class="status-line"><span>Repeated change across area ${help("Percentage of this area where strong change occurred in two or more annual periods. The periods do not need to be consecutive, so this value describes the full study period and does not change with the timeline.")}</span><strong>${formatPercent(detail.repeat_change_coverage, 0)}</strong></div>
      <div class="status-line"><span>${escapeHtml(coverageLabel)} ${help(coverageHelp)}</span><strong>${formatPercent(selectedCoverage, 0)}</strong></div>
      <div class="status-line"><span>Year-to-year pattern ${help("For each cell, variance is calculated across its seven annual embedding-change values and then averaged across this area. Compared with other hot spots, low variance means the annual values were similar; high variance means one or a few years stood out.")}</span><strong>${escapeHtml(patternLabel(detail.year_to_year_pattern))}</strong></div>
      <div class="status-line"><span>Change intensity trend ${help("A straight line is fitted through each cell’s seven annual embedding-change values, and the slopes are averaged across this area. Positive means change magnitude tended to increase; negative means it tended to decrease. This is not ecological improvement or decline.")}</span><strong>${escapeHtml(trendLabel(detail.change_intensity_trend))}</strong></div>
    </section>
    <section class="content-section"><h3>Supporting datasets</h3><div class="evidence-badges">
      ${evidenceBadge("AI embedding", detail.embedding_change_signal, "embedding")}
      ${evidenceBadge("DEA land cover", detail.dea_transition_signal, "dea")}
      ${evidenceBadge("NDVI", detail.ndvi_change_signal, "ndvi")}
    </div></section>
    <details class="advanced-details"><summary>Detailed values</summary>
      <div class="status-line"><span>Average strong-change count ${help("For each approximately 30 m cell, count how many of the seven annual periods exceeded the strong-change cut-off, then average those counts across this area.")}</span><strong>${formatNumber(detail.mean_hotspot_intervals, 1)} of 7</strong></div>
      <div class="status-line"><span>Most repeated cell ${help("Largest strong-change count found in any approximately 30 m cell inside this area.")}</span><strong>${formatNumber(detail.maximum_hotspot_intervals, 0)} of 7</strong></div>
      <div class="status-line"><span>Year-to-year variability ${help("Average variance of the seven annual embedding distances. Larger values mean the annual change magnitudes were less even.")}</span><strong>${formatNumber(detail.variance_mean, 5)}</strong></div>
      <div class="status-line"><span>Change trend slope ${help("Average linear-regression slope fitted to the seven annual embedding distances. Positive means change magnitude tended to rise; negative means it tended to fall.")}</span><strong>${formatNumber(detail.slope_mean, 5)}</strong></div>
      <div class="status-line"><span>Seven-period change total ${help("Average cumulative change: the seven annual embedding distances added together. It is a relative signal magnitude, not physical area or percentage.")}</span><strong>${formatNumber(detail.cumulative_change_mean, 3)}</strong></div>
    </details>
    <a class="maps-link" href="https://www.google.com/maps?q=${detail.lat},${detail.lon}" target="_blank" rel="noreferrer"><i data-lucide="external-link"></i>Open coordinate in Google Maps</a>`;
}

function lineChart(values, labels, colour, cssClass, fixedDomain = null) {
  const finite = values.filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value))).map(Number);
  if (!finite.length) return "";
  let minimum = fixedDomain ? fixedDomain[0] : Math.min(...finite);
  let maximum = fixedDomain ? fixedDomain[1] : Math.max(...finite);
  if (!fixedDomain) {
    const padding = (maximum - minimum || Math.max(Math.abs(maximum), 0.1)) * 0.12;
    minimum = Math.max(0, minimum - padding); maximum += padding;
  }
  const width = 350, height = 116, left = 31, right = 8, top = 9, bottom = 21;
  const x = (index) => left + (index * (width - left - right)) / Math.max(1, labels.length - 1);
  const y = (value) => top + ((maximum - value) / (maximum - minimum || 1)) * (height - top - bottom);
  let started = false;
  const path = values.map((value, index) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "";
    const command = started ? "L" : "M"; started = true;
    return `${command}${x(index).toFixed(1)},${y(Number(value)).toFixed(1)}`;
  }).join(" ");
  const circles = values.map((value, index) => value === null || value === undefined || !Number.isFinite(Number(value)) ? "" : `<circle class="chart-dot" cx="${x(index)}" cy="${y(Number(value))}" r="3" fill="${colour}"></circle>`).join("");
  const grid = [minimum, (minimum + maximum) / 2, maximum].map((value) => `<line class="chart-grid" x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}"></line><text class="chart-label" x="${left - 4}" y="${y(value) + 3}" text-anchor="end">${value.toFixed(2)}</text>`).join("");
  const xLabels = labels.map((label, index) => `<text class="chart-label" x="${x(index)}" y="${height - 5}" text-anchor="middle">${escapeHtml(label)}</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" role="img">${grid}<path class="${cssClass}" d="${path}"></path>${circles}${xLabels}</svg>`;
}

function renderTimeline(detail) {
  const annualIntervals = INTERVALS.filter((interval) => interval !== "endpoint");
  const embedding = annualIntervals.map((interval) => detail[`annual_change_${interval}`]);
  const embeddingLabels = annualIntervals.map((interval) => `${interval.slice(2, 4)}–${interval.slice(7, 9)}`);
  const years = app.metadata.years.map(String);
  const ndvi = years.map((year) => detail.annual_context[year]?.ndvi_mean ?? null);
  const rows = annualIntervals.map((interval) => {
    const endYear = interval.split("_")[1];
    return `<tr class="${app.interval === interval ? "selected-year" : ""}"><td>${escapeHtml(INTERVAL_LABELS[interval])}</td><td>${formatNumber(detail[`annual_change_${interval}`], 3)}</td><td>${formatPercent(detail[`annual_hotspot_${interval}_fraction`], 0)}</td><td>${formatNumber(detail.annual_context[endYear]?.ndvi_mean, 3)}</td></tr>`;
  }).join("");
  $("detailContent").innerHTML = `
    <div class="chart-section"><div class="chart-heading"><strong>AI embedding change</strong><span>Euclidean distance</span></div><div class="chart-wrap">${lineChart(embedding, embeddingLabels, "#c66b1f", "chart-line-embedding")}</div></div>
    <div class="chart-section"><div class="chart-heading"><strong>Vegetation greenness</strong><span>NDVI · −1 to 1</span></div><div class="chart-wrap">${lineChart(ndvi, years.map((year) => year.slice(2)), "#1e7a69", "chart-line-ndvi", [-1, 1])}</div></div>
    <section class="content-section"><h3>Annual values</h3><table class="year-table timeline-values-table"><thead><tr><th>Period</th><th>Change</th><th>Strong-change area</th><th>NDVI</th></tr></thead><tbody>${rows}</tbody></table></section>`;
}

function renderContext(detail) {
  const context = detail.annual_context;
  const start = context["2017"], end = context["2024"];
  const firstChange = Number(detail.dea_level3_first_change_year) > 0 ? String(detail.dea_level3_first_change_year) : null;
  const broadChanged = Boolean(detail.dea_level3_changed);
  const sameEndpointClass = start.dea_level3 === end.dea_level3;
  let landHeadline;
  let landNote;
  if (!broadChanged) {
    landHeadline = `Stayed ${start.dea_level3}`;
    landNote = "The dominant mapped broad class was unchanged in every annual DEA map.";
  } else if (sameEndpointClass) {
    landHeadline = `Returned to ${end.dea_level3}`;
    landNote = `The dominant mapped broad class first changed in ${firstChange || "an intermediate year"}, then returned by 2024.`;
  } else {
    landHeadline = `${start.dea_level3} → ${end.dea_level3}`;
    landNote = `The first change in the dominant mapped broad class was detected in ${firstChange || "the annual sequence"}.`;
  }
  const ndviChange = Number(detail.ndvi_endpoint_change);
  const ndviAction = ndviChange > 0 ? "increased" : ndviChange < 0 ? "decreased" : "was unchanged";
  const ndviNote = `Average NDVI ${ndviAction}${ndviChange === 0 ? "" : ` by ${formatNumber(Math.abs(ndviChange), 3)}`} between the first and last study years.`;
  const rows = app.metadata.years.map((year, index) => {
    const item = context[String(year)];
    const previous = index > 0 ? context[String(app.metadata.years[index - 1])] : null;
    const broadTransition = previous && previous.dea_level3 !== item.dea_level3;
    const secondary = Number(item.dea_level3_secondary_share) >= 0.15
      ? `<span class="land-secondary">Also present: ${escapeHtml(item.dea_level3_secondary)} (${formatPercent(item.dea_level3_secondary_share, 0)})</span>` : "";
    const eventLabels = [
      broadTransition ? `<span class="year-event land-event">Land-cover change</span>` : "",
      item.ndvi_change_event ? `<span class="year-event ndvi-event">Vegetation change from ${app.metadata.years[index - 1]}</span>` : "",
    ].join("");
    const detailedClass = item.dea_level4 && item.dea_level4 !== "Unknown 0" ? item.dea_level4 : "Detailed class unavailable";
    return `<tr>
      <td class="year-cell"><strong>${year}</strong>${eventLabels}</td>
      <td class="land-cell"><span class="land-class">${escapeHtml(item.dea_level3)} <small>${formatPercent(item.dea_level3_share, 0)}</small></span><span class="land-detail"><b>Detailed:</b> ${escapeHtml(detailedClass)} (${formatPercent(item.dea_level4_share, 0)})</span>${secondary}</td>
      <td class="ndvi-cell">${formatNumber(item.ndvi_mean, 3)}</td>
    </tr>`;
  }).join("");
  $("detailContent").innerHTML = `
    <section class="context-summary">
      <div class="context-summary-row">
        <span>Land cover across study period ${help("Uses the dominant DEA Level 3 broad land-cover class for each year. A change means the mapped dominant class changed; it does not identify the cause.")}</span>
        <strong>${escapeHtml(landHeadline)}</strong>
        <p>${escapeHtml(landNote)}</p>
      </div>
      <div class="context-summary-row">
        <span>Vegetation greenness across study period ${help("Compares average regional NDVI in the final study year with the first. It describes satellite-observed greenness, not ecological condition by itself.")}</span>
        <strong>${escapeHtml(directionLabel(detail.ndvi_direction))}</strong>
        <p>${escapeHtml(ndviNote)}</p>
      </div>
    </section>
    <details class="context-history" open>
      <summary>Annual land and vegetation history</summary>
      <table class="year-table land-history-table"><thead><tr><th class="year-col">Year</th><th>DEA land cover <small>broad / detailed</small></th><th class="ndvi-col">NDVI</th></tr></thead><tbody>${rows}</tbody></table>
    </details>`;
}

function resetFilters() {
  $("showHotspots").checked = true; $("showColdspots").checked = true;
  $("landTransition").value = "all"; $("changePattern").value = "all"; $("minArea").value = 0; $("annualHotspotsOnly").checked = false;
  $("evidenceDea").checked = false; $("evidenceNdvi").checked = false;
  $("vegetationDirection").value = "all"; app.evidenceMatch = "all";
  document.querySelectorAll(".match-option").forEach((button) => button.classList.toggle("active", button.dataset.match === "all"));
  applyFilters();
}

function parseCoordinates(query) {
  const match = query.trim().match(/^(-?\d{1,3}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)$/);
  if (!match) return null;
  const first = Number(match[1]), second = Number(match[2]);
  if (first < 0 && second > 100) return [second, first];
  if (second < 0 && first > 100) return [first, second];
  return null;
}

async function search(query) {
  const requestId = ++app.searchRequest;
  const normalized = query.trim().toLowerCase();
  if (!normalized) return renderSearchResults([]);
  const results = [];
  const coords = parseCoordinates(query);
  if (coords) results.push({ name: "Coordinate", detail: `${coords[1].toFixed(5)}, ${coords[0].toFixed(5)}`, center: coords });
  Array.from(app.featureLookup.values()).filter((item) => item.feature_id.toLowerCase().startsWith(normalized)).slice(0, 5).forEach((item) => results.push({ name: item.feature_id, detail: behaviourInfo(item.behaviour).label, center: [item.lon, item.lat], featureId: item.feature_id }));
  LOCAL_PLACES.filter((place) => `${place.name} ${place.detail}`.toLowerCase().includes(normalized)).slice(0, 5).forEach((place) => results.push(place));
  if (requestId === app.searchRequest) renderSearchResults(results.slice(0, 8));
  if (normalized.length >= 3 && !coords) {
    try {
      const [west, south, east, north] = app.metadata.bounds;
      const url = new URL("https://nominatim.openstreetmap.org/search");
      url.searchParams.set("format", "jsonv2"); url.searchParams.set("q", `${query}, Victoria, Australia`); url.searchParams.set("countrycodes", "au"); url.searchParams.set("viewbox", `${west},${north},${east},${south}`); url.searchParams.set("bounded", "1"); url.searchParams.set("limit", "4");
      const response = await fetch(url, { headers: { "Accept-Language": "en-AU,en" } });
      if (response.ok) (await response.json()).forEach((item) => results.push({ name: item.name || item.display_name.split(",")[0], detail: item.display_name, center: [Number(item.lon), Number(item.lat)] }));
    } catch (_) { /* Local search remains available offline. */ }
  }
  if (requestId === app.searchRequest) renderSearchResults(results.slice(0, 8));
}

function renderSearchResults(results) {
  const panel = $("searchResults");
  if (!results.length) { panel.hidden = true; panel.innerHTML = ""; return; }
  panel.innerHTML = results.map((result, index) => `<button class="search-result" data-result-index="${index}"><strong>${escapeHtml(result.name)}</strong><span>${escapeHtml(result.detail)}</span></button>`).join("");
  panel.hidden = false;
  panel.querySelectorAll(".search-result").forEach((button) => button.addEventListener("click", () => activateSearchResult(results[Number(button.dataset.resultIndex)])));
}

function activateSearchResult(result) {
  $("searchInput").value = result.name; $("searchResults").hidden = true;
  if (result.featureId) return selectFeature(result.featureId, true);
  app.map.flyTo({ center: result.center, zoom: 14, duration: 750 });
  if (app.searchMarker) app.searchMarker.remove();
  app.searchMarker = new maplibregl.Marker({ color: "#12766d" }).setLngLat(result.center).addTo(app.map);
}

function shiftInterval(direction) {
  const current = INTERVALS.indexOf(app.interval);
  setInterval(INTERVALS[Math.max(0, Math.min(INTERVALS.length - 1, current + direction))]);
}

function bindEvents() {
  ["showHotspots", "showColdspots", "landTransition", "changePattern", "minArea", "annualHotspotsOnly", "evidenceDea", "evidenceNdvi", "vegetationDirection"].forEach((id) => $(id).addEventListener("input", applyFilters));
  document.querySelectorAll(".match-option").forEach((button) => button.addEventListener("click", () => {
    app.evidenceMatch = button.dataset.match;
    document.querySelectorAll(".match-option").forEach((item) => item.classList.toggle("active", item === button));
    applyFilters();
  }));
  $("resetFilters").addEventListener("click", resetFilters); $("fitBounds").addEventListener("click", fitBounds);
  $("basemapToggle").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleBasemapMenu();
  });
  document.querySelectorAll(".basemap-option").forEach((button) => button.addEventListener("click", () => setBasemap(button.dataset.basemap)));
  $("previousImageryYear").addEventListener("click", () => shiftImageryYear(-1));
  $("nextImageryYear").addEventListener("click", () => shiftImageryYear(1));
  $("zoomIn").addEventListener("click", () => app.map.zoomIn()); $("zoomOut").addEventListener("click", () => app.map.zoomOut());
  $("locateMe").addEventListener("click", () => navigator.geolocation?.getCurrentPosition((position) => activateSearchResult({ name: "Current location", detail: "Browser location", center: [position.coords.longitude, position.coords.latitude] })));
  $("closeDetails").addEventListener("click", closeDetails);
  document.querySelectorAll(".detail-tab").forEach((tab) => tab.addEventListener("click", () => {
    app.selectedTab = tab.dataset.tab;
    document.querySelectorAll(".detail-tab").forEach((item) => item.classList.toggle("active", item === tab));
    renderDetail();
    $("detailContent").scrollTop = 0;
  }));
  document.querySelectorAll(".time-step").forEach((button) => button.addEventListener("click", () => setInterval(button.dataset.interval)));
  $("previousTime").addEventListener("click", () => shiftInterval(-1)); $("nextTime").addEventListener("click", () => shiftInterval(1));
  let timer = null;
  $("searchInput").addEventListener("input", (event) => { clearTimeout(timer); timer = setTimeout(() => search(event.target.value), 250); });
  $("searchInput").addEventListener("keydown", (event) => { if (event.key === "Escape") $("searchResults").hidden = true; });
  $("clearSearch").addEventListener("click", () => { $("searchInput").value = ""; $("searchResults").hidden = true; if (app.searchMarker) app.searchMarker.remove(); });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) $("searchResults").hidden = true;
    if (!event.target.closest(".basemap-control")) closeBasemapMenu();
  });
  $("openFilters").addEventListener("click", () => $("sidebar").classList.add("open")); $("closeFilters").addEventListener("click", () => $("sidebar").classList.remove("open"));
  const dialog = $("aboutDialog");
  $("showAbout").addEventListener("click", () => dialog.showModal()); $("closeAbout").addEventListener("click", () => dialog.close());
  document.addEventListener("mouseover", (event) => {
    const button = event.target.closest(".help-tip, .inline-help");
    if (button && !app.helpPinned) showHelpPopover(button, false);
  });
  document.addEventListener("mouseout", (event) => {
    const button = event.target.closest(".help-tip, .inline-help");
    if (button && !button.contains(event.relatedTarget)) hideHelpPopover(true);
  });
  document.addEventListener("focusin", (event) => {
    const button = event.target.closest(".help-tip, .inline-help");
    if (button && !app.helpPinned) showHelpPopover(button, false);
  });
  document.addEventListener("focusout", (event) => {
    if (event.target.closest(".help-tip, .inline-help")) hideHelpPopover(false);
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".help-tip, .inline-help");
    if (!button) return hideHelpPopover(true);
    event.preventDefault();
    const closeCurrent = app.helpPinned && app.helpAnchor === button;
    closeCurrent ? hideHelpPopover(true) : showHelpPopover(button, true);
  });
  window.addEventListener("resize", () => hideHelpPopover(true));
  document.addEventListener("scroll", () => hideHelpPopover(true), true);
}

async function initialize() {
  try {
    if (window.lucide) lucide.createIcons();
    await loadData();
    $("headerSummary").textContent = `${app.metadata.feature_count.toLocaleString()} regions · annual embedding, DEA and NDVI history`;
    $("hotspotCount").textContent = app.metadata.hotspot_feature_count.toLocaleString();
    $("coldspotCount").textContent = app.metadata.coldspot_feature_count.toLocaleString();
    updateImageryYearControl();
    updateTransitionPeriod();
    updateMapStatus();
    bindEvents(); renderLegend(false); createMap();
  } catch (error) {
    $("mapLoading").innerHTML = `<strong>Map failed to start</strong><span>${escapeHtml(error.message)}</span>`;
    console.error(error);
  }
}

initialize();
