# Main entry for broader evaluation data

Upload the matching submission.csv and entry.zip in this folder. The archive predicts from the supplied test queries, the histories before each cutoff, and a checkpoint fitted to organizer-released data. It requires only the Python standard library at inference. The code has no saved per-query forecasts, machine-ID lookup, external API, or test-label dependency.

The predictor compares the trained model with alternatives that estimate constant odds, changes in payout frequency, and relationships with individual lags or pairs of lags through eight ticks. It weighs their predictions using evidence from the incoming histories. Win frequency and the distribution of positive payouts can adapt separately. Machines can change at a different time from their neighbors.

## Released kit

The organizer checker scored the previous entry at 58.5652/60 and this entry at 58.5901/60 on 768 validation queries. Both use two-fold predictions with whole episodes excluded from fitting. Model development used this public validation set. The small score difference alone is weak evidence for any improvement on the private evaluation.

The final fit used the full public calibration set. All 1,536 test queries passed the checker. The extracted archive reproduced the submitted CSV byte-for-byte on the local machine. Public test inference took 25.3 seconds in the recorded run.

## Generalization checks

For the simulation comparison, each entry used its packaged checkpoint. No synthetic examples were used to fit the checkpoint. Each scenario used 32 newly generated episodes with different histories. There were 1,159 queries in total, including a machine type absent from training. Values are mean summed squared error across the five payout probabilities, averaged within each episode and then across episodes. Lower is better.

| Simulated machine behavior | Previous entry | This entry |
|---|---:|---:|
| Constant odds | 0.218045 | 0.006938 |
| Abrupt change in frequency | 0.246722 | 0.009854 |
| Single-lag win pattern | 0.334451 | 0.018928 |
| Lag pair absent from training | 0.345835 | 0.027013 |
| Different two-lag transition rule | 0.240952 | 0.021707 |
| Smooth drift | 0.267469 | 0.064380 |

A second comparison used 384 queries from 48 organizer validation episodes excluded from the calibration fits used for this check. Swapping the 1× and 5× payouts in both histories and probability targets reduced the previous entry's accuracy substantially. Mean summed squared error was 0.146527 for the previous entry and 0.021572 for this entry. With roughly half the observed spins randomly hidden, the two had essentially the same error, 0.133972 and 0.134017. Sparse histories remain a limitation. Actual organizer test odds and private scores are unavailable.
