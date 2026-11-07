"""Train, score, package, and reproduce a House Edge entry for a released kit."""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from fit import fit
from predict import COLUMNS, episode_reader, forecast, load_rows


def folds(public):
    groups = {
        r["query_id"]: r["condition"]
        for r in load_rows(public / "validation/conditions.csv")
    }
    strata = defaultdict(set)
    for q in load_rows(public / "validation/queries.csv"):
        strata[groups[q["query_id"]]].add(q["episode_id"])
    result = [set(), set()]
    for episodes in strata.values():
        ordered = sorted(
            episodes,
            key=lambda e: hashlib.sha256(
                ("house-edge-holdout-v1:" + e).encode()
            ).digest(),
        )
        if len(ordered) < 2:
            raise ValueError(
                "Each validation condition needs at least two episodes for this evaluation."
            )
        cut = (len(ordered) + 1) // 2
        result[0].update(ordered[:cut])
        result[1].update(ordered[cut:])
    return result


def command(*args, cwd=None):
    result = subprocess.run(
        [sys.executable, "-B", *map(str, args)],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    print(result.stdout, flush=True)
    return result.stdout


def build(kit, out, required_round=None, team=None):
    public = kit / "public"
    meta = json.loads((public / "metadata.json").read_text())
    if required_round and required_round != meta["round"]:
        raise ValueError(
            f"Expected {required_round}; kit metadata says {meta['round']}."
        )
    out.mkdir(parents=True, exist_ok=False)
    source = out / "source"
    source.mkdir()
    for name in (
        "predict.py",
        "fit.py",
        "build_round.py",
        "general.py",
        "stationary_fit.py",
    ):
        shutil.copyfile(Path(__file__).with_name(name), source / name)
    halves = folds(public)
    trained = [fit(public, group) for group in halves]
    validation = out / "validation_predictions.csv"
    with validation.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query_id", *COLUMNS])
        for queries, hist in episode_reader(public / "validation"):
            excluded = 1 if queries[0]["episode_id"] in halves[0] else 0
            w.writerows(forecast(queries, hist, trained[excluded]))
    checker = kit / "check_submission.py"
    score = command(checker, validation, "--data", public, "--split", "validation")
    (source / "model.json").write_text(
        json.dumps(fit(public), indent=2), encoding="utf-8"
    )
    submission = out / "submission.csv"
    start = time.monotonic()
    command(source / "predict.py", "--data", public, "--out", submission)
    elapsed = time.monotonic() - start
    check = command(checker, submission, "--data", public)
    digest = hashlib.sha256(submission.read_bytes()).hexdigest()
    repro = [
        "python",
        "predict.py",
        "--data",
        "/data",
        "--out",
        "/output/submission.csv",
    ]
    (source / "reproduce.json").write_text(
        json.dumps({"image": "python", "command": repro}, indent=2), encoding="utf-8"
    )
    import numpy as np

    team_line = f"Team ID: {team}\n\n" if team else ""
    (source / "README.md").write_text(
        f"""# House Edge forecast

{team_line}Round: {meta["round"]} · Season: {meta["season_id"]}

Submit submission.csv and entry.zip as separate files. Forecast SHA-256: {digest}

## Reproduce

    python predict.py --data /data --out /output/submission.csv

The predictor uses the Python standard library, model.json, and the supplied test queries and histories. It runs offline on CPU and accepts new query, machine, and episode IDs. The public-kit inference took {elapsed:.1f} seconds locally on {platform.system()} with Python {platform.python_version()}. All machine and neighbor information is restricted to ticks before the query cutoff. Grouped data is streamed one episode at a time. Interleaved data is read in bounded batches.

## Fit and evaluate

Fitting locally uses NumPy {np.__version__}. Prediction has no third-party dependencies. The fit is deterministic. Parameters are learned from official training histories and released validation probabilities. The fitted checkpoint contains global parameters only. It contains no query lookup tables or forecasts.

    python fit.py --data /path/to/kit/public --out model.json
    python build_round.py --kit /path/to/extracted-kit --round {meta["round"]} --out /path/to/fresh-run

For the adaptation kit, set --round adaptation and use its extracted folder and a fresh output directory. The build learns lag pairs and payout rules again, runs two-fold validation with whole episodes, refits using all calibration episodes, checks the CSV, packages the code and verifies the archive's predictions in a fresh directory. The holdout assignments are deterministic and stratified by validation condition. Conditions are used only for evaluation splitting. Development choices used a subset of public validation.

## Model

Training scans all pairs of lags from 1 through 8 for recurring win patterns. It learns which payout-size patterns accompany each win pattern. At inference, the model weighs hypotheses about the lag pair, orientation, payout-size regime and timing of a shared change using observed histories. It estimates a shared change in win odds from neighboring machines using a two-state filter. Missing lag values are marginalized approximately. Forecasts average the five payout probabilities across hypotheses.

For unfamiliar machines, the predictor also evaluates historical evidence for constant odds, changes in payout frequency, single-lag dependencies, and flexible win transitions at any pair of lags through eight. It weights the trained and alternative predictions separately for win frequency and positive payout size. This adjustment uses the supplied pre-cutoff logs and works with the frozen checkpoint.

For sparse observations, the checkpoint includes conditional probabilities for supported lag rules, computed from the fitted transition model's stationary distribution. The predictor uses the observed lag values to average over missing win and size states. It also considers three-lag parity and general binary tables across lags 1–8. Candidate discovery during local training uses at most 1,024 training machines, six retained lag pairs, and four size rules per pair. These are discovery budgets, not limits on the number of test machines.

Calibration selects a lag for peer win frequency using only the current fit's calibration episodes and a minimum improvement criterion. The likelihood of each observation uses only earlier peer spins. The training histories also estimate how often and when machine relationships reverse and how persistent the shared win-rate shift is. A separate stationary alternative shrinks sparse win and size frequencies toward other machines of the same observed type in the same episode when the data support it.
""",
        encoding="utf-8",
    )
    archive = out / "entry.zip"
    command(kit / "build_entry.py", "--source", source, "--out", archive)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        repro_root = Path(tmp)
        with zipfile.ZipFile(archive) as z:
            z.extractall(repro_root)
        regenerated = repro_root / "recreated.csv"
        command("predict.py", "--data", public, "--out", regenerated, cwd=repro_root)
        if regenerated.read_bytes() != submission.read_bytes():
            raise ValueError("Recreated submission differs from the packaged forecast.")
    (out / "checks.txt").write_text(
        score + "\n" + check + "\nFresh archive reproduction: byte-identical.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--kit", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--round", choices=("main", "adaptation"))
    p.add_argument("--team-id")
    args = p.parse_args()
    build(args.kit.resolve(), args.out.resolve(), args.round, args.team_id)
