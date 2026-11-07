# Mock adaptation rehearsal: sealed scoring report

Scored once by Claude (Cowork) against the committed sealed truth. Linux, Python 3.13, the kit's own `contest_score` (max 40), with the test reference = official pooled starter fitted on mock train.

## Integrity
| Item | SHA-256 | Check |
|---|---|---|
| Mock kit ZIP | 486ad8026f347dbd82334b2f141b48aa63c324cb8f0eaf075cc58edb6f2f693c | matches FOR_CLAUDE.txt |
| Sealed test truth | 9625c03eddeeb05ee1dcee72bd800676835ffab987060f83921920b27cb9eb62 | matches the commitment made before forecasts existed |
| A_pooled_starter.csv | 3a4e52a1…a926 | matches; identical to Claude's own starter run |
| B_unchanged_peer_main.csv | 6903aaa8…35f4 | matches |
| C_refitted_peer_main.csv | 85aaadd9…7659 | matches |

All three: 1,536 rows, 0 missing, 0 extra, 0 duplicate, 0 invalid probability rows.
C reproduction: extracting `C_reproduction_only.zip` and running `python predict.py --data <mock public> --out ...` on Linux/Python 3.13 reproduced C within 2.2e-16 in 23 s. `model.json` contains no query, machine or episode IDs. The checker accepts C's test format.

## Results (test, out of 40)
| Entry | Points | stable | short_history | drift | shared_change |
|---|---:|---:|---:|---:|---:|
| A pooled starter | **20.00** | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| B unchanged peer_main | **25.68** | 0.1110 | 0.2300 | 1.0024 | 0.8859 |
| C refitted peer_main | **35.91** | 0.0560 | 0.0989 | 0.1661 | 0.1352 |

Condition columns are normalized error ratios versus the pooled reference (lower is better).

**Paired C − B: +10.22 points, 95% CI [+9.34, +11.03]** (400 resamples of whole episodes within condition).
Validation vs test for C: 36.32 vs 35.91. The small drop means no meaningful overfitting to mock validation.
Build time reported by Codex: about 205 s (fit + validation + package + reproduction). Prediction: 23 s on Linux.

## Hidden rules (now unsealed) and what C learned
| Hidden rule | Truth | C's checkpoint |
|---|---|---|
| Win lag pairs | (1,4), (3,6), (2,7) | pairs (3,6), (2,7), (1,4) ✅ exact |
| Win rule | XOR for 80% of machines, **AND for 20%** | XOR family only |
| Peer delay | lag 5 on 60% of machines, none on 40% | peer_lag 5 ✅ |
| Size regime | per-machine table over big (≥2x) payouts at (1,3), (2,6) or (3,5) | size rules over (1,3), (3,5), (2,6) ✅ |
| Conditions | drift = per-machine gradual reversal; shared_change = episode-wide flip | handled for XOR machines |

## Where the remaining error is (mean summed squared error per query, C)
| | XOR machines | AND machines |
|---|---:|---:|
| stable | 0.0086 | 0.0131 |
| short_history | 0.0121 | 0.0323 |
| drift | **0.0115** | **0.1206** |
| shared_change | **0.0086** | **0.1085** |

**Finding:** refitting works and is essential (+10 points). Almost all of C's remaining drift and shared-change error comes from the 20% of AND-rule machines when their rule reverses. Their error is about 10–12× that of XOR machines, and about the same as the unchanged model (B: 0.123 / 0.116). The general binary tables do not seem to track reversal over time for non-XOR rules.

**Suggested hardening for round two (Codex):** let the general 2-lag table hypotheses use the same forgetting/change-point machinery as the XOR specialist (or add an explicit AND/NAND orientation with reversal), and confirm discovery reports which rule family each machine uses. Only worth doing if it is cheap and validated, since the real round two may not contain AND rules.

## Decision for tonight
Use the refit pipeline (`build_round.py --round adaptation`) on the real round-two kit. Never submit the unchanged main checkpoint for round two.
