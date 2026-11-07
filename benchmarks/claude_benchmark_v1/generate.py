"""House Edge synthetic benchmark generator (Python standard library only, deterministic).

Builds paired, masked copies of the same latent episodes in the kit schema:
  data/<set>/<scenario>/<mask>/test/{queries.csv,history.csv}
Truth (never inside a data root):
  truth/<set>/truth.csv  with query_id, episode_id, scenario, mask, p_0, p_1, p_2, p_5, p_20

Usage:  python generate.py --out .
Every spin is generated from earlier ticks only. The target at the cutoff is the simulator's
probability vector computed before any cutoff outcome would be drawn (none is drawn).
"""
import argparse, csv, hashlib, json, math, os, random

PAY = [0, 1, 2, 5, 20]
TYPES = {  # (off logit, on logit), two size regimes P(1x,2x,5x,20x | win)
    "steady":   ((-1.77, 3.02), [[0.455, 0.436, 0.107, 0.002], [0.754, 0.197, 0.048, 0.001]]),
    "balanced": ((-3.12, 1.74), [[0.214, 0.547, 0.205, 0.034], [0.500, 0.348, 0.130, 0.022]]),
    "jackpot":  ((-4.53, 0.31), [[0.121, 0.324, 0.416, 0.139], [0.335, 0.245, 0.315, 0.105]]),
}
MAIN_PAIRS = [(1, 3), (2, 5), (4, 7)]
SCENARIOS = {
    # name: win rule, lag sets, size rule, change mode, level spread
    "constant":    dict(rule="none", lags=[()], size="constant", change="none", weak=False),
    "weak_dep":    dict(rule="xor", lags=MAIN_PAIRS, size="lag_big", change="none", weak=True),
    "main_like":   dict(rule="xor", lags=MAIN_PAIRS, size="lag_big", change="weather", weak=False),
    "new_pairs":   dict(rule="xor", lags=[(2, 6), (3, 8), (1, 5), (5, 7)], size="lag_big", change="weather", weak=False),
    "and_rule":    dict(rule="and", lags=MAIN_PAIRS, size="lag_big", change="weather", weak=False),
    "xor3":        dict(rule="xor", lags=[(1, 3, 6), (2, 4, 7), (1, 5, 8)], size="lag_big", change="weather", weak=False),
    "changes":     dict(rule="xor", lags=MAIN_PAIRS, size="lag_big", change="drift_and_shared", weak=False),
    "size_indep":  dict(rule="xor", lags=MAIN_PAIRS, size="markov", change="weather", weak=False),
}
MASKS = ["full", "recent40_older24", "window48", "gaps35"]
SETS = {"dev": (8, 1_000), "sealed": (40, 900_000)}  # episodes per scenario, seed base (disjoint ranges)


def sig(x):
    return 1.0 / (1.0 + math.exp(-x))


def rng_for(*parts):
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def rule_on(rule, wins):
    if rule == "xor":
        return sum(wins) % 2 == 1
    if rule == "and":
        return all(wins)
    return False


def latent_episode(scn, cfg, seed):
    rng = rng_for("episode", scn, seed)
    n = rng.randint(4, 10)
    C = rng.randint(192, 256)
    w_time, w_sign = rng.randint(int(C * 0.3), int(C * 0.9)), rng.choice([-1, 1])
    shared_flip = rng.randint(int(C * 0.3), int(C * 0.9))
    machines = []
    for _ in range(n):
        ty = rng.choice(list(TYPES))
        (lo, hi), _ = TYPES[ty]
        if cfg["weak"]:
            mid = (lo + hi) / 2
            lo, hi = mid - 0.3, mid + 0.3
        m = dict(ty=ty, s=rng.choice([-1, 0, 1]), lags=rng.choice(cfg["lags"]), orient=rng.random() < 0.5,
                 lo=lo + rng.gauss(0, 0.3), hi=hi + rng.gauss(0, 0.3), const=rng.random(),
                 size_lag=rng.choice([1, 2, 4]), size_orient=rng.random() < 0.5, size_state=rng.random() < 0.5,
                 drift_t=rng.randint(int(C * 0.2), int(C * 0.8)), drifts=rng.random() < 0.5)
        machines.append(m)
    hist = [dict() for _ in machines]
    targets = []
    for t in range(C + 1):
        for i, m in enumerate(machines):
            h = hist[i]
            # probability that the machine is "on" at tick t, from earlier ticks only
            if cfg["rule"] == "none":
                on_p = m["const"]
            else:
                on = rule_on(cfg["rule"], [h.get(t - l, 0) > 0 for l in m["lags"]])
                base = float(on != m["orient"])
                if cfg["change"] == "drift_and_shared":
                    if m["drifts"]:
                        f = min(1.0, max(0.0, (t - m["drift_t"]) / 60))
                        base = (1 - f) * base + f * (1 - base)
                    elif t >= shared_flip:
                        base = 1 - base
                on_p = base
            shift = 0.38 * m["s"]
            if cfg["change"] in ("weather", "drift_and_shared"):
                shift += 0.4 * w_sign * (1 if t >= w_time else -1)
            pw = on_p * sig(m["hi"] + shift) + (1 - on_p) * sig(m["lo"] + shift)
            if cfg["size"] == "constant":
                reg = m["size_state"]
            elif cfg["size"] == "markov":
                if rng.random() < 0.05:
                    m["size_state"] = not m["size_state"]
                reg = m["size_state"]
            else:
                reg = (h.get(t - m["size_lag"], 0) >= 2) != m["size_orient"]
            sz = TYPES[m["ty"]][1][int(reg)]
            p = [1 - pw] + [pw * x for x in sz]
            if t == C:
                targets.append(p)
            else:
                h[t] = rng.choices(PAY, p)[0]
    return C, machines, hist, targets


def apply_mask(mask, ticks, rng):
    if mask == "full":
        return ticks
    if mask == "recent40_older24":
        return sorted(rng.sample(ticks[:-40], 24)) + ticks[-40:]
    if mask == "window48":
        return ticks[-48:]
    if mask == "gaps35":
        return [t for t in ticks if rng.random() >= 0.35]
    raise ValueError(mask)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    manifest = {"scenarios": SCENARIOS, "masks": MASKS, "sets": {}, "files": {}}
    for set_name, (n_eps, seed_base) in SETS.items():
        truth = []
        per = {}
        for scn, cfg in SCENARIOS.items():
            seeds = [seed_base + 1000 * list(SCENARIOS).index(scn) + e for e in range(n_eps)]
            per[scn] = {"episodes": n_eps, "seeds": [seeds[0], seeds[-1]], "machines": 0}
            data = {mask: ([], []) for mask in MASKS}
            for e, seed in enumerate(seeds):
                C, machines, hist, targets = latent_episode(scn, cfg, seed)
                eid = f"bench-{set_name}-{scn}-e{e:03d}"
                per[scn]["machines"] += len(machines)
                for mask in MASKS:
                    mrng = rng_for("mask", scn, seed, mask)
                    q_rows, h_rows = data[mask]
                    for i, m in enumerate(machines):
                        mid = f"{eid}-m{i:02d}"
                        qid = f"{mid}-next"
                        q_rows.append([qid, eid, mid, m["ty"], m["s"], C])
                        for t in apply_mask(mask, sorted(hist[i]), mrng):
                            h_rows.append([eid, mid, t, hist[i][t]])
                        truth.append([qid, eid, scn, mask] + [repr(x) for x in targets[i]])
            for mask, (q_rows, h_rows) in data.items():
                root = os.path.join(args.out, "data", set_name, scn, mask, "test")
                write_csv(os.path.join(root, "queries.csv"),
                          ["query_id", "episode_id", "machine_id", "machine_type", "signal", "cutoff"], q_rows)
                write_csv(os.path.join(root, "history.csv"), ["episode_id", "machine_id", "tick", "payout"], h_rows)
        write_csv(os.path.join(args.out, "truth", set_name, "truth.csv"),
                  ["query_id", "episode_id", "scenario", "mask", "p_0", "p_1", "p_2", "p_5", "p_20"], truth)
        manifest["sets"][set_name] = per
    for base, _, files in os.walk(args.out):
        for fn in files:
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, args.out).replace(os.sep, "/")
            if rel.startswith(("data/", "truth/")):
                manifest["files"][rel] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print(json.dumps(manifest["sets"], indent=1))


if __name__ == "__main__":
    main()
