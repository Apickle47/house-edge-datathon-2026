"""Score benchmark forecasts against hidden truth; optional paired comparison.

Usage:
  python score.py --set dev --entries baseline                 # one entry
  python score.py --set sealed --entries baseline candidate    # paired: candidate minus baseline
Metric: summed squared error over the five probabilities per query, averaged within each episode,
then over episodes for each scenario x mask. Lower is better. Paired episode differences are
bootstrapped (2,000 resamples, fixed seed) for 95% intervals. A built-in reference forecaster
("pooled_ref": machine frequencies shrunk toward the machine-type pool, standard library) is
scored too, for scale.
"""
import argparse, csv, json, os, random, collections, math

P = ["p_0", "p_1", "p_2", "p_5", "p_20"]
PAY = [0, 1, 2, 5, 20]

def read_truth(bench, set_name):
    T = {}
    for r in csv.DictReader(open(os.path.join(bench, "truth", set_name, "truth.csv"), newline="")):
        T[(r["scenario"], r["mask"], r["query_id"])] = (r["episode_id"], [float(r[k]) for k in P])
    return T

def read_forecast(path):
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        p = [float(r[k]) for k in P]
        out[r["query_id"]] = p
    return out

def pooled_ref(root, strength=20.0):
    q = list(csv.DictReader(open(os.path.join(root, "test", "queries.csv"), newline="")))
    counts = collections.defaultdict(lambda: [0.0] * 5)
    by_type = collections.defaultdict(lambda: [0.5] * 5)
    mtype = {r["machine_id"]: r["machine_type"] for r in q}
    for r in csv.DictReader(open(os.path.join(root, "test", "history.csv"), newline="")):
        i = PAY.index(int(r["payout"]))
        counts[r["machine_id"]][i] += 1
        by_type[mtype[r["machine_id"]]][i] += 1
    out = {}
    for r in q:
        prior = by_type[r["machine_type"]]
        z = sum(prior)
        c = [x + strength * y / z for x, y in zip(counts[r["machine_id"]], prior)]
        s = sum(c)
        out[r["query_id"]] = [x / s for x in c]
    return out

def episode_errors(T, forecasts, scn, mask):
    ep = collections.defaultdict(list)
    missing = 0
    for (s, m, qid), (eid, truth) in T.items():
        if s != scn or m != mask:
            continue
        p = forecasts.get(qid)
        if p is None:
            missing += 1
            p = [0.2] * 5
        ep[eid].append(sum((a - b) ** 2 for a, b in zip(p, truth)))
    return {e: sum(v) / len(v) for e, v in ep.items()}, missing

def boot(diffs, reps=2000, seed=7):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev")
    ap.add_argument("--entries", nargs="+", required=True)
    ap.add_argument("--bench", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()
    T = read_truth(a.bench, a.set)
    combos = sorted({(s, m) for s, m, _ in T})
    table = {}
    for scn, mask in combos:
        root = os.path.join(a.bench, "data", a.set, scn, mask)
        row = {"pooled_ref": episode_errors(T, pooled_ref(root), scn, mask)[0]}
        for name in a.entries:
            path = os.path.join(a.bench, "results", a.set, name, scn, f"{mask}.csv")
            fc = read_forecast(path) if os.path.exists(path) else {}
            errs, missing = episode_errors(T, fc, scn, mask)
            row[name] = errs
            if missing:
                print(f"WARNING {name} {scn}/{mask}: {missing} missing forecasts scored as uniform")
        table[(scn, mask)] = row
    names = ["pooled_ref"] + a.entries
    print(f"\nMean per-episode summed squared error ({a.set}); lower is better\n")
    print("| scenario | mask | " + " | ".join(names) + (" | diff (cand-base) [95% CI] |" if len(a.entries) == 2 else " |"))
    print("|---" * (2 + len(names) + (1 if len(a.entries) == 2 else 0)) + "|")
    summary = {}
    all_diffs = []
    for (scn, mask), row in table.items():
        means = {n: sum(row[n].values()) / len(row[n]) for n in names}
        line = f"| {scn} | {mask} | " + " | ".join(f"{means[n]:.5f}" for n in names)
        if len(a.entries) == 2:
            b, c = a.entries
            diffs = [row[c][e] - row[b][e] for e in sorted(row[b])]
            all_diffs += diffs
            lo, hi = boot(diffs)
            d = sum(diffs) / len(diffs)
            flag = "WIN" if hi < 0 else "REGRESSION" if lo > 0 else "tie"
            line += f" | {d:+.5f} [{lo:+.5f}, {hi:+.5f}] {flag}"
            summary[f"{scn}/{mask}"] = {"means": means, "diff": d, "ci": [lo, hi], "flag": flag}
        else:
            summary[f"{scn}/{mask}"] = {"means": means}
        print(line + " |")
    overall = {n: sum(sum(r[n].values()) / len(r[n]) for r in table.values()) / len(table) for n in names}
    print("\nOverall (equal weight per scenario x mask): " + ", ".join(f"{n}={v:.5f}" for n, v in overall.items()))
    if len(a.entries) == 2:
        lo, hi = boot(all_diffs)
        print(f"Overall paired diff ({a.entries[1]} - {a.entries[0]}): {sum(all_diffs)/len(all_diffs):+.5f} [{lo:+.5f}, {hi:+.5f}]")
    out = os.path.join(a.bench, "results", a.set, "score_" + "_vs_".join(a.entries) + ".json")
    json.dump({"overall": overall, "cells": summary}, open(out, "w"), indent=1)

if __name__ == "__main__":
    main()
