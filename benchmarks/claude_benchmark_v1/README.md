# House Edge independent benchmark (Claude)

A paired, masked synthetic benchmark for comparing two frozen House Edge entries. It uses the Python standard library only and is deterministic.

## Contents
- `generate.py`: the generator. `python generate.py --out .` recreates every file in `data/` and `truth/` byte for byte. `manifest.json` lists SHA-256 hashes, seeds and counts.
- `data/<set>/<scenario>/<mask>/test/{queries.csv,history.csv}`: kit schema, one data root per scenario and mask. Pass `--data data/<set>/<scenario>/<mask>` to `predict.py`.
- `truth/dev/truth.csv`: query_id, episode_id, scenario, mask, p_0, p_1, p_2, p_5, p_20. It is outside every data root.
- `truth/sealed/truth.csv`: **not shipped**. Claude keeps it until both entries are frozen. Its hash is in `manifest.json`, so tampering is detectable. Please don't regenerate or inspect the sealed set before the comparison, by agreement.
- `run_entry.py`: unpacks an entry ZIP and runs `predict.py --data ROOT --out FORECAST.csv` on every root.
- `score.py`: per-episode summed squared error, averaged by scenario x mask, with a built-in pooled reference. With two entries it reports paired episode differences (candidate minus baseline) and 2,000-resample bootstrap 95% intervals, labeled WIN, REGRESSION or tie.
- `results/dev/baseline_general_main/`: dev-set forecasts and log for the baseline. These are a pipeline check and development evidence only.
- `legacy_mock_suite/`: the earlier four-scenario stress test (code and results). It is not reproducible byte for byte; see its RESULTS.md.

## Design
- Sets: **dev** has 8 episodes per scenario (seeds 1000+). **sealed** has 40 episodes per scenario (seeds 900000+). Episodes and seed ranges don't overlap. Each episode has 4 to 10 machines and a cutoff between 192 and 256.
- Every spin is drawn from probabilities computed from earlier ticks only. The target is the probability vector at the cutoff, and no cutoff outcome is drawn.
- Masks are applied to the **same latent episodes and targets**: `full` (all ticks), `recent40_older24` (40 recent consecutive ticks plus 24 random older ones), `window48` (last 48 ticks only) and `gaps35` (each tick independently hidden with probability 0.35).
- Scenarios (machine-specific level offsets with sd 0.3, signal slope 0.38):
  - `constant`: no lag dependence; each machine has fixed odds. The size regime is fixed.
  - `weak_dep`: XOR over pairs (1,3), (2,5), (4,7), but the on and off levels are only 0.6 logit apart.
  - `main_like`: XOR over the main pairs, with a size regime set by a big payout at lag 1, 2 or 4, and episode weather (a ±0.4 logit shift at a shared time).
  - `new_pairs`: XOR over (2,6), (3,8), (1,5) or (5,7), which are absent from the released data.
  - `and_rule`: an AND rule over the main pairs, with a per-machine orientation.
  - `xor3`: parity over three lags, (1,3,6), (2,4,7) or (1,5,8).
  - `changes`: half the machines reverse gradually over 60 ticks at their own time; the rest flip together at a shared episode time. Weather is on.
  - `size_indep`: wins as in main_like, but the payout-size regime follows its own Markov chain (5% switch rate per tick), independent of wins.
- Payout-size distributions per type are the two released-kit regimes.

## Commands
```
python run_entry.py --entry path/to/baseline/entry.zip --name baseline --set dev
python run_entry.py --entry path/to/candidate/entry.zip --name candidate --set dev
python score.py --set dev --entries baseline candidate
```
For the sealed comparison, Claude runs the same commands with `--set sealed` once both ZIPs are frozen, and reports the full table, including regressions.
