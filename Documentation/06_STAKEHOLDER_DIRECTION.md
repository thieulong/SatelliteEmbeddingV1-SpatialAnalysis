# Stakeholder Direction

This file records project direction communicated through supervisor, manager,
team and presentation feedback. It is paraphrased rather than copied from
private correspondence.

## Research direction

The central interest is not only whether an AI embedding changes, but whether
embedding-space change can reveal useful landscape dynamics beyond traditional
spectral indices.

A supervisor highlighted prior success using NDVI thresholding and Bayesian
methods for vegetation/fuel-condition monitoring. The important limitation was
that NDVI alone may not distinguish canopy, forest floor and other object or
structural effects. This led to the working comparison question:

> Can embedding-space change metrics detect vegetation degradation and
> restoration patterns as well as, or better than, traditional indices such as
> NDVI?

Implications retained in the project:

- compare embedding magnitude with absolute NDVI change;
- preserve signed NDVI direction separately;
- inspect known disturbance/restoration sites when reliable event data becomes
  available;
- evaluate performance by land/object type;
- consider time-series modelling and clustering only after the baseline is
  well validated; and
- do not expect perfect embedding-NDVI correlation because the embedding may
  contain broader information.

## Product direction

Managers and collaborators want a map that non-specialists can explore. The
product should show both change and low-change references, allow temporal
navigation, and explain what supporting data says about selected areas.

Key UX decisions from review:

- Use `AusHabitat` as the product name and show the CNPS identity.
- Prefer plain-language labels and concise hover/click explanations.
- Keep specialist numerical metrics under a detailed-values section.
- Do not present evidence tiers as confidence scores.
- Separate AI embedding detection from DEA/NDVI supporting evidence filters.
- Make the normal map default; let users opt into historical imagery.
- Report actual historical imagery capture dates.
- Avoid filters that duplicate existing controls or require expert knowledge.
- Keep the timeline compact and readable over both map and satellite views.

## Communication direction

Technical reports and presentations should use the following story:

1. Landscape monitoring problem and motivation.
2. Embeddings detect change magnitude but not meaning.
3. DEA adds annual land-cover context.
4. NDVI adds signed vegetation context.
5. Sampled diagnostics establish feasibility.
6. Wall-to-wall processing establishes spatial coverage.
7. The interactive map demonstrates practical delivery.
8. Results are contextual agreement, not causal classification accuracy.

Use visuals, maps and a concrete case study before detailed equations. Define
terms such as embedding, raster, hotspot, persistence and NDVI once in plain
language.

## Requested coordinate-extraction capability

A team member asked whether the project can extract embeddings for 46 supplied
latitude/longitude coordinates, including:

- the exact 10 m embedding cell; and
- median embedding values for several buffer sizes around each coordinate.

This is feasible and is a useful future utility. Requirements still to confirm:

- years needed;
- buffer radii or square window sizes;
- whether to return the 64 raw dimensions, temporal distances, or both;
- edge/nodata rules; and
- coordinate reference and point identifiers.

Implement it as a windowed coordinate-extraction tool, not by loading the full
embedding cube. Preserve raw vectors and derived summaries in separate columns
or files.

## Long-term vision

- Expand from Bass Coast to Australia.
- Deliver a reliable online map, then consider a mobile/PWA experience.
- Allow people to inspect where change is strong or low, navigate years, view
  land-cover and vegetation histories, and follow evidence to source data.
- Add new datasets only when they answer a defined interpretation question.
- Explore predictive modelling only when validated targets and an explicit
  decision use case exist.
