# Sealed comparison #2: peer_main (candidate) vs short_main (submitted)

Benchmark v2 sealed set: 10 scenarios (adds peer_lag3 and peer_lag5, where machines react to their neighbors' wins 3 or 5 ticks earlier) × 40 episodes × 4 masks. Fresh seeds (7,000,000+), disjoint from every earlier set. Evaluator: Claude (Cowork), Linux, Python 3.13. Run once.

## Integrity
| Item | SHA-256 | Status |
|---|---|---|
| Sealed truth (v2) | 116c06eb9be2afe2f7ec525630f839a8a3c0dcb5a52bc6a75629dddd947ca943 | verified before scoring |
| short_main entry | ff580b4d6e1c94166dbae6ee15cd7c102bc1f26a71219234260ed7c80e3f0154 | 40/40 runs rc=0 |
| peer_main entry | 2f53382209ab7c0e729d9bb0bb2546b8caa83c5a1b3cd41fd392da4398c5f465 | 40/40 runs rc=0 |

Extra checks on peer_main: a Linux rerun of entry.zip on the released kit matches submission.csv within 2.2e-16. The checker accepts the 1,536-row test CSV. Rescoring validation_predictions.csv gives 59.035628/60. model.json has no query, machine or episode IDs.

## Overall
- Equal-weight error: short_main 0.03742, peer_main 0.03764.
- Paired difference (peer − short): **+0.00022, 95% CI [−0.00003, +0.00048]**. Episodes bootstrapped within scenario, masks kept together. **Statistically a tie**, leaning very slightly worse. This matches Codex's own fresh-seed run (+0.00022 [−0.00017, +0.00062]).

Per scenario (all masks):
      and_rule    +0.00005 [-0.00040, +0.00061]
      changes     +0.00174 [+0.00080, +0.00275]
      constant    -0.00155 [-0.00205, -0.00104]
      main_like   +0.00042 [-0.00010, +0.00096]
      new_pairs   +0.00141 [+0.00079, +0.00203]
      peer_lag3   -0.00087 [-0.00165, -0.00021]
      peer_lag5   +0.00006 [-0.00075, +0.00104]
      size_indep  +0.00025 [-0.00067, +0.00127]
      weak_dep    -0.00176 [-0.00243, -0.00109]
      xor3        +0.00245 [+0.00112, +0.00365]

## Scenario × mask
| scenario | mask | pooled_ref | short_main | peer_main | diff (cand-base) [95% CI] |
|---|---|---|---|---|---|
| and_rule | full | 0.10975 | 0.01951 | 0.01947 | -0.00004 [-0.00021, +0.00010] tie |
| and_rule | gaps35 | 0.10982 | 0.06757 | 0.06750 | -0.00007 [-0.00048, +0.00043] tie |
| and_rule | recent40_older24 | 0.11178 | 0.03136 | 0.03172 | +0.00035 [-0.00059, +0.00152] tie |
| and_rule | window48 | 0.10994 | 0.02737 | 0.02734 | -0.00002 [-0.00091, +0.00083] tie |
| changes | full | 0.19199 | 0.01668 | 0.01742 | +0.00074 [-0.00050, +0.00196] tie |
| changes | gaps35 | 0.19096 | 0.09941 | 0.10302 | +0.00361 [+0.00068, +0.00691] REGRESSION |
| changes | recent40_older24 | 0.18242 | 0.01736 | 0.01903 | +0.00167 [+0.00070, +0.00287] REGRESSION |
| changes | window48 | 0.18009 | 0.01947 | 0.02040 | +0.00093 [-0.00025, +0.00186] tie |
| constant | full | 0.00235 | 0.00706 | 0.00597 | -0.00110 [-0.00214, +0.00007] tie |
| constant | gaps35 | 0.00375 | 0.00844 | 0.00665 | -0.00179 [-0.00262, -0.00113] WIN |
| constant | recent40_older24 | 0.00799 | 0.01927 | 0.01697 | -0.00230 [-0.00362, -0.00123] WIN |
| constant | window48 | 0.01125 | 0.01962 | 0.01860 | -0.00102 [-0.00152, -0.00049] WIN |
| main_like | full | 0.19385 | 0.01257 | 0.01309 | +0.00051 [+0.00006, +0.00098] REGRESSION |
| main_like | gaps35 | 0.19724 | 0.09799 | 0.09789 | -0.00010 [-0.00160, +0.00139] tie |
| main_like | recent40_older24 | 0.18789 | 0.01236 | 0.01303 | +0.00066 [+0.00008, +0.00124] REGRESSION |
| main_like | window48 | 0.18711 | 0.01375 | 0.01434 | +0.00059 [+0.00008, +0.00117] REGRESSION |
| new_pairs | full | 0.18688 | 0.01094 | 0.01098 | +0.00004 [-0.00057, +0.00073] tie |
| new_pairs | gaps35 | 0.19051 | 0.12927 | 0.12927 | +0.00000 [-0.00063, +0.00065] tie |
| new_pairs | recent40_older24 | 0.17884 | 0.02603 | 0.03008 | +0.00405 [+0.00239, +0.00574] REGRESSION |
| new_pairs | window48 | 0.17906 | 0.01901 | 0.02057 | +0.00156 [+0.00074, +0.00248] REGRESSION |
| peer_lag3 | full | 0.17074 | 0.01650 | 0.01590 | -0.00060 [-0.00110, -0.00016] WIN |
| peer_lag3 | gaps35 | 0.16945 | 0.10224 | 0.10084 | -0.00140 [-0.00349, +0.00039] tie |
| peer_lag3 | recent40_older24 | 0.16577 | 0.01482 | 0.01413 | -0.00069 [-0.00120, -0.00019] WIN |
| peer_lag3 | window48 | 0.16518 | 0.01364 | 0.01286 | -0.00078 [-0.00134, -0.00030] WIN |
| peer_lag5 | full | 0.18765 | 0.01608 | 0.01625 | +0.00017 [-0.00144, +0.00154] tie |
| peer_lag5 | gaps35 | 0.18892 | 0.10766 | 0.10654 | -0.00112 [-0.00276, +0.00051] tie |
| peer_lag5 | recent40_older24 | 0.17888 | 0.01798 | 0.01862 | +0.00063 [-0.00026, +0.00176] tie |
| peer_lag5 | window48 | 0.18102 | 0.01663 | 0.01721 | +0.00057 [-0.00016, +0.00151] tie |
| size_indep | full | 0.18931 | 0.02182 | 0.02103 | -0.00079 [-0.00278, +0.00094] tie |
| size_indep | gaps35 | 0.19250 | 0.11738 | 0.11775 | +0.00037 [-0.00227, +0.00317] tie |
| size_indep | recent40_older24 | 0.18602 | 0.02337 | 0.02341 | +0.00004 [-0.00234, +0.00175] tie |
| size_indep | window48 | 0.18265 | 0.02223 | 0.02363 | +0.00140 [+0.00062, +0.00230] REGRESSION |
| weak_dep | full | 0.01395 | 0.01022 | 0.01018 | -0.00004 [-0.00043, +0.00029] tie |
| weak_dep | gaps35 | 0.01442 | 0.01768 | 0.01592 | -0.00175 [-0.00306, -0.00080] WIN |
| weak_dep | recent40_older24 | 0.01598 | 0.02375 | 0.02053 | -0.00322 [-0.00485, -0.00175] WIN |
| weak_dep | window48 | 0.01677 | 0.01907 | 0.01706 | -0.00201 [-0.00280, -0.00129] WIN |
| xor3 | full | 0.19244 | 0.01538 | 0.01491 | -0.00047 [-0.00153, +0.00011] tie |
| xor3 | gaps35 | 0.19636 | 0.15822 | 0.15986 | +0.00164 [+0.00025, +0.00323] REGRESSION |
| xor3 | recent40_older24 | 0.18561 | 0.04949 | 0.05524 | +0.00575 [+0.00232, +0.00894] REGRESSION |
| xor3 | window48 | 0.18569 | 0.03738 | 0.04025 | +0.00286 [+0.00067, +0.00517] REGRESSION |

## Reading
- **Wins:** no-pattern or weak-pattern machines (constant, weak_dep) in every short mask, and peer_lag3 (the neighbor effect the candidate was built for) in three of four masks.
- **Regressions:** the short-history masks of new_pairs, xor3 and changes, plus small regressions on main_like. The extra pooling and peer terms seem to cost a little when a machine has an unfamiliar rule and few observations.
- peer_lag5 (a neighbor effect at a different delay) is a tie, so the gain is specific to the lag-3 delay learned from the released data.

## Recommendation (Claude)
**Submit peer_main, with modest confidence.** The organizers' main test comes from the same simulator as the released validation set. On that data, peer_main is +0.19 points with an episode-bootstrap interval of +0.057 to +0.350, using cross-fitted, episode-held-out predictions, and it improves all four conditions. On out-of-distribution synthetic data it is a statistical tie overall: it wins where there's no pattern and loses some where unfamiliar rules meet short histories. So it gains on in-distribution data and is about even out of distribution. Caveat: public validation has now been used for several rounds of development, so the real gain is probably smaller than +0.19.

This sealed set is now spent.
