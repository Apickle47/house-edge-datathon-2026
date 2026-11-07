"""Fit an offline checkpoint on released train histories and calibration episodes."""

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
import math
import hashlib
from heapq import nsmallest
from pathlib import Path
import numpy as np
from stationary_fit import compile_tables
from predict import COLUMNS, PAYOUTS, Machine, episode_reader, load_rows, win_features
from predict import machines_at_cutoff, peer_totals, peer_feature


def constants(data, selected):
    q = {r["query_id"]: r for r in load_rows(data / "validation/queries.csv")}
    samples = defaultdict(list)
    for r in load_rows(data / "validation/targets.csv"):
        row = q[r["query_id"]]
        if selected is None or row["episode_id"] in selected:
            p = np.array([float(r[c]) for c in COLUMNS])
            for typ in [row["machine_type"], "*"]:
                samples[typ].append((int(row["signal"]), p))
    levels, sizes, assignments = {}, {}, {}
    for typ, rows in samples.items():
        p = np.array([r[1] for r in rows]).clip(1e-10, 1)
        logits = np.log(p[:, 1:].sum(1) / p[:, 0])
        centers = np.quantile(logits, [0.15, 0.85])
        for _ in range(20):
            high = logits > np.mean(centers)
            if high.all() or not high.any():
                centers = np.array([np.mean(logits) - 0.05, np.mean(logits) + 0.05])
                break
            centers = np.array([logits[~high].mean(), logits[high].mean()])
        assignments[typ] = (np.array([r[0] for r in rows]), high, logits)
        conditional = p[:, 1:] / p[:, 1:].sum(1)[:, None]
        if typ == "*":
            sizes[typ] = [conditional.mean(0).tolist()] * 2
        else:
            split = conditional[:, 0] > 0.5 * (
                conditional[:, 0].min() + conditional[:, 0].max()
            )
            sizes[typ] = [
                (conditional[m].mean(0) if m.any() else conditional.mean(0)).tolist()
                for m in [~split, split]
            ]
    num, den = 0.0, 0.0
    for typ, (s, h, y) in assignments.items():
        if typ == "*":
            continue
        for mask in [~h, h]:
            if mask.any():
                x = s[mask] - s[mask].mean()
                num += x @ (y[mask] - y[mask].mean())
                den += x @ x
    slope = float(num / max(den, 1))
    size_effect = {}
    for typ, (s, h, y) in assignments.items():
        z = y - s * slope
        sz = first_size_state(samples[typ], sizes[typ])
        design = np.column_stack([~h, h, sz - 0.5])
        coef = np.linalg.lstsq(design, z, rcond=None)[0]
        size_effect[typ] = float(coef[2])
        levels[typ] = [float(v) for v in coef[:2]]
    # Remove shared episode variation when estimating type and signal effects.
    types = sorted(t for t in levels if t != "*")
    fixed = len(types) * 3 + 1
    episode_data = defaultdict(list)
    for r in load_rows(data / "validation/targets.csv"):
        row = q[r["query_id"]]
        if selected is not None and row["episode_id"] not in selected:
            continue
        typ = row["machine_type"]
        win = max(1e-10, 1 - float(r["p_0"]))
        y = math.log(win / max(1e-10, float(r["p_0"])))
        sz = (
            float(float(r["p_1"]) / win > (sizes[typ][0][0] + sizes[typ][1][0]) / 2)
            - 0.5
        )
        signal = int(row["signal"])
        active = int(y > sum(levels[typ]) / 2 + slope * signal + sz * size_effect[typ])
        x = np.zeros(fixed)
        i = types.index(typ) * 3
        x[i + active] = 1
        x[i + 2] = sz
        x[-1] = signal
        episode_data[row["episode_id"]].append((x, y))
    lhs = np.eye(fixed) * 0.0001
    rhs = np.zeros(fixed)
    for obs in episode_data.values():
        x, y = np.array([a for a, b in obs]), np.array([b for a, b in obs])
        lhs += x.T @ x - np.outer(x.sum(0), x.sum(0)) / (len(x) + 0.45)
        rhs += x.T @ y - x.sum(0) * y.sum() / (len(x) + 0.45)
    effects = np.linalg.solve(lhs, rhs)
    for i, typ in enumerate(types):
        levels[typ] = effects[3 * i : 3 * i + 2].tolist()
        size_effect[typ] = float(effects[3 * i + 2])
    slope = float(effects[-1])
    offsets = [
        np.mean([y - x @ effects for x, y in obs]) for obs in episode_data.values()
    ]
    weather_scale = float(np.std(offsets).clip(0.1, 1.5))
    return {
        "slope": slope,
        "levels": levels,
        "sizes": sizes,
        "size_effect": size_effect,
        "weather_scale": weather_scale,
    }


def fit_peer(data, model, selected):
    targets = {r["query_id"]: r for r in load_rows(data / "validation/targets.csv")}
    types = sorted(t for t in model["levels"] if t != "*")
    width = len(types) * 3 + 1
    design = []
    lag_features = []
    y = []
    episode_ids = []
    initial = []
    for qs, h in episode_reader(data / "validation"):
        ep = qs[0]["episode_id"]
        if selected is not None and ep not in selected:
            continue
        for cut in sorted({int(q["cutoff"]) for q in qs}):
            current = [q for q in qs if int(q["cutoff"]) == cut]
            totals = peer_totals(current, h, cut)
            for q in current:
                r = targets[q["query_id"]]
                typ = q["machine_type"]
                signal = int(q["signal"])
                win = max(1e-10, 1 - float(r["p_0"]))
                logit = math.log(win / max(1e-10, float(r["p_0"])))
                sz = (
                    float(
                        float(r["p_1"]) / win
                        > sum(v[0] for v in model["sizes"][typ]) / 2
                    )
                    - 0.5
                )
                offset = signal * model["slope"] + sz * model["size_effect"][typ]
                k = int(logit > sum(model["levels"][typ]) / 2 + offset)
                x = np.zeros(width)
                i = types.index(typ) * 3
                x[i + k] = 1.0
                x[i + 2] = sz
                x[-1] = signal
                design.append(x)
                y.append(logit)
                initial.append(logit - model["levels"][typ][k] - offset)
                lag_features.append(
                    [
                        peer_feature(totals, h[q["machine_id"]], cut - d)
                        for d in range(1, 9)
                    ]
                )
                episode_ids.append((ep, cut))
    order = {key: i for i, key in enumerate(dict.fromkeys(episode_ids))}
    groups = np.array([order[key] for key in episode_ids])
    n = np.bincount(groups)
    episode_means = np.bincount(groups, weights=initial) / n
    # Resolve the publicly observed high/low episode offset before fitting the
    # peer effect. Omit this correction on rounds without separated states.
    lo, hi = np.quantile(episode_means, [0.2, 0.8])
    for _ in range(12):
        hot = episode_means > (lo + hi) / 2
        if hot.all() or not hot.any():
            return
        lo, hi = episode_means[~hot].mean(), episode_means[hot].mean()
    if np.var(episode_means - np.where(hot, hi, lo)) > 0.4 * np.var(episode_means):
        return
    X = np.column_stack([design, 2 * hot[groups] - 1])
    L = np.array(lag_features)
    Y = np.array(y)
    best = (float("inf"), None)
    # Select one lag using out-of-episode errors within the calibration fold.
    for j in [-1, *range(8)]:
        x = X if j < 0 else np.column_stack([X, L[:, j]])
        penalty = np.eye(x.shape[1]) * 0.002
        if j >= 0:
            penalty[-1, -1] = 1.0
        loss = 0.0
        for parity in (0, 1):
            held = groups % 2 == parity
            train = x[~held]
            coef = np.linalg.solve(train.T @ train + penalty, train.T @ Y[~held])
            loss += np.sum((x[held] @ coef - Y[held]) ** 2)
        # Require an improvement beyond a negligible change in mean logit error.
        if j >= 0:
            loss += len(Y) * 0.001
        if loss < best[0]:
            best = (loss, j)
    j = best[1]
    x = X if j < 0 else np.column_stack([X, L[:, j]])
    penalty = np.eye(x.shape[1]) * 0.002
    if j >= 0:
        penalty[-1, -1] = 1.0
    coef = np.linalg.solve(x.T @ x + penalty, x.T @ Y)
    for i, typ in enumerate(types):
        model["levels"][typ] = coef[i * 3 : i * 3 + 2].tolist()
        model["size_effect"][typ] = float(coef[i * 3 + 2])
    model["slope"] = float(coef[width - 1])
    model["weather_scale"] = float(np.clip(coef[width], 0.1, 1.5))
    model["peer_lag"] = [j + 1, float(coef[-1])] if j >= 0 else [1, 0.0]


def first_size_state(rows, table):
    threshold = (table[0][0] + table[1][0]) / 2
    return np.array([float(p[1] / max(1e-10, sum(p[1:])) > threshold) for _, p in rows])


def discover(data, model):
    pairs = list(combinations(range(1, 9), 2))
    votes = Counter()
    # Include single lags, pairwise parity, and threshold conjunctions/disjunctions.
    rules = [(a, a, k, k, 1) for a in range(1, 9) for k in (1, 2, 5)]
    rules += [
        (a, b, ka, kb, op)
        for a, b in pairs
        for ka in (1, 2, 5)
        for kb in (1, 2, 5)
        for op in (0, 1, 2)
    ]
    a, b, ka, kb, ops = np.array(rules).T
    size_evidence = []
    winning_pairs = []
    # Limit mixture-fit memory on larger training kits. Use complete machines.
    sampled = set(
        nsmallest(
            1024,
            (q["query_id"] for q in load_rows(data / "train/queries.csv")),
            key=lambda x: hashlib.sha256(x.encode()).digest(),
        )
    )
    for queries, hist in episode_reader(data / "train"):
        for q in queries:
            if q["query_id"] not in sampled:
                continue
            seq = hist.get(q["machine_id"], {})
            cut = int(q["cutoff"])
            ticks = np.array(
                sorted(
                    t for t in seq if t < cut and all(t - l in seq for l in range(1, 9))
                ),
                dtype=int,
            )
            if len(ticks) < 10:
                continue
            v = np.array([seq[t] for t in ticks])
            lags = np.array([[seq[t - l] for t in ticks] for l in range(1, 9)])
            bits = lags > 0
            match = np.array(
                [((bits[i - 1] ^ bits[j - 1]) == (v > 0)) * 2 - 1 for i, j in pairs]
            )
            correlations = (
                sum(abs(part.mean(1)) for part in np.array_split(match, 3, axis=1)) / 3
            )
            if correlations.max() > 0.38:
                # Divide ambiguous votes (e.g. very few payouts) across tied candidates.
                tied = np.where(correlations >= correlations.max() - 0.025)[0]
                for k in tied:
                    votes[pairs[k]] += 1 / len(tied)
            keep = v > 0
            if not keep.any():
                continue
            winning_pairs.append(pairs[int(np.argmax(correlations))])
            lagwin = lags[:, keep]
            table = np.asarray(
                model["sizes"].get(q["machine_type"], model["sizes"]["*"])
            )
            diff = np.log(table[1] / table[0])[np.searchsorted(PAYOUTS, v[keep]) - 1]
            x, y = lagwin[a - 1] >= ka[:, None], lagwin[b - 1] >= kb[:, None]
            pat = np.where(
                ops[:, None] == 0, x ^ y, np.where(ops[:, None] == 1, x | y, x & y)
            )
            size_evidence.append(((pat - 0.5) * diff).sum(axis=1))
    freq = votes.most_common()
    active = (
        [(a, b, n) for (a, b), n in freq[:6] if n >= 0.06 * freq[0][1]] if freq else []
    )
    if not active:
        active = [(a, b, 1) for a, b in pairs[:6]]
    total = sum(n for a, b, n in active)
    model["pairs"] = [[a, b, n / total] for a, b, n in active]
    pos = np.asarray(size_evidence)
    if not len(pos):
        model["size_rules"] = [[1, 1, 2, 2, 1, 0.5, 0.5]]
        return
    evidence = np.concatenate([pos, -pos], axis=1)
    lik = np.exp(evidence - evidence.max(1)[:, None])
    prior = np.ones(lik.shape[1]) / lik.shape[1]
    for _ in range(180):
        w = lik * prior
        prior = (w / w.sum(1)[:, None]).sum(0) + 0.001
        prior /= prior.sum()
    n = len(rules)
    priority = prior[:n] + prior[n:]
    top = [int(i) for i in np.argsort(-priority)[:4] if priority[i] > 0.002]
    if not top:
        top = [int(np.argmax(priority))]
    model["size_rules"] = [
        [*rules[i], float(prior[i]), float(prior[n + i])] for i in top
    ]
    model["size_by_pair"] = {}
    for a, b, _ in active:
        subset = lik[[p == (a, b) for p in winning_pairs]]
        if len(subset) < 8:
            continue
        pp = prior.copy()
        for _ in range(100):
            w = subset * pp
            pp = (w / w.sum(1)[:, None]).sum(0) + prior * 1.5
            pp /= pp.sum()
        importance = pp[:n] + pp[n:]
        chosen = [
            i
            for i in np.argsort(-importance)[:4]
            if importance[i] >= max(0.007, importance.max() * 0.15)
        ]
        if not chosen:
            chosen = [int(np.argmax(importance))]
        normalizer = sum(importance[chosen])
        model["size_by_pair"][str((a, b))] = [
            [*rules[i], float(pp[i] / normalizer), float(pp[n + i] / normalizer)]
            for i in chosen
        ]


def calibrate(data, model, selected):
    target = {
        r["query_id"]: (1 - float(r["p_0"]), float(r["p_1"]))
        for r in load_rows(data / "validation/targets.csv")
    }
    rows = defaultdict(list)
    for queries, hist in episode_reader(data / "validation"):
        if selected is not None and queries[0]["episode_id"] not in selected:
            continue
        for cut in sorted({q["cutoff"] for q in queries}):
            machines = machines_at_cutoff(
                [q for q in queries if q["cutoff"] == cut], hist, model
            )
            for m, (_, feat) in zip(machines, win_features(machines)):
                win, p1 = target[m.q["query_id"]]
                sz = p1 / max(1e-10, win) > sum(d[0] for d in model["sizes"][m.typ]) / 2
                y = (
                    math.log(max(1e-10, win) / max(1e-10, 1 - win))
                    - (int(sz) - 0.5) * model["size_effect"][m.typ]
                )
                on = int(y > sum(m.levels) / 2 + model["slope"] * m.signal)
                rows[m.typ].append((feat, y - m.peer_shift, on))
    # Shared slope and residual coefficients, with separate type and state intercepts.
    groups = sorted((typ, k) for typ in rows for k in (0, 1))
    X, y = [], []
    for typ, items in rows.items():
        for feat, z, k in items:
            X.append([float(g == (typ, k)) for g in groups] + feat[1:])
            y.append(z)
    X = np.array(X)
    center = np.array(
        [model["levels"][typ][k] for typ, k in groups]
        + [model["slope"], 0.5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
    )
    penalty = np.array([1.0] * len(groups) + [1, 3, 3, 3, 4, 3, 3, 4, 4, 4, 4, 3])
    coeff = np.linalg.solve(
        X.T @ X + np.diag(penalty), X.T @ np.array(y) + penalty * center
    )
    model["coef"] = {
        typ: [
            [float(coeff[groups.index((typ, k))]), *coeff[len(groups) :].tolist()]
            for k in (0, 1)
        ]
        for typ in rows
    }
    model["coef"]["*"] = [
        [l, *coeff[len(groups) :].tolist()] for l in model["levels"]["*"]
    ]


def dynamics(data, model):
    records = []
    # Bound the cost of fitting global priors when a larger round is supplied.
    ids = {q["episode_id"] for q in load_rows(data / "train/queries.csv")}
    chosen = set(nsmallest(96, ids, key=lambda e: hashlib.sha256(e.encode()).digest()))
    for queries, hist in episode_reader(data / "train"):
        if queries[0]["episode_id"] not in chosen:
            continue
        for cut in sorted({q["cutoff"] for q in queries}):
            ms = machines_at_cutoff(
                [q for q in queries if q["cutoff"] == cut], hist, model
            )
            if len(ms) > 32:
                ms = ms[:32]
            list(win_features(ms, records))
    result = {}
    for kind in ("sparse", "long"):
        evidence = [
            np.asarray(ev) for k, ev, _ in records if k == kind and len(ev[0]) == 22
        ]
        if len(evidence) < 4:
            continue
        # Give each training episode equal influence. Smooth the empirical
        # distribution to preserve support for other transition times.
        base = np.array([0.5] + [0.5 / 21] * 21)
        prior = base.copy()
        for _ in range(12):
            counts = 4 * base
            for ev in evidence:
                scores = ev + np.log(prior)
                weights = np.exp(scores - scores.max(1, keepdims=True))
                post = (weights / weights.sum(1, keepdims=True)).mean(0)
                counts += post
            counts[1:] = 0.5 * counts[1:] + 0.5 * np.convolve(
                np.pad(counts[1:], 1, mode="edge"), [0.25, 0.5, 0.25], "valid"
            )
            prior = counts / counts.sum()
        result[kind] = prior.tolist()
    rates = np.array([0.004, 0.008, 0.012, 0.017, 0.022, 0.03, 0.04, 0.06, 0.08])
    scores = np.zeros(len(rates))
    for _, _, times in records:
        p = np.full(len(rates), 0.5)
        last = None
        for tick, entry in sorted(times.items()):
            if last is not None:
                p = 0.5 + (p - 0.5) * (1 - 2 * rates) ** (tick - last)
            high = p * math.exp(min(300, entry))
            norm = 1 - p + high
            scores += np.log(norm)
            p = np.clip(high / norm, 1e-15, 1 - 1e-15)
            last = tick
    # Allow episode-level departures from the learned typical switching rate.
    weights = np.exp((scores - scores.max()) / 4)
    weights = 0.85 * weights / weights.sum() + 0.15 / len(rates)
    result["weather"] = [rates.tolist(), weights.tolist()]
    return result


def fit(data, selected=None):
    model = constants(data, selected)
    fit_peer(data, model, selected)
    discover(data, model)
    model["gap_tables"] = compile_tables(model)
    model["dynamics"] = dynamics(data, model)
    calibrate(data, model, selected)
    return model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--episodes", type=Path, help="Optional JSON list of calibration episode IDs"
    )
    args = ap.parse_args()
    chosen = set(json.loads(args.episodes.read_text())) if args.episodes else None
    args.out.write_text(json.dumps(fit(args.data, chosen), indent=2))
