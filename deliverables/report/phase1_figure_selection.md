# Phase 1 Figure Selection for Updated Technical Report

This note records the figures selected for the next extension of the AusHabitat technical progress report. Existing report figures already use `fig1.png` through `fig11.png`; new DEA-related figures therefore start at `fig12.png`.

## Selected Figures

| New file | Source file | Intended report role |
| --- | --- | --- |
| `fig12.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_dea_level3_2017_2024.png` | Introduces DEA Land Cover as an external contextual dataset by showing Level 3 land-cover state at the start and end of the study period. |
| `fig13.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_dea_change_share_by_category.png` | Main evidence figure showing that embedding-derived change categories have higher DEA-observed land-cover change shares than stable controls. |
| `fig14.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_phase3_vs_phase5_comparison.png` | Demonstrates that the sampled Phase 3 result is consistent with the Phase 5 wall-to-wall result. |
| `fig15.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_top_level3_transitions.png` | Summarizes the dominant broad DEA Level 3 endpoint transitions associated with the embedding categories. |
| `fig16.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_level3_sequence_types.png` | Summarizes full 2017-2024 DEA Level 3 sequence behaviour rather than only endpoint transitions. |
| `fig17.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_timing_alignment.png` | Shows how DEA first-change timing aligns with embedding-derived timing metrics. |
| `fig18.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_dea_level3_sequence_type.png` | Provides a spatial map of DEA Level 3 sequence types across the Bass Coast study area. |
| `fig19.png` | `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_hotspot_dea_sequence_overlay.png` | Connects embedding endpoint hotspots with DEA sequence types, making the link between AI-derived hotspots and land-cover history visually interpretable. |

## Figures Considered But Not Copied

| Source file | Reason not selected for the main report continuation |
| --- | --- |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_category_pixel_counts.png` | Useful as a technical diagnostic, but less central than change-share, transition and map figures. Pixel counts can be reported in text or a table if needed. |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_endpoint_change.png` | Similar endpoint-change content is already represented by existing `fig8.png`. |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_endpoint_hotspots.png` | Useful but mostly superseded by `fig19.png`, which overlays hotspots with DEA sequence context. |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_persistence_count.png` | Similar persistence content is already represented by existing `fig5.png`. |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_slope_annual_change.png` | Similar slope content is already represented by existing `fig6.png`. |
| `BassCoast_Phase6_Visualization_Report_outputs/figures/phase6_map_max_change_year.png` | Useful for detailed timing discussion, but not essential for the concise progress-report continuation. |
| `BassCoast_Phase4_Visualization_Report_outputs/phase4_*` | Earlier sampled/reporting figures are now superseded by the Phase 5 wall-to-wall and Phase 6 figures. |
| `BassCoast_Phase2_Pixel_Sampling_outputs/map_phase2b_review_points.png` | Operationally useful for review-point selection, but too process-specific for the main technical progress narrative. |

## Suggested Placement

- `fig12.png`: Section 7, when introducing DEA Land Cover as an external land-cover history layer.
- `fig13.png`: Section 8 or 9, as the main validation/enrichment result.
- `fig14.png`: Section 9, after explaining why the wall-to-wall summary was needed.
- `fig15.png` and `fig16.png`: Section 9, when interpreting what broad DEA transitions and sequences dominate.
- `fig17.png`: Section 9 or 10, when discussing temporal agreement between embedding metrics and DEA first-change year.
- `fig18.png`: Section 10, for spatial visualization of DEA sequence histories.
- `fig19.png`: Section 10, as the strongest visual link between embedding hotspots and DEA land-cover histories.
