# Bass Coast Phase 3 DEA Land Cover Pipeline Report

Generated at: 2026-06-22T00:24:52

## Purpose

This local Phase 3 pipeline attaches DEA Land Cover histories to sampled embedding-change points and summarizes the resulting DEA sequence patterns. It replaces the earlier separate Phase 3A and Phase 3B scripts.

## Coverage

- Points processed: 89707
- Complete DEA Level 3 sequences: 89707/89707 (100.0%)
- DEA Level 3 changed points: 57823/89707 (64.5%)
- DEA Level 4 changed points: 79053/89707 (88.1%)

## Category-Level DEA Agreement

| category | points | level3_changed_points | level3_changed_share | level4_changed_points | level4_changed_share |
| --- | --- | --- | --- | --- | --- |
| positive_slope | 9971 | 7526 | 0.755 | 9080 | 0.911 |
| persistent_ge3 | 9946 | 7395 | 0.744 | 9906 | 0.996 |
| persistent_ge2 | 9984 | 7168 | 0.718 | 9817 | 0.983 |
| temporary_or_recovery_candidate | 9926 | 6786 | 0.684 | 9147 | 0.922 |
| high_variance | 9950 | 6784 | 0.682 | 9207 | 0.925 |
| negative_slope | 9976 | 6563 | 0.658 | 8965 | 0.899 |
| endpoint_hotspot | 10000 | 6478 | 0.648 | 8819 | 0.882 |
| sudden_candidate | 9954 | 6135 | 0.616 | 8398 | 0.844 |
| stable_control | 10000 | 2988 | 0.299 | 5714 | 0.571 |

## Most Common 2017-2024 Level 3 Transitions

| level3_2017 | level3_2024 | level3_transition_2017_2024 | points |
| --- | --- | --- | --- |
| Cultivated Terrestrial Vegetation | Cultivated Terrestrial Vegetation | Cultivated Terrestrial Vegetation -> Cultivated Terrestrial Vegetation | 34175 |
| Natural Terrestrial Vegetation | Natural Terrestrial Vegetation | Natural Terrestrial Vegetation -> Natural Terrestrial Vegetation | 25443 |
| Natural Terrestrial Vegetation | Cultivated Terrestrial Vegetation | Natural Terrestrial Vegetation -> Cultivated Terrestrial Vegetation | 20931 |
| Cultivated Terrestrial Vegetation | Natural Terrestrial Vegetation | Cultivated Terrestrial Vegetation -> Natural Terrestrial Vegetation | 3184 |
| Natural Terrestrial Vegetation | Artificial Surface | Natural Terrestrial Vegetation -> Artificial Surface | 1550 |
| Artificial Surface | Artificial Surface | Artificial Surface -> Artificial Surface | 1064 |
| Cultivated Terrestrial Vegetation | Artificial Surface | Cultivated Terrestrial Vegetation -> Artificial Surface | 935 |
| Natural Terrestrial Vegetation | Natural Bare Surface | Natural Terrestrial Vegetation -> Natural Bare Surface | 354 |
| Water | Water | Water -> Water | 258 |
| Natural Terrestrial Vegetation | Water | Natural Terrestrial Vegetation -> Water | 242 |
| Cultivated Terrestrial Vegetation | Natural Bare Surface | Cultivated Terrestrial Vegetation -> Natural Bare Surface | 219 |
| Natural Aquatic Vegetation | Natural Aquatic Vegetation | Natural Aquatic Vegetation -> Natural Aquatic Vegetation | 199 |

## Most Common Level 3 Sequence Types

| level3_sequence_type | points |
| --- | --- |
| temporary_or_return_to_start | 29439 |
| natural_to_cultivated_vegetation | 20931 |
| stable_natural | 16995 |
| stable_cultivated | 13685 |
| cultivated_to_natural_vegetation | 3184 |
| transition_to_artificial_surface | 2532 |
| water_aquatic_or_bare_involved | 1447 |
| stable_artificial_surface | 738 |
| transition_from_artificial_surface | 290 |
| stable_natural_aquatic_vegetation | 182 |
| stable_water | 178 |
| stable_natural_bare_surface | 106 |

## First DEA Change Timing Alignment

| category | points | level3_changed_points | match_max_year_pm1 | match_first_hotspot_year_pm1 | match_max_year_pm1_share_of_changed | match_first_hotspot_year_pm1_share_of_changed |
| --- | --- | --- | --- | --- | --- | --- |
| endpoint_hotspot | 10000 | 6478 | 2754 | 1848 | 0.425 | 0.285 |
| high_variance | 9950 | 6784 | 2686 | 2792 | 0.396 | 0.412 |
| negative_slope | 9976 | 6563 | 4107 | 1655 | 0.626 | 0.252 |
| persistent_ge2 | 9984 | 7168 | 2799 | 3872 | 0.390 | 0.540 |
| persistent_ge3 | 9946 | 7395 | 2766 | 4778 | 0.374 | 0.646 |
| positive_slope | 9971 | 7526 | 1114 | 737 | 0.148 | 0.098 |
| stable_control | 10000 | 2988 | 1163 | 0 | 0.389 | 0.000 |
| sudden_candidate | 9954 | 6135 | 2739 | 1144 | 0.446 | 0.186 |
| temporary_or_recovery_candidate | 9926 | 6786 | 2511 | 2522 | 0.370 | 0.372 |

## Interpretation

A high Level 3 change share in embedding-change categories compared with stable controls indicates that the embedding categories are enriched for real DEA-observed land-cover transitions. This is a validation signal, not a strict accuracy score, because DEA is a broad categorical product and does not capture every possible ecosystem or condition change.

## Position For Next Phase

This script is built to run either the 900-point review table or the larger Phase 2 sampled table. For the next phase, use the same local pipeline with chunk/checkpoint support on the larger sampled table, not all 191 million raster pixels.
