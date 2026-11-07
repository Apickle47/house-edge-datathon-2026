# House Edge: TAMU Datathon 2026 (team backup and handoff)

This is a private backup of everything the team (Arush, with Codex and Claude as assistants) built for the **House Edge** slot-machine forecasting challenge, plus the Dashboard Royale side entry. It's written so another agent can pick up the work cold.

## Status (Sat Nov 7, 2026, ~7 PM Central)

| Round | Status | Entry | Score |
|---|---|---|---|
| Main (60 pts) | **Submitted, final** (closes 9 PM CT Sat) | `submissions/main_peer_main/` | **59.0356 / 60** on public validation (episode-held-out); alternate split 59.023 |
| Adaptation / round two (40 pts) | Kit opens **9 PM CT Sat**, due **11 AM CT Sun** | build with `round_two_builder/` | rehearsal: 35.9–36.6 / 40 on mock kits |

The official scores come from private test answers after judging. 59.04 is a verified validation result, not a leaderboard number.

**Submitted main pair (must stay matched):**
- `submissions/main_peer_main/entry.zip`: SHA-256 `2f53382209ab7c0e729d9bb0bb2546b8caa83c5a1b3cd41fd392da4398c5f465`
- `submissions/main_peer_main/submission.csv`: SHA-256 `67fa8d869e2a538973fa96d7214085b25089d7ae651548976c8a58b82378e16f`

Verified independently by Codex (scoring, leakage, byte-identical replay, fake-future-payout test) and Claude (rescoring, Linux/Python 3.13 sandboxed rerun with no network, within 2.2e-16; limit 1e-8). See `CONSENSUS_CHECKLIST.md`.

## Round two: what to do at 9 PM
Full instructions: `round_two_builder/RUN_AT_9.md` and `CONSENSUS_CHECKLIST.md`.
1. Download the official adaptation kit and extract it to a new folder. `public/metadata.json` must say `adaptation`.
2. Build (local fit needs NumPy; the packed entry is standard library only):
   ```
   python round_two_builder/source/build_round.py --round adaptation --kit <extracted-kit> --out ./real-adaptation-run
   ```
   It refits on the new kit, runs two-fold episode validation, chooses between the ordinary refit and a "two-lag reversal" variant (the variant must win both halves and gain at least 0.10 points), packages `entry.zip`, and checks that it reproduces.
3. Verify: round, season, query IDs, validation score, the method chosen in `model-comparison.json`, and an independent regeneration of the test CSV from the ZIP.
4. Upload `real-adaptation-run/submission.csv` and `entry.zip` through the **adaptation** Google Form. Keep the confirmation.
5. **Never** upload the unchanged main checkpoint for round two. In the rehearsal it was about 10 points worse than refitting.

## What we learned about the simulator (main round)
- **Win chance:** each machine has a hidden on/off state set by XOR (or XNOR) of its wins at a lag pair: (1,3), (2,5) or (4,7). The pair and orientation are per machine. On/off logits by type: steady about −1.8/+3.0, balanced about −3.1/+1.7, jackpot about −4.5/+0.3. Signal slope is about +0.38 logit. Neighbours' wins 3 ticks earlier shift the odds (found by Codex).
- **Payout size given a win:** exactly two fixed distributions per type. The regime is set by whether payouts at a lag pair were big (2x or more).
- **Conditions:** drift = gradual per-machine reversal; shared_change = episode-wide change; short_history = 40 recent plus 24 sampled older ticks.
- **Ceiling:** the remaining error is mostly an episode-wide shift at the cutoff that cannot be predicted from history (Claude tested this; |corr| ≤ 0.1). The practical ceiling is about 59.1–59.3.

## Layout
| Path | Contents |
|---|---|
| `submissions/main_peer_main/` | Submitted main pair, validation predictions, checks, results, unpacked source (`predict.py`, `fit.py`, `build_round.py`, `model.json`, …) |
| `round_two_builder/` | Builder for tonight (`RUN_AT_9.md`, `source/`) |
| `history/` | Earlier entries: Claude v3 (57.14), Codex optimized (58.57), general (58.59), short (58.85) |
| `benchmarks/claude_benchmark_v1`, `_v2` | Claude's synthetic generalization benchmarks (`generate.py` recreates the data deterministically), scorers, and sealed comparison reports |
| `mock_adaptation/` | Round-two rehearsal: mock kit, frozen forecasts A/B/C, sealed scoring report (C refit 35.91 vs B 25.68), unsealed generator, fresh-seed rehearsal of the new builder (36.57) |
| `handoffs/` | Messages exchanged between Codex and Claude |
| `notes/HOUSE_EDGE_NOTES.md` | Running log of decisions and results |
| `dashboard_royale/` | Dashboard Royale entry (dashboard HTML, write-up, appendix, video script, code) |

## Not included
- The organizers' raw kit data. Download it from the participant guide's Data link (Google Drive `1WXrMzPXHv_ZuwpKvdRrcKYoJaMR5J6VV`, file `main-participants-60-40.zip`). The adaptation kit is released at 9 PM CT.
- Team tokens or credentials. Keep this repository **private**; it contains a live competition entry.

## Key links
- Main submission form: https://docs.google.com/forms/d/e/1FAIpQLSfv2WV_Fz7NHstRPN2TGi3pvMAFrcQuvs2SkQL1DqpdLebhFg/viewform
- Challenge list: https://tamudatathon.com/challenges · Devpost: https://tamu-datathon-26-casino-royale.devpost.com/
