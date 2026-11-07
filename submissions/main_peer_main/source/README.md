# House Edge forecast

Round: main · Season: 5fffdc4d0c700bbf61c3f911

Submit submission.csv and entry.zip as separate files. Forecast SHA-256: 67fa8d869e2a538973fa96d7214085b25089d7ae651548976c8a58b82378e16f

## Reproduce

    python predict.py --data /data --out /output/submission.csv

The predictor uses the Python standard library, model.json, and the supplied test queries and histories. It runs offline on CPU and accepts new query, machine, and episode IDs. The public-kit inference took 22.8 seconds locally on Windows with Python 3.14.6. All machine and neighbor information is restricted to ticks before the query cutoff. Grouped data is streamed one episode at a time. Interleaved data is read in bounded batches.

## Fit and evaluate

Fitting locally uses NumPy 2.4.6. Prediction has no third-party dependencies. The fit is deterministic. Parameters are learned from official training histories and released validation probabilities. The fitted checkpoint contains global parameters only. It contains no query lookup tables or forecasts.

    python fit.py --data /path/to/kit/public --out model.json
    python build_round.py --kit /path/to/extracted-kit --round main --out /path/to/fresh-run

For the adaptation kit, set --round adaptation and use its extracted folder and a fresh output directory. The build learns lag pairs and payout rules again, runs two-fold validation with whole episodes, refits using all calibration episodes, checks the CSV, packages the code and verifies the archive's predictions in a fresh directory. The holdout assignments are deterministic and stratified by validation condition. Conditions are used only for evaluation splitting. Development choices used a subset of public validation.

## Model

Training scans all pairs of lags from 1 through 8 for recurring win patterns. It learns which payout-size patterns accompany each win pattern. At inference, the model weighs hypotheses about the lag pair, orientation, payout-size regime and timing of a shared change using observed histories. It estimates a shared change in win odds from neighboring machines using a two-state filter. Missing lag values are marginalized approximately. Forecasts average the five payout probabilities across hypotheses.

For unfamiliar machines, the predictor also evaluates historical evidence for constant odds, changes in payout frequency, single-lag dependencies, and flexible win transitions at any pair of lags through eight. It weights the trained and alternative predictions separately for win frequency and positive payout size. This adjustment uses the supplied pre-cutoff logs and works with the frozen checkpoint.

For sparse observations, the checkpoint includes conditional probabilities for supported lag rules, computed from the fitted transition model's stationary distribution. The predictor uses the observed lag values to average over missing win and size states. It also considers three-lag parity and general binary tables across lags 1–8. Candidate discovery during local training uses at most 1,024 training machines, six retained lag pairs, and four size rules per pair. These are discovery budgets, not limits on the number of test machines.

Calibration selects a lag for peer win frequency using only the current fit's calibration episodes and a minimum improvement criterion. The likelihood of each observation uses only earlier peer spins. The training histories also estimate how often and when machine relationships reverse and how persistent the shared win-rate shift is. A separate stationary alternative shrinks sparse win and size frequencies toward other machines of the same observed type in the same episode when the data support it.
