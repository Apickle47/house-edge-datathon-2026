"""House Edge forecaster (standard library only).

Win model: each machine's chance of paying out is driven by whether it paid out at a pair of
earlier ticks, one of (1,3), (2,5) or (4,7). For every pair, a per-cell "on/off" posterior is
tracked with exponential forgetting, and win levels come from type-specific on/off logits plus a
signal shift. Pairs, memory lengths and a machine offset are combined by Bayesian model averaging
using each model's sequential predictive likelihood on the machine's own history.

Size model: given a win, payout sizes follow one of two fixed distributions per machine type.
The regime is estimated from earlier wins in the same pattern cell (tempered likelihood).

All constants (size distributions, on/off levels, signal slope) are estimated from the public
validation targets of the current round at run time, so the same code adapts to a new round.
"""
import csv, math, collections

PAY = [0, 1, 2, 5, 20]
PAIRS = [(1, 3), (2, 5), (4, 7)]
CONFIG = dict(gammas=(1.0, 0.97, 0.94, 0.9), deltas=(-0.6, 0.0, 0.6), half=15.0, prior_sd=0.4, floor=1e-5)


def sig(x):
    return 1.0 / (1.0 + math.exp(-x))


def read_split(root, split):
    d = f"{root}/{split}/"
    queries = list(csv.DictReader(open(d + "queries.csv", newline="", encoding="utf-8")))
    hist = collections.defaultdict(dict)
    for r in csv.DictReader(open(d + "history.csv", newline="", encoding="utf-8")):
        hist[(r["episode_id"], r["machine_id"])][int(r["tick"])] = int(r["payout"])
    return queries, hist


def _two_means(values, iters=50):
    lo, hi = min(values), max(values)
    for _ in range(iters):
        a = [v for v in values if abs(v - lo) <= abs(v - hi)]
        b = [v for v in values if abs(v - lo) > abs(v - hi)]
        if not a or not b:
            break
        lo, hi = sum(a) / len(a), sum(b) / len(b)
    return lo, hi


def fit_constants(root):
    """Estimate size regimes, on/off win levels and the signal slope from validation targets."""
    q = {r["query_id"]: r for r in csv.DictReader(open(f"{root}/validation/queries.csv", newline="", encoding="utf-8"))}
    rows = []
    for r in csv.DictReader(open(f"{root}/validation/targets.csv", newline="", encoding="utf-8")):
        p = [float(r[k]) for k in ("p_0", "p_1", "p_2", "p_5", "p_20")]
        qq = q[r["query_id"]]
        rows.append((qq["machine_type"], int(qq["signal"]), p))
    size, lev = {}, {}
    types = sorted({t for t, _, _ in rows})
    # size regimes: the two most common size vectors (rounded) per type
    for t in types:
        groups = collections.defaultdict(list)
        for tt, _, p in rows:
            if tt != t:
                continue
            pw = 1 - p[0]
            s = [x / pw for x in p[1:]]
            groups[round(s[0], 4)].append(s)
        top = sorted(groups.values(), key=len, reverse=True)[:2]
        if len(top) < 2:
            top = top * 2
        size[t] = [[sum(col) / len(col) for col in zip(*g)] for g in sorted(top, key=lambda g: g[0][0])]
    # win levels: split logits into off/on clusters per type, then a pooled signal slope
    num = den = 0.0
    clusters = {}
    for t in types:
        lg = [(math.log((1 - p[0]) / p[0]), s) for tt, s, p in rows if tt == t]
        lo, hi = _two_means([v for v, _ in lg])
        cl = [[(v, s) for v, s in lg if abs(v - lo) <= abs(v - hi)], [(v, s) for v, s in lg if abs(v - lo) > abs(v - hi)]]
        clusters[t] = cl
        for c in cl:
            ms = sum(s for _, s in c) / len(c); mv = sum(v for v, _ in c) / len(c)
            num += sum((s - ms) * (v - mv) for v, s in c); den += sum((s - ms) ** 2 for _, s in c)
    beta = num / den if den else 0.0
    for t in types:
        lev[t] = tuple(sum(v - beta * s for v, s in c) / len(c) for c in clusters[t])
    return size, lev, beta


SIZE_PAIRS = [(1, 2), (1, 4), (2, 4)]


def _tied_runs(seq, ticks, cutoff, ctx, gammas, pon, poff):
    """XOR/XNOR hypothesis for one lag pair: one log-likelihood ratio whose sign flips with parity.

    Returns (log evidence, prediction at cutoff, per-tick predictive trace) for each memory length."""
    lpon, l1pon, lpoff, l1poff = math.log(pon), math.log(1 - pon), math.log(poff), math.log(1 - poff)
    up, down = lpon - lpoff, l1pon - l1poff
    res = []
    for g in gammas:
        llr, last, L, trace = 0.0, None, 0.0, {}
        for t in ticks:
            if any((t - l) not in seq for l in ctx):
                continue
            sgn = 1 if sum(seq[t - l] > 0 for l in ctx) % 2 == 1 else -1
            if last is not None and g < 1:
                llr *= g ** (t - last)
            last = t
            a = sig(sgn * llr)
            p = a * pon + (1 - a) * poff
            y = seq[t] > 0
            L += math.log(p if y else 1 - p)
            trace[t] = p
            llr += sgn * (up if y else down)
        if any((cutoff - l) not in seq for l in ctx):
            continue
        sgn = 1 if sum(seq[cutoff - l] > 0 for l in ctx) % 2 == 1 else -1
        d = g ** (cutoff - last) if (last is not None and g < 1) else 1.0
        a = sig(sgn * llr * d)
        res.append((L, a * pon + (1 - a) * poff, trace))
    return res


def win_model(seq, cutoff, mtype, signal, lev, beta, cfg):
    ticks = sorted(seq)
    lo, hi = lev[mtype]
    runs = []
    for dl in cfg["deltas"]:
        pon, poff = sig(hi + beta * signal + dl), sig(lo + beta * signal + dl)
        for ctx in cfg.get("pairs", PAIRS):
            runs += _tied_runs(seq, ticks, cutoff, ctx, cfg["gammas"], pon, poff)
    if not runs:
        return sig((lo + hi) / 2 + beta * signal), {}
    m = max(r[0] for r in runs)
    ws = [math.exp(r[0] - m) for r in runs]
    s = sum(ws)
    ws = [w / s for w in ws]
    pw = sum(w * r[1] for w, r in zip(ws, runs))
    trace, tw = collections.defaultdict(float), collections.defaultdict(float)
    for w, r in zip(ws, runs):
        for t, p in r[2].items():
            trace[t] += w * p
            tw[t] += w
    return pw, {t: trace[t] / tw[t] for t in trace}


def episode_offset(items, cutoff, half, prior_sd, burn=30):
    """Shared, recency-weighted logit shift for all machines in an episode (Newton steps, Gaussian prior)."""
    d = 0.0
    for _ in range(20):
        g, h = -d / prior_sd ** 2, -1 / prior_sd ** 2
        for seq, trace in items:
            for t, p in trace.items():
                if t < burn:
                    continue
                w = 0.5 ** ((cutoff - 1 - t) / half)
                q = sig(math.log(p / (1 - p)) + d)
                g += w * ((seq[t] > 0) - q)
                h -= w * q * (1 - q)
        step = g / h
        d -= step
        if abs(step) < 1e-6:
            break
    return d


def size_model(seq, cutoff, dists, pairs=SIZE_PAIRS):
    """Two payout-size regimes; regime depends on which of two lagged payouts were big (>=2x)."""
    ticks = sorted(seq)
    l0 = [math.log(x) for x in dists[0]]
    l1 = [math.log(x) for x in dists[1]]
    runs = []
    for ctx in pairs:
        cell, L = {}, 0.0
        for t in ticks:
            v = seq[t]
            if v <= 0 or any((t - l) not in seq for l in ctx):
                continue
            key = tuple(seq[t - l] >= 2 for l in ctx)
            i = PAY.index(v) - 1
            a = sig(cell.get(key, 0.0))
            L += math.log(a * dists[0][i] + (1 - a) * dists[1][i])
            cell[key] = cell.get(key, 0.0) + l0[i] - l1[i]
        if any((cutoff - l) not in seq for l in ctx):
            continue
        a = sig(cell.get(tuple(seq[cutoff - l] >= 2 for l in ctx), 0.0))
        runs.append((L, [a * x + (1 - a) * y for x, y in zip(dists[0], dists[1])]))
    if not runs:
        return [0.5 * x + 0.5 * y for x, y in zip(dists[0], dists[1])]
    m = max(r[0] for r in runs)
    ws = [math.exp(r[0] - m) for r in runs]
    s = sum(ws)
    return [sum(w * r[1][i] for w, r in zip(ws, runs)) / s for i in range(4)]


def forecast(queries, hist, size, lev, beta, cfg=CONFIG):
    by_episode = collections.defaultdict(list)
    for q in queries:
        by_episode[q["episode_id"]].append(q)
    out = {}
    for ep in sorted(by_episode):
        qs = by_episode[ep]
        state = {}
        for q in qs:
            cut = int(q["cutoff"])
            seq = {t: v for t, v in hist[(q["episode_id"], q["machine_id"])].items() if t < cut}  # strictly earlier
            pw, trace = win_model(seq, cut, q["machine_type"], int(q["signal"]), lev, beta, cfg)
            state[q["query_id"]] = (seq, cut, pw, trace)
        cutoffs = {v[1] for v in state.values()}
        shift = {}
        for c in cutoffs:
            items = [(v[0], {t: p for t, p in v[3].items() if t < c}) for v in state.values()]
            shift[c] = episode_offset(items, c, cfg["half"], cfg["prior_sd"])
        for q in qs:
            seq, cut, pw, _ = state[q["query_id"]]
            pw = min(max(pw, 1e-9), 1 - 1e-9)
            pw = sig(math.log(pw / (1 - pw)) + shift[cut])
            sz = size_model(seq, cut, size[q["machine_type"]], cfg.get("size_pairs", SIZE_PAIRS))
            p = [1 - pw] + [pw * x for x in sz]
            p = [max(x, cfg["floor"]) for x in p]
            t = math.fsum(p)
            out[q["query_id"]] = [x / t for x in p]
    return out


# ---------------------------------------------------------------------------
# Pattern discovery: which lag pairs drive wins and payout sizes in this round's data.
# ---------------------------------------------------------------------------
ALL_PAIRS = [(a, b) for a in range(1, 9) for b in range(a + 1, 9)]


def discover_win_pairs(root, lev, beta, min_share=0.05, splits=("train", "validation")):
    """Average posterior over XOR lag pairs across all public train/validation machines."""
    share = collections.defaultdict(float)
    n = 0
    for sp in splits:
        queries, hist = read_split(root, sp)
        for q in queries:
            seq = hist[(q["episode_id"], q["machine_id"])]
            ticks = sorted(seq)
            cut = ticks[-1] + 1
            lo, hi = lev[q["machine_type"]]
            s = int(q["signal"])
            pon, poff = sig(hi + beta * s), sig(lo + beta * s)
            ev = []
            for ctx in ALL_PAIRS:
                r = _tied_runs(seq, ticks, cut, ctx, (0.97,), pon, poff)
                ev.append(r[0][0] if r else -1e18)
            m = max(ev)
            w = [math.exp(e - m) for e in ev]
            z = sum(w)
            for c, x in zip(ALL_PAIRS, w):
                share[c] += x / z
            n += 1
    chosen = sorted((c for c in ALL_PAIRS if share[c] / n >= min_share), key=lambda c: -share[c])
    return chosen or [max(ALL_PAIRS, key=lambda c: share[c])]


def discover_size_pairs(root, size, top=3):
    """Rank lag pairs by how well big-payout (>=2x) cells predict the size regime in validation targets."""
    queries, hist = read_split(root, "validation")
    targets = {r["query_id"]: r for r in csv.DictReader(open(f"{root}/validation/targets.csv", newline="", encoding="utf-8"))}
    data = []
    for q in queries:
        d = size[q["machine_type"]]
        t = targets[q["query_id"]]
        pw = 1 - float(t["p_0"])
        th = float(t["p_1"]) / pw
        cut = int(q["cutoff"])
        seq = {k: v for k, v in hist[(q["episode_id"], q["machine_id"])].items() if k < cut}
        data.append((seq, cut, d, 1.0 if abs(th - d[0][0]) < abs(th - d[1][0]) else 0.0))
    scored = []
    for ctx in ALL_PAIRS:
        se = 0.0
        for seq, cut, d, st0 in data:
            if any(cut - l not in seq for l in ctx):
                se += 0.25
                continue
            key = tuple(seq[cut - l] >= 2 for l in ctx)
            ll = 0.0
            for t, v in seq.items():
                if v > 0 and all(t - l in seq for l in ctx) and tuple(seq[t - l] >= 2 for l in ctx) == key:
                    i = PAY.index(v) - 1
                    ll += math.log(d[0][i]) - math.log(d[1][i])
            se += (sig(0.5 * ll) - st0) ** 2
        scored.append((se / len(data), ctx))
    scored.sort()
    return [c for _, c in scored[:top]]


def write_csv(path, preds):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "p_0", "p_1", "p_2", "p_5", "p_20"])
        for qid in sorted(preds):
            w.writerow([qid] + [repr(x) for x in preds[qid]])
