# House Edge (TAMU Datathon 2026): working notes

## Deadlines (Central)
- Main round closes Sat Nov 7, 9 PM. Submit through the Google Form (latest response counts).
- Round two (adaptation) kit opens 9 PM. Submissions close Sun Nov 8, 11 AM.
- Points: main 60 + adaptation 40 (RULES.md). The guide said 80/20; RULES.md wins.

## Submissions made / ready
- v1 baseline (pooled starter): 30.0 validation points. Downloads\house_edge_baseline
- v2: 54.4. Downloads\house_edge_v2
- v3: 57.14 (stable .036, short .089, drift .039, shared .037). Downloads\house_edge_v3
  Code: housemodel.py + predict.py, stdlib only, deterministic, about 15 s.

## What the simulator does (main round)
- Win = hidden on/off state. On iff XOR or XNOR (per machine) of win-status at a lag pair, one of (1,3), (2,5), (4,7).
  It can reverse over time (drift/shared change), which forgetting handles.
- Win logit by type, off/on: steady -1.77/3.02, balanced -3.12/1.74, jackpot -4.53/0.31. Signal slope about +0.38 logit.
  Residual of about ±0.5 logit, partly an episode-wide time-varying shift.
- Size given win: exactly two fixed distributions per type (P(1x) steady .455/.754, balanced .214/.500, jackpot .121/.335;
  the 2:5:20 ratios are fixed per type). The regime depends on big (>=2x) payouts at a lag pair, one of (1,2), (1,4), (2,4), with
  an arbitrary per-machine table.
- fit_constants() re-estimates the size regimes, on/off levels and signal slope from validation/targets.csv at run time.

## Round-two plan
1. Unzip the new kit to a separate folder. Run predict.py --split validation and score with check_submission.py.
2. Re-check whether the lag pairs changed: search lag pairs for win (XOR) and size (big), as in szsearch.py/ep.py.
3. Update PAIRS / SIZE_PAIRS if needed, then rebuild the CSV and ZIP and verify a fresh-folder reproduction.

## Update: optimized model (built by Arush's terminal assistant). Recommended main submission.
- Folder: Downloads\house_edge_optimized_main (submission.csv + entry.zip). Validation 58.57 (leave-episode-out).
- Independently verified by Claude (Cowork) on its own random half/half episode split: 58.74 and 58.32 vs v3 57.22 and 57.02.
- On Linux/Python 3.13, a fresh-folder rerun matches the CSV within 2.2e-16 (tolerance 1e-8). The checker passes. model.json holds global parameters only, and the predictor filters ticks < cutoff.
- Key extra findings: payout-size regime is tied to the win pair; there is a shared episode "weather" state with change timing.
- Round two: run source/build_round.py --round adaptation --kit <extracted kit> --out ./adaptation-run (needs local Anaconda numpy for fitting).

## Collaboration with Codex (Sat afternoon)
- Codex owns the predictor; current baseline is Downloads\house_edge_general_main (entry SHA 0ae79c25...6184, validation 58.59, reads the test folder only, runtime alternatives).
- Claude owns the independent benchmark: Downloads\house_edge_claude_benchmark (zip SHA 090d643d...7476). 8 scenarios x 4 masks; dev has 8 episodes per scenario, sealed has 40 per scenario. Sealed truth is held by Claude (SHA 7fabf32a...f802; kept in /home/claude/bench/sealed_keep in this session; regenerable with generate.py).
- Dev weak spots of the baseline: no 3-lag parity, large degradation with 35% random gaps, slightly worse than pooled where no pattern exists.
- Next: the candidate ZIP from Codex leads to one sealed paired run (run_entry.py + score.py --set sealed).

## Sealed comparison done (~2:50 PM): RECOMMEND house_edge_short_main
- Candidate Downloads\house_edge_short_main (entry SHA ff580b4d...0154, validation 58.848) vs baseline general_main (58.590).
- Sealed synthetic: candidate error 0.03699 vs 0.05265; paired diff -0.0157 [-0.0173, -0.0140]. The gain is almost all 3-lag XOR; other scenarios are neutral. Small regressions: constant/window48 and weak_dep/window48.
- Linux reproduction within 2.2e-16; checker passes. Sealed set is now spent; use new seeds for any further comparison.
- Report: Downloads\house_edge_claude_benchmark\sealed_results.md

## Dashboard Royale (side entry, built Sat ~3 PM)
- Package: Downloads\dashboard_royale (dashboard_royale.html, WRITEUP.md, CLAIMS_AND_EVIDENCE.md incl. AI disclosure, VIDEO_SCRIPT.md, zip with code). Published artifact "Luck, Location, or a Leak?" (private until shared).
- Findings: 9/10 of the bottom ten are in the Back Forty; the walkway closure (Mar 3 to Apr 7) gave a -31% relative drop. M-1158 hit rate 38.6% vs 31.5% (z about 124). Comp points per $ cut 12.5 to 5.8 in late April. Weekday forecast MAE $69k vs $218k.
- Plan: inspect 5 ($6,000) + Back Forty wayfinding ($7,500) + comp pilot ($4,000); hold $82,500.
- Still needed from Arush: a public dashboard link or file upload on Devpost, and recording the 2-minute video.

## Sealed comparison #2 (~3:15 PM): peer_main vs short_main. RECOMMEND peer_main (modest)
- peer_main entry SHA 2f533822...c465, validation 59.0356 (+0.19 vs short_main, CI +0.057..+0.350).
- Sealed v2 synthetic (10 scenarios incl. peer_lag3/5): diff +0.00022 [-0.00003,+0.00048], a tie. Wins: constant, weak_dep, peer_lag3. Losses: short-history new_pairs/xor3/changes.
- Verified: Linux repro within 2.2e-16, checker passes, no IDs in model.json. The v2 sealed set is now spent.

## Round-two rehearsal scored (~5 PM)
- Mock adaptation kit (season 5c719147f8b11fc50266ddc0). Test: A starter 20.00, B unchanged peer_main 25.68, C refit (build_round.py) 35.91 / 40. C − B = +10.22 [+9.34, +11.03].
- C rediscovered the hidden win pairs, peer lag 5 and size pairs exactly. Its weakness: AND-rule machines under drift/shared_change (error about 10x XOR).
- C reproduces on Linux within 2.2e-16; build about 205 s, predict 23 s. Tonight: always use the refit pipeline; never submit the unchanged checkpoint.
- Report: Downloads\house_edge_mock_adaptation\RESULTS_FROM_CLAUDE\SEALED_SCORE_REPORT.md

## "Push further" test (~5:30 PM): main model is at its ceiling
- Reran peer_main at cutoffs 1–16 ticks earlier on validation; the model's recent misses (y − p), pooled per episode or per machine, do not predict the cutoff-time residual (|corr| <= 0.10 for windows 2/4/8/16; null SE about 0.10 with 96 episodes).
- The cutoff-time episode shift looks like unobservable noise. No further main-round work recommended.

## Consensus (~6:30 PM): main final; round-two builder rehearsed
- Codex and Claude independently verified SUBMIT_house_edge_peer_main (59.0356; alt split 59.023; leakage-free; sandboxed Linux rerun within 2.2e-16).
- New builder (ROUND_TWO_house_edge_builder) on fresh mock (season 339a5d47...): 128 s, picked the reversal variant, val 36.50 vs sealed test 36.57.
- Checklist: Downloads\CONSENSUS_CHECKLIST.md
