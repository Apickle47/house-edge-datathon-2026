# Sealed comparison: candidate_short_main vs baseline_general_main

Run once on the sealed set: 8 scenarios × 40 episodes × 4 masks, 2,216 machines per mask (8,864 forecasts per entry).
Evaluator: Claude (Cowork), Sat Nov 7, ~2:50 PM CT. Linux, Python 3.13.

## Integrity
| Item | SHA-256 | Status |
|---|---|---|
| Benchmark ZIP | 090d643d99be751ecf3fbeefe18335a1947b3188337ba84f7aeee99d75bf7476 | as shipped |
| Sealed truth | 7fabf32aa963bb288e191d98e8e308ecd075bd2c495965ae5a133df5f503f802 | verified before scoring |
| Baseline entry (house_edge_general_main) | 0ae79c2581911b32bf0bc9aa84bfa5745c55a762cf5cf2e07fcb3b5a38eb6184 | 32/32 runs rc=0, 50.8 s total, no missing forecasts |
| Candidate entry (house_edge_short_main) | ff580b4d6e1c94166dbae6ee15cd7c102bc1f26a71219234260ed7c80e3f0154 | 32/32 runs rc=0, 66.6 s total, no missing forecasts |

Extra checks on the candidate: a Linux rerun of entry.zip on the released kit matches submission.csv within 2.2e-16 (tolerance 1e-8). The checker accepts the test CSV. Rescoring validation_predictions.csv gives 58.848472/60. model.json (849 KB, mostly gap_tables) has only global parameters, with no query, machine or episode IDs.

## Overall
- Equal-weight mean error over the 32 cells: pooled_ref 0.13098, baseline 0.05265, **candidate 0.03699**.
- Paired difference (candidate − baseline): **−0.01566, 95% CI [−0.01727, −0.01401]**. Bootstrap: 4,000 resamples of independent episodes within each scenario, with all four masks of an episode kept together.
- Excluding xor3: mean cell difference −0.00027 (essentially neutral).

Per scenario (all masks pooled, episode bootstrap):
      and_rule    +0.00001 [-0.00116, +0.00141]
      changes     -0.00191 [-0.00396, +0.00010]
      constant    +0.00015 [-0.00036, +0.00068]
      main_like   +0.00032 [-0.00102, +0.00167]
      new_pairs   -0.00023 [-0.00109, +0.00059]
      size_indep  -0.00039 [-0.00192, +0.00113]
      weak_dep    +0.00018 [-0.00031, +0.00071]
      xor3        -0.12341 [-0.13570, -0.11149]

## Scenario × mask (per-cell paired bootstrap, 2,000 resamples, not adjusted for 32 comparisons)
| scenario | mask | pooled_ref | baseline_general_main | candidate_short_main | diff (cand-base) [95% CI] |
|---|---|---|---|---|---|
| and_rule | full | 0.10345 | 0.01802 | 0.01828 | +0.00026 [-0.00010, +0.00076] tie |
| and_rule | gaps35 | 0.10519 | 0.06745 | 0.06871 | +0.00126 [-0.00270, +0.00631] tie |
| and_rule | recent40_older24 | 0.10466 | 0.03762 | 0.03630 | -0.00132 [-0.00325, +0.00040] tie |
| and_rule | window48 | 0.10750 | 0.03055 | 0.03039 | -0.00016 [-0.00118, +0.00085] tie |
| changes | full | 0.18934 | 0.02306 | 0.02292 | -0.00014 [-0.00040, +0.00000] tie |
| changes | gaps35 | 0.19148 | 0.11463 | 0.10950 | -0.00513 [-0.01257, +0.00174] tie |
| changes | recent40_older24 | 0.18093 | 0.02084 | 0.01859 | -0.00225 [-0.00612, +0.00097] tie |
| changes | window48 | 0.17360 | 0.02491 | 0.02479 | -0.00012 [-0.00080, +0.00059] tie |
| constant | full | 0.00235 | 0.00840 | 0.00837 | -0.00002 [-0.00005, -0.00000] WIN |
| constant | gaps35 | 0.00355 | 0.00911 | 0.00851 | -0.00059 [-0.00158, +0.00026] tie |
| constant | recent40_older24 | 0.00892 | 0.01812 | 0.01846 | +0.00034 [-0.00114, +0.00177] tie |
| constant | window48 | 0.01117 | 0.01778 | 0.01865 | +0.00087 [+0.00019, +0.00169] REGRESSION |
| main_like | full | 0.18565 | 0.01403 | 0.01402 | -0.00001 [-0.00004, +0.00001] tie |
| main_like | gaps35 | 0.18752 | 0.10068 | 0.10210 | +0.00141 [-0.00380, +0.00614] tie |
| main_like | recent40_older24 | 0.18411 | 0.01184 | 0.01167 | -0.00017 [-0.00157, +0.00137] tie |
| main_like | window48 | 0.18606 | 0.01146 | 0.01153 | +0.00007 [-0.00045, +0.00055] tie |
| new_pairs | full | 0.19298 | 0.01689 | 0.01693 | +0.00004 [-0.00000, +0.00011] tie |
| new_pairs | gaps35 | 0.19186 | 0.11759 | 0.11690 | -0.00069 [-0.00208, +0.00059] tie |
| new_pairs | recent40_older24 | 0.18737 | 0.03477 | 0.03401 | -0.00077 [-0.00306, +0.00115] tie |
| new_pairs | window48 | 0.18862 | 0.02721 | 0.02770 | +0.00048 [-0.00076, +0.00216] tie |
| size_indep | full | 0.17783 | 0.02070 | 0.02070 | -0.00000 [-0.00002, +0.00000] tie |
| size_indep | gaps35 | 0.18010 | 0.10738 | 0.10404 | -0.00334 [-0.00900, +0.00215] tie |
| size_indep | recent40_older24 | 0.17211 | 0.01535 | 0.01691 | +0.00156 [-0.00007, +0.00339] tie |
| size_indep | window48 | 0.17232 | 0.01464 | 0.01488 | +0.00023 [-0.00017, +0.00068] tie |
| weak_dep | full | 0.01224 | 0.01112 | 0.01112 | +0.00000 [-0.00006, +0.00008] tie |
| weak_dep | gaps35 | 0.01328 | 0.01824 | 0.01859 | +0.00035 [-0.00067, +0.00141] tie |
| weak_dep | recent40_older24 | 0.01598 | 0.02376 | 0.02369 | -0.00008 [-0.00111, +0.00094] tie |
| weak_dep | window48 | 0.01664 | 0.02271 | 0.02315 | +0.00044 [+0.00006, +0.00088] REGRESSION |
| xor3 | full | 0.18794 | 0.18480 | 0.01414 | -0.17066 [-0.19009, -0.15336] WIN |
| xor3 | gaps35 | 0.18863 | 0.18854 | 0.15258 | -0.03596 [-0.05042, -0.02259] WIN |
| xor3 | recent40_older24 | 0.18304 | 0.17951 | 0.03954 | -0.13998 [-0.16091, -0.11916] WIN |
| xor3 | window48 | 0.18480 | 0.17305 | 0.02602 | -0.14703 [-0.16268, -0.13113] WIN |

## Wins and regressions
- Wins (CI below 0): xor3 in all four masks (large: −0.036 to −0.171), plus constant/full (negligible, −0.00002).
- Regressions (CI above 0): constant/window48 +0.00087 [+0.00019, +0.00169]; weak_dep/window48 +0.00044 [+0.00006, +0.00088]. Both are small, both occur when there's no strong pattern and only 48 recent spins, and both repeat the dev-set constant/window48 regression.
- Every other cell is a tie. There's no meaningful change on main_like, new_pairs, and_rule, changes or size_indep.

## Recommendation (Claude)
**Prefer the candidate over the baseline.** On sealed synthetic data it is clearly better overall, driven by the new 3-lag rules. Outside that it is roughly neutral, with two small regressions in no-pattern, short-window cases. On the released kit it also scores higher (58.848 vs 58.590), and its own analysis puts the public-score gain's 95% interval at −0.07 to +0.81 points, so the main-round gain is likely but uncertain. Both entries reproduce, pass the checker and use only the Python standard library at inference.

Caveat: these are synthetic scenarios Claude designed. The candidate's big win is in a scenario (3-lag parity) that may or may not appear in the organizers' data. The sealed set is now spent, so any further candidate comparison should use a new seed range.
