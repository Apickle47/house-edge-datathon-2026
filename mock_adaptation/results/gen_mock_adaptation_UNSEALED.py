"""Mock House Edge ADAPTATION round (rehearsal). Standard library only, deterministic.

Writes a participant kit (kit/) mirroring main-participants-60-40.zip and a sealed evaluator folder (sealed/).
Hidden rules (documented in sealed/RULES_SECRET.md, not shipped to participants):
  win: per-machine on/off state = XOR (80%) or AND (20%) of lagged wins over pairs (1,4),(3,6),(2,7); per-machine orientation
  levels: type on/off logits (shifted from main), signal slope 0.38, machine offset N(0,0.3), episode weather +-0.35
  peer: per machine, none (40%) or neighbours' win rate at lag 5 (60%), coefficient 1.0 on logit
  size: two regimes per type (new values); regime = per-machine random table over 'big' (>=2x) payouts at a lag pair from
        (1,3),(2,6),(3,5)
  conditions: stable; short_history (40 recent + 24 older sampled ticks); drift (per-machine gradual reversal over 60 ticks);
        shared_change (episode-wide orientation flip at one tick)
"""
import csv, hashlib, json, math, os, random, sys

PAY = [0, 1, 2, 5, 20]
TYPES = {  # (off logit, on logit), two size regimes P(1,2,5,20 | win) -- changed from main round
    "steady":   ((-1.55, 2.80), [[0.380, 0.480, 0.137, 0.003], [0.690, 0.245, 0.063, 0.002]]),
    "balanced": ((-2.90, 1.95), [[0.180, 0.560, 0.220, 0.040], [0.450, 0.380, 0.145, 0.025]]),
    "jackpot":  ((-4.30, 0.55), [[0.100, 0.300, 0.440, 0.160], [0.300, 0.270, 0.320, 0.110]]),
}
WIN_PAIRS = [(1, 4), (3, 6), (2, 7)]
SIZE_PAIRS = [(1, 3), (2, 6), (3, 5)]
CONDS = ["stable", "short_history", "drift", "shared_change"]
SPLITS = {"train": 24, "validation": 24, "test": 48}  # episodes per condition
MASTER = "house-edge-mock-adaptation-2026-11-07-r1"

def R(*parts):
    h = hashlib.sha256("|".join(map(str, (MASTER,) + parts)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))

def sig(x): return 1 / (1 + math.exp(-x))

def episode(split, cond, e):
    rng = R("episode", split, cond, e)
    C = rng.randint(192, 256)
    w_t, w_s = rng.randint(int(C * .25), int(C * .9)), rng.choice([-1, 1])
    flip_t = rng.randint(int(C * .35), int(C * .85))
    ms = []
    for i in range(8):
        ty = rng.choice(list(TYPES))
        ms.append(dict(ty=ty, s=rng.choice([-1, 0, 1]), pair=rng.choice(WIN_PAIRS), rule="and" if rng.random() < .2 else "xor",
                       orient=rng.random() < .5, off=rng.gauss(0, .3), peer=rng.random() < .6,
                       spair=rng.choice(SIZE_PAIRS), stable_tab={k: rng.random() < .5 for k in [(a, b) for a in (0, 1) for b in (0, 1)]},
                       drift_t=rng.randint(int(C * .2), int(C * .75))))
    hist = [dict() for _ in ms]
    targets = []
    for t in range(C + 1):
        row = []
        for i, m in enumerate(ms):
            h = hist[i]
            w = [h.get(t - l, 0) > 0 for l in m["pair"]]
            on = (w[0] != w[1]) if m["rule"] == "xor" else (w[0] and w[1])
            base = float(on != m["orient"])
            if cond == "drift":
                f = min(1., max(0., (t - m["drift_t"]) / 60))
                base = (1 - f) * base + f * (1 - base)
            elif cond == "shared_change" and t >= flip_t:
                base = 1 - base
            shift = .38 * m["s"] + m["off"] + .35 * w_s * (1 if t >= w_t else -1)
            if m["peer"]:
                nb = [hist[j].get(t - 5) for j in range(8) if j != i]
                nb = [v for v in nb if v is not None]
                if nb: shift += 1.0 * (sum(v > 0 for v in nb) / len(nb) - .5)
            lo, hi = TYPES[m["ty"]][0]
            pw = base * sig(hi + shift) + (1 - base) * sig(lo + shift)
            key = tuple(int(h.get(t - l, 0) >= 2) for l in m["spair"])
            reg = int(m["stable_tab"][key])
            p = [1 - pw] + [pw * x for x in TYPES[m["ty"]][1][reg]]
            row.append(p)
        if t == C:
            targets = row; break
        for i, p in enumerate(row):  # synchronous draw after all probabilities for tick t are fixed
            hist[i][t] = rng.choices(PAY, p)[0]
    label_rng = R("label", split, cond, e)
    labels = [label_rng.choices(PAY, p)[0] for p in targets]
    mask_rng = R("mask", split, cond, e)
    if cond == "short_history":
        ticks = list(range(C))
        keep = set(ticks[-40:]) | set(mask_rng.sample(ticks[:-40], 24))
        hist = [{t: v for t, v in h.items() if t in keep} for h in hist]
    return C, ms, hist, targets, labels

def wcsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(rows)

def main(out):
    kit, sealed = os.path.join(out, "kit"), os.path.join(out, "sealed")
    allq = {}
    for split, n in SPLITS.items():
        Q, H, L, T, Cd = [], [], [], [], []
        k = 0
        for cond in CONDS:
            for e in range(n):
                C, ms, hist, targets, labels = episode(split, cond, e)
                eid = f"adaptation-{split}-e{k:05d}"; k += 1
                for i, m in enumerate(ms):
                    mid = f"{eid}-m{i:03d}"; qid = f"{mid}-next"
                    Q.append([qid, eid, mid, m["ty"], m["s"], C])
                    H += [[eid, mid, t, v] for t, v in sorted(hist[i].items())]
                    L.append([qid, labels[i]]); Cd.append([qid, cond])
                    T.append([qid, eid] + [repr(x) for x in targets[i]] + [labels[i]])
        # shuffle episode order deterministically so condition is not readable from position
        order = sorted({q[1] for q in Q}, key=lambda e: hashlib.sha256((MASTER + "order" + e).encode()).digest())
        rename = {e: f"adaptation-{split}-e{i:05d}" for i, e in enumerate(order)}
        def ren(s):
            for old in (s,):
                eid = old[:len(f"adaptation-{split}-e00000")]
                return rename[eid] + old[len(eid):]
        Q = sorted([[ren(q[0]), rename[q[1]], ren(q[2])] + q[3:] for q in Q])
        H = sorted([[rename[h[0]], ren(h[1])] + h[2:] for h in H], key=lambda r: (r[0], r[1], r[2]))
        L = sorted([[ren(x[0]), x[1]] for x in L]); Cd = sorted([[ren(x[0]), x[1]] for x in Cd])
        T = sorted([[ren(x[0]), rename[x[1]]] + x[2:] for x in T])
        pub = os.path.join(kit, "public", split)
        wcsv(os.path.join(pub, "queries.csv"), ["query_id", "episode_id", "machine_id", "machine_type", "signal", "cutoff"], Q)
        wcsv(os.path.join(pub, "history.csv"), ["episode_id", "machine_id", "tick", "payout"], H)
        wcsv(os.path.join(pub, "sample_submission.csv"), ["query_id", "p_0", "p_1", "p_2", "p_5", "p_20"], [[q[0], .2, .2, .2, .2, .2] for q in Q])
        dest = pub if split != "test" else sealed
        wcsv(os.path.join(dest, "labels.csv" if split != "test" else "test_labels.csv"), ["query_id", "outcome"], L)
        wcsv(os.path.join(dest, "conditions.csv" if split != "test" else "test_conditions.csv"), ["query_id", "condition"], Cd)
        if split != "train":
            wcsv(os.path.join(dest, "targets.csv" if split != "test" else "test_targets.csv"),
                 ["query_id", "episode_id", "p_0", "p_1", "p_2", "p_5", "p_20", "outcome"], T)
        allq[split] = len(Q)
    season = hashlib.sha256((MASTER + "season").encode()).hexdigest()[:24]
    meta = {"conditions": CONDS, "counts_per_condition": SPLITS, "history": "Mock adaptation rehearsal: changed lag relationships, payout regimes and peer delays.",
            "machines_per_episode": 8, "max_points": 40, "mode": "event",
            "reference": "Pooled, strength=20, fitted separately on this round's training observations.", "round": "adaptation",
            "season_id": season, "suite_version": "experimentation-suite-v3", "target": "Next-spin probabilities for 0x, 1x, 2x, 5x, 20x.",
            "test_policy": "Test targets, conditions and reference predictions stay private.", "warning": "MOCK REHEARSAL KIT built by Claude; not organizer data."}
    with open(os.path.join(kit, "public", "metadata.json"), "w") as f: json.dump(meta, f, indent=2)
    print(json.dumps(allq), season)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
