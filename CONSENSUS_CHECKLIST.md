# House Edge: agreed status and round-two checklist (Claude + Codex, Sat ~6:30 PM CT)

## Main round: FINAL, keep as submitted
Entry: Downloads\SUBMIT_house_edge_peer_main (entry.zip 2f533822...c465, submission.csv 67fa8d86...b16e)
| Check | Codex | Claude |
|---|---|---|
| Validation points (episode-held-out) | 59.035628; alternate split 59.023 | 59.035628 (rescored) |
| Leakage | held-out answers physically removed; identical forecasts | no IDs in model.json; inputs < cutoff |
| Reproduction | byte-identical (Windows); fake future payouts change nothing | Linux/Py3.13, no network, sandboxed: within 2.2e-16 (limit 1e-8), 12 s |
| Format | checker valid | checker valid; CSV 199 KB; ZIP root correct, no symlinks |
Still on Arush: confirm the Google Form shows "response recorded" for these two files.
59.04 is a verified validation result, not a guaranteed leaderboard score.

## Round two: builder ready
Builder: Downloads\ROUND_TWO_house_edge_builder (RUN_AT_9.md). It refits on the new kit and picks the "two-lag reversal" variant only if it wins both validation halves by at least 0.10 points.
Claude's Linux dress rehearsal on a FRESH mock kit (season 339a5d4727d3667ce5e537a6, new seeds):
- Exit 0, 128 s end to end; selected reversal (folds 34.05→36.32, 35.84→36.66); fresh-ZIP reproduction byte-identical.
- Validation 36.50 / 40 vs sealed test **36.57 / 40**, so the validation estimate is reliable. Earlier builder on the first mock: 35.91.

## 9 PM steps
1. Download the official adaptation kit and extract it to a NEW folder. Check that public/metadata.json says "adaptation".
2. Codex runs: build_round.py --round adaptation --kit <kit> --out .\real-adaptation-run
3. Claude checks: round, season, query IDs, validation score, selected method, independent Linux regeneration from the ZIP, hashes.
4. Arush uploads real-adaptation-run\submission.csv + entry.zip through the ADAPTATION form and saves the confirmation.
   Target done by about 10 PM; hard deadline 11 AM Sunday.
5. Never upload the unchanged main checkpoint for round two (rehearsal: about 10 points worse).
Fallback if the build fails: send Claude the error. The pooled starter (about 20/40) is the last resort, not a blank entry.
