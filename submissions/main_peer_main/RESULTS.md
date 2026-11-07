# Main entry comparison

The submitted entry is house_edge_short_main. This candidate uses the observed win frequency of other machines at a delay learned from calibration episodes. Both calibration halves selected a three-tick delay. It also estimates the frequency of changes in machine behavior from training histories and can pool stable payout estimates among similar machines within one episode. The final forecast reads only test queries and histories before the cutoff.

## Released validation

| Official result | Submitted | Candidate |
|---|---:|---:|
| Main validation points out of 60 | 58.848472 | **59.035628** |
| Stable loss ratio | 0.008177 | 0.006744 |
| Short-history loss ratio | 0.044922 | 0.038809 |
| Drift loss ratio | 0.015254 | 0.011160 |
| Shared-change loss ratio | 0.009918 | 0.008629 |

The checker used all 768 validation queries. Each prediction excluded its episode from model fitting. Of 96 episodes, 58 had lower error. The 0.1872-point increase had a paired bootstrap interval of +0.057 to +0.350 points when resampling whole episodes within condition. This interval describes sampling variability on a public set used for development. The final leaderboard uses private targets.

## Fresh simulation comparison

Both frozen ZIPs were run locally on Claude's simulator using a fresh seed range beginning at 4733000, with 32 independent episodes per scenario and four matched masks per episode. The simulator provided the exact odds for each cutoff. All 7,084 forecasts per entry passed probability and ID checks. There were 256 distinct latent episodes. None of these synthetic examples were used to train the candidate.

Equal-weight mean squared probability-vector error was **0.03961** for the submitted entry and **0.03984** for this candidate. The paired difference was +0.00022, with 95% bootstrap interval [-0.00017, +0.00062]. The bootstrap sampled episodes within each scenario and kept each episode's four masks together. The simulator shares mechanisms with Claude's earlier benchmark; fresh seeds test new episodes within these mechanisms. This is a local comparison, separate from Claude's independent evaluation of the previous pair.

| Simulated behavior | Submitted error | Candidate error |
|---|---:|---:|
| and_rule | 0.03993 | 0.04045 |
| changes | 0.04848 | 0.05162 |
| constant | 0.01532 | 0.01181 |
| main_like | 0.03773 | 0.03787 |
| new_pairs | 0.04428 | 0.04506 |
| size_indep | 0.04765 | 0.04763 |
| weak_dep | 0.01893 | 0.01767 |
| xor3 | 0.06456 | 0.06657 |

Full scenario and mask results are in fresh-comparison.json. The official checker accepted the 1,536-query test CSV, and a fresh extraction of entry.zip reproduced it byte-for-byte. The ZIP and CSV are a matched pair.
