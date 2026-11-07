# Short history candidate

The frozen main-round pair is entry.zip and submission.csv. The official kit checker scored episode-wise cross-fitted validation predictions at **58.848472/60**, up from **58.590101/60** for house_edge_general_main. The short-history loss ratio fell from 0.062906 to 0.044922, a 28.6% reduction. The other three ratios agreed to within 0.000001. The final checkpoint uses all available public calibration episodes after validation.

The short-history model averages over unknown lagged spins using the stationary distribution implied by each supported candidate rule and its fitted odds. This helps distinguish possible rules when few consecutive older observations are available. For unfamiliar machines, the fallback now also checks 56 possible three-lag combinations with both parity and unrestricted binary tables. On the released kit the gap change alone scored 58.846407/60.

## Validation uncertainty

Mean error improved in 21 of the 24 short-history episodes. One episode contributed much of the total improvement. A paired bootstrap of whole episodes, stratified by condition, gave a 95% interval of −0.07 to +0.81 points for the difference. This is a measured public-score gain; the organizer's private score is unknown. Independently masking each of 72 longer released validation episodes to 40 recent and 24 older observations lowered mean per-episode error from 0.00577 to 0.00511. These episodes were excluded from calibration for their predictions, and the public validation set has been used for model development.

## Claude's development suite

Both frozen entries ran on Claude's development inputs. The baseline was house_edge_general_main. Each of eight unfamiliar scenarios had eight independent episodes and four matched masks. All 32 candidate runs completed and the scorer reported no missing forecasts.

| Mean per-episode summed squared probability error | Baseline | Candidate |
|---|---:|---:|
| Across all scenarios and masks | 0.05979 | 0.04543 |
| Across scenarios with the 40 recent and 24 older mask | 0.05132 | 0.03640 |
| Across all masks, excluding three-lag XOR | 0.04132 | 0.04073 |

Most of the gain came from three-lag XOR. The per-cell paired intervals showed eight wins, 22 inconclusive comparisons, and two regressions. Constant odds with a 48-spin window worsened from 0.01812 to 0.02155. The other regression was very small, from 0.01226 to 0.01229 for unseen lag pairs with full history. The 32 per-cell intervals are exploratory and are not adjusted for multiple comparisons. Full cell results are in claude-dev-scores.json. Claude retains the sealed evaluation truth. Its result is pending.

## Reproduction

The official checker validated the final 1,536 test forecasts. Running the extracted code ZIP reproduced the CSV byte-for-byte. The prediction command requires only the Python standard library and the supplied test inputs. checks.txt contains the checker output. FOR_CLAUDE.txt identifies both frozen archives for independent verification.
