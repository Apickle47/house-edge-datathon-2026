"""Offline inference for the House Edge probability forecast."""

import argparse
from bisect import bisect_left
from collections import defaultdict
import csv
import itertools
import json
import math
from pathlib import Path
from general import flexible, family_weights, pooled_frequency

PAYOUTS = (0, 1, 2, 5, 20)
COLUMNS = ["p_" + str(v) for v in PAYOUTS]


def logistic(x):
    return 1 / (1 + math.exp(-max(-50, min(50, x))))


def weights(scores):
    maximum = max(scores)
    raw = [math.exp(v - maximum) for v in scores]
    total = sum(raw)
    return [v / total for v in raw], maximum + math.log(total)


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as src:
        yield from csv.DictReader(src)


def episode_reader(folder):
    """Keep only one episode's spins in RAM, also for unsorted CSV input."""
    groups = defaultdict(list)
    for row in load_rows(folder / "queries.csv"):
        groups[row["episode_id"]].append(row)
    # The public kit groups rows by episode. Stream directly where possible.
    history = folder / "history.csv"
    seen = set()
    ordered = True
    for ep, block in itertools.groupby(load_rows(history), lambda r: r["episode_id"]):
        if ep in seen:
            ordered = False
            break
        seen.add(ep)
        for _ in block:
            pass
    if ordered:
        for ep, block in itertools.groupby(
            load_rows(history), lambda r: r["episode_id"]
        ):
            if ep in groups:
                seq = defaultdict(dict)
                for r in block:
                    seq[r["machine_id"]][int(r["tick"])] = int(r["payout"])
                yield groups.pop(ep), seq
    else:
        # Re-scan interleaved logs in bounded batches; the official runner limits scratch space.
        ids = iter(groups)
        while batch := list(itertools.islice(ids, 128)):
            blocks = {ep: defaultdict(dict) for ep in batch}
            for r in load_rows(history):
                if r["episode_id"] in blocks:
                    blocks[r["episode_id"]][r["machine_id"]][int(r["tick"])] = int(
                        r["payout"]
                    )
            for ep in batch:
                yield groups[ep], blocks[ep]
        return
    for queries in groups.values():
        yield queries, defaultdict(dict)


def peer_totals(queries, histories, cutoff):
    totals = defaultdict(lambda: [0, 0])
    for mid in {q["machine_id"] for q in queries}:
        for tick, value in histories.get(mid, {}).items():
            if tick < cutoff:
                totals[tick][0] += value > 0
                totals[tick][1] += 1
    return totals


def peer_feature(totals, seq, tick, center=0.5):
    wins, seen = totals.get(tick, (0, 0))
    if tick in seq:
        wins -= seq[tick] > 0
        seen -= 1
    return (wins / seen - center) if seen else 0.0


def machines_at_cutoff(queries, hist, model):
    totals = peer_totals(queries, hist, int(queries[0]["cutoff"]))
    return [Machine(q, hist.get(q["machine_id"], {}), model, totals) for q in queries]


class Machine:
    def __init__(self, q, seq, model, totals=None):
        self.q = q
        self.cut = int(q["cutoff"])
        self.seq = {t: v for t, v in seq.items() if t < self.cut}
        self.ticks = sorted(self.seq)
        self.typ = q["machine_type"]
        self.signal = int(q["signal"])
        self.weather_scale = model.get("weather_scale", 0.4)
        self.dynamics = model.get("dynamics", {})
        self.levels = model["levels"].get(self.typ, model["levels"]["*"])
        size_effect = model["size_effect"].get(self.typ, model["size_effect"]["*"])
        self.win = [
            [
                logistic(v + model["slope"] * self.signal + (s - 0.5) * size_effect)
                for s in (0, 1)
            ]
            for v in self.levels
        ]
        lag, effect = model.get("peer_lag", [1, 0.0])
        self.peer_shift = (
            effect * peer_feature(totals or {}, self.seq, self.cut - lag)
            if totals is not None
            else 0.0
        )
        shifts = (
            [effect * peer_feature(totals, self.seq, t - lag) for t in self.ticks]
            if totals is not None
            else [0.0] * len(self.ticks)
        )
        by_shift = {
            d: [
                [
                    logistic(
                        v + model["slope"] * self.signal + (s - 0.5) * size_effect + d
                    )
                    for s in (0, 1)
                ]
                for v in self.levels
            ]
            for d in set(shifts)
        }
        win_history = [by_shift[d] for d in shifts]
        self.short = len(self.seq) < 0.7 * max(1, self.cut)
        self.hypotheses = []
        # A missing lag is marginalized with the observed win frequency.
        marginal = (2 + sum(v > 0 for v in self.seq.values())) / (4 + len(self.seq))
        for a, b, prior in model["pairs"]:

            def parity(t):
                va, vb = self.seq.get(t - a), self.seq.get(t - b)
                pa = marginal if va is None else float(va > 0)
                pb = marginal if vb is None else float(vb > 0)
                return pa + pb - 2 * pa * pb

            parities = [parity(t) for t in self.ticks]
            for size_prior, sizes, next_size, rule, orient in size_hypotheses(
                self, model, (a, b)
            ):
                gap_model = (
                    model.get("gap_tables", {}).get(rule, {}) if self.short else {}
                )
                size_table = model["sizes"].get(self.typ, model["sizes"]["*"])
                if gap_model:
                    _, _, r, threshold = map(int, rule.split(","))

                    def mask_at(t):
                        bits = []
                        for lag, limit in [(a, 1), (b, 1), (r, threshold), (1, 1)]:
                            v = self.seq.get(t - lag)
                            bits.append(0 if v is None else 1 + int(v >= limit))
                        if 0 not in bits[:3]:
                            return None
                        return bits[0] + 3 * bits[1] + 9 * bits[2] + 27 * bits[3]

                    masks = [mask_at(t) for t in self.ticks]
                for sign in [1, -1]:
                    on = parities if sign == 1 else [1 - x for x in parities]
                    forward, reverse = [0.0], [0.0]
                    pf, pr = [], []
                    plus = gap_model.get(f"{self.typ},{self.signal},{sign},{orient}")
                    minus = gap_model.get(f"{self.typ},{self.signal},{-sign},{orient}")

                    def integrate(joint, outcome, approximate_size, local_win):
                        win = sum(
                            joint[2 * k + j] * local_win[k][j]
                            for k in (0, 1)
                            for j in (0, 1)
                        )
                        if outcome == 0:
                            return win, 1 - win
                        i = PAYOUTS.index(outcome) - 1
                        full = sum(
                            joint[2 * k + j] * local_win[k][j] * size_table[j][i]
                            for k in (0, 1)
                            for j in (0, 1)
                        )
                        # size_prior already includes the geometric interpolation.
                        divisor = (
                            size_table[0][i] ** (1 - approximate_size)
                            * size_table[1][i] ** approximate_size
                        )
                        return win, full / divisor

                    for idx, (t, x, s) in enumerate(zip(self.ticks, on, sizes)):
                        local_win = win_history[idx]
                        lo, hi = [row[0] + s * (row[1] - row[0]) for row in local_win]
                        p = lo + x * (hi - lo)
                        z = lo + (1 - x) * (hi - lo)
                        if plus and masks[idx] is not None:
                            p0, p = integrate(
                                plus[masks[idx]], self.seq[t], s, local_win
                            )
                            p1, z = integrate(
                                minus[masks[idx]], self.seq[t], s, local_win
                            )
                            pf.append(p0)
                            pr.append(p1)
                        else:
                            pf.append(p)
                            pr.append(z)
                            if self.seq[t] == 0:
                                p, z = 1 - p, 1 - z
                        forward.append(forward[-1] + math.log(max(1e-12, p)))
                        reverse.append(reverse[-1] + math.log(max(1e-12, z)))
                    next_on = parity(self.cut)
                    if sign < 0:
                        next_on = 1 - next_on
                    self.hypotheses.append(
                        (
                            math.log(prior * 0.5) + size_prior,
                            on,
                            next_on,
                            forward,
                            reverse,
                            pf,
                            pr,
                            next_size,
                            (plus[mask_at(self.cut)], minus[mask_at(self.cut)])
                            if plus and mask_at(self.cut) is not None
                            else None,
                        )
                    )

    def candidate(self, switch):
        at = bisect_left(self.ticks, switch)
        scores = [h[0] + h[3][at] + h[4][-1] - h[4][at] for h in self.hypotheses]
        return weights(scores)

    def features(self, switches, episode_weights, local):
        joint = [[0.0, 0.0], [0.0, 0.0]]
        expected = [0.0] * len(self.ticks)
        history_win = [0.0] * len(self.ticks)
        for switch, sw, local_weights in zip(switches, episode_weights, local):
            at = bisect_left(self.ticks, switch)
            for h, prob in zip(self.hypotheses, local_weights):
                w = sw * prob
                if w < 1e-9:
                    continue
                _, on, nxt, _, _, pf, pr, sz, missing_joint = h
                active = nxt if switch > self.cut else 1 - nxt
                for k, pk in enumerate((1 - active, active)):
                    if missing_joint:
                        dist = missing_joint[int(switch <= self.cut)]
                        joint[k][0] += w * dist[2 * k]
                        joint[k][1] += w * dist[2 * k + 1]
                    else:
                        joint[k][0] += w * pk * (1 - sz)
                        joint[k][1] += w * pk * sz
                for j, x in enumerate(on):
                    expected[j] += w * (x if j < at else 1 - x)
                    history_win[j] += w * (pf[j] if j < at else pr[j])
        scales = (1e10, 48.0, 14.0, 4.0)
        residual, information = [0.0] * 6, [0.0] * 6
        for t, on, p in zip(self.ticks, expected, history_win):
            err = (self.seq[t] > 0) - p
            for i, scale in enumerate(scales):
                w = 1.0 if i == 0 else math.exp((t - self.cut) / scale)
                residual[i] += w * err
                information[i] += w * p * (1 - p)
            for i, fraction in enumerate((1 - on, on), 4):
                residual[i] += fraction * err
                information[i] += fraction * p * (1 - p)
        total = sum(map(sum, joint))
        self.history_win = history_win
        return [[x / total for x in row] for row in joint], residual, information


def win_features(machines, training=None):
    cutoff = machines[0].cut
    switches = [cutoff + 1] + sorted(
        set(int(cutoff * f / 100) for f in range(29, 92, 3))
    )
    count = len(switches) - 1
    kind = "sparse" if sum(m.short for m in machines) > len(machines) / 2 else "long"
    prior = machines[0].dynamics.get(kind, [])
    if len(prior) != len(switches):
        prior = [0.5] + [0.5 / count] * count
    logprior = [math.log(x) for x in prior]
    traces = [[m.candidate(c) for c in switches] for m in machines]
    episode_scores = [
        prior + sum(trace[j][1] for trace in traces) for j, prior in enumerate(logprior)
    ]
    ep_weights, episode_evidence = weights(episode_scores)
    details = []
    for m, trace in zip(machines, traces):
        # Predict this machine's switch time from the rest of its episode.
        _, neighbor_evidence = weights(
            [x - v[1] for x, v in zip(episode_scores, trace)]
        )
        # A machine can also switch independently of its neighbors.
        private_weights, private_evidence = weights(
            [prior + value[1] for prior, value in zip(logprior, trace)]
        )
        mode, combined = weights(
            [episode_evidence - neighbor_evidence, private_evidence]
        )
        switch_weights = [
            mode[0] * shared + mode[1] * private
            for shared, private in zip(ep_weights, private_weights)
        ]
        _, size_factor = weights([h[0] for h in m.hypotheses])
        m.win_evidence = combined - math.log(2) - size_factor
        m.size_factor = size_factor
        details.append(m.features(switches, switch_weights, [a for a, _ in trace]))
    ep_r = [sum(d[1][j] for d in details) for j in range(4)]
    ep_i = [sum(d[2][j] for d in details) for j in range(4)]
    # A two-state filter pools timestamped evidence from all machines.
    # Compare switch rates by marginal likelihood, accounting for gaps in ticks.
    scale = machines[0].weather_scale
    times = defaultdict(float)
    for m in machines:
        for t, p in zip(m.ticks, m.history_win):
            if t < 8:
                continue
            a = p * (math.exp(scale) - 1) + 1
            b = p * (math.exp(-scale) - 1) + 1
            times[t] += math.log(b / a) + (2 * scale if m.seq[t] > 0 else 0.0)

    def update(hazard):
        hot = 0.5
        last = None
        evidence = 0.0
        for t, logratio in sorted(times.items()):
            if last is not None:
                hot = 0.5 + (hot - 0.5) * (1 - 2 * hazard) ** (t - last)
            probs, log_likelihood = weights(
                [math.log1p(-hot), math.log(hot) + logratio]
            )
            hot = probs[1]
            evidence += log_likelihood
            last = t
        if last is not None:
            hot = 0.5 + (hot - 0.5) * (1 - 2 * hazard) ** (cutoff - last)
        return evidence, (2 * hot - 1) * scale

    rates, rate_prior = machines[0].dynamics.get(
        "weather", [(0.008, 0.025, 0.07), [1 / 3] * 3]
    )
    candidates = [update(rate) for rate in rates]
    mix, _ = weights([v[0] + math.log(p) for v, p in zip(candidates, rate_prior)])
    if training is not None:
        training.append((kind, [[ev for _, ev in tr] for tr in traces], dict(times)))
    weather = sum(w * v[1] for w, v in zip(mix, candidates))
    for m, (on, res, info) in zip(machines, details):
        machine = [r / (3 + i) for r, i in zip(res, info)]
        shared = [
            (r - mr) / (8 + i - mi) for r, mr, i, mi in zip(ep_r, res, ep_i, info)
        ]
        yield on, [1.0, m.signal, *machine, *shared, weather]


def size_hypotheses(m, model, pair):
    table = model["sizes"].get(m.typ, model["sizes"]["*"])
    diffs = [math.log(b / a) for a, b in zip(*table)]
    rules = model.get("size_by_pair", {}).get(str(tuple(pair)), model["size_rules"])
    for a, b, ta, tb, op, prior_plus, prior_minus in rules:

        def state(t):
            x, y = m.seq.get(t - a), m.seq.get(t - b)
            if x is None or y is None:
                return 0.5
            x, y = x >= ta, y >= tb
            return float((x != y) if op == 0 else ((x or y) if op == 1 else (x and y)))

        history = [state(t) for t in m.ticks]
        d = sum(
            (s - 0.5) * diffs[PAYOUTS.index(m.seq[t]) - 1]
            for t, s in zip(m.ticks, history)
            if m.seq[t] > 0
        )
        s = state(m.cut)
        key = f"{pair[0]},{pair[1]},{a},{ta}" if a == b and ta == tb and op != 0 else ""
        yield math.log(prior_plus) + d, history, s, key, 1
        yield math.log(prior_minus) - d, [1 - x for x in history], 1 - s, key, -1


def forecast(queries, hist, model):
    # A common cutoff is usual. Rebuild neighbor features at each requested cutoff.
    for cutoff in sorted({int(q["cutoff"]) for q in queries}):
        current = [q for q in queries if int(q["cutoff"]) == cutoff]
        machines = machines_at_cutoff(current, hist, model)
        features = list(win_features(machines))
        win_options = [flexible(m.seq, cutoff) for m in machines]
        size_options = [flexible(m.seq, cutoff, size=True) for m in machines]
        win_options = pooled_frequency(win_options, machines)
        size_options = pooled_frequency(size_options, machines, size=True)
        win_mix = family_weights(
            [m.win_evidence - opt[0] for m, opt in zip(machines, win_options)]
        )
        size_odds = []
        for m, opt in zip(machines, size_options):
            table = model["sizes"].get(m.typ, model["sizes"]["*"])
            log_base = [0.5 * (math.log(a) + math.log(b)) for a, b in zip(*table)]
            size_odds.append(
                m.size_factor
                + sum(log_base[PAYOUTS.index(v) - 1] for v in m.seq.values() if v > 0)
                - opt[0]
            )
        size_mix = family_weights(size_odds)
        for idx, (m, (joint, feat)) in enumerate(zip(machines, features)):
            coef = model["coef"].get(m.typ, model["coef"]["*"])
            size_effect = model["size_effect"].get(m.typ, model["size_effect"]["*"])
            table = model["sizes"].get(m.typ, model["sizes"]["*"])
            win_size = [0.0, 0.0]
            for k, row in enumerate(coef):
                intercept = m.peer_shift + sum(x * y for x, y in zip(feat, row))
                for s in (0, 1):
                    win_size[s] += joint[k][s] * logistic(
                        intercept + (s - 0.5) * size_effect
                    )
            specialist_win = sum(win_size)
            win = (
                win_mix[idx] * specialist_win
                + (1 - win_mix[idx]) * win_options[idx][1][1]
            )
            conditional = [
                (win_size[0] * a + win_size[1] * b) / max(1e-15, specialist_win)
                for a, b in zip(*table)
            ]
            sizes = [
                size_mix[idx] * p + (1 - size_mix[idx]) * alt
                for p, alt in zip(conditional, size_options[idx][1])
            ]
            yield [m.q["query_id"], max(0.0, 1 - win), *[win * s for s in sizes]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", type=Path, default=Path(__file__).with_name("model.json"))
    p.add_argument("--split", choices=["test", "validation"], default="test")
    args = p.parse_args()
    model = json.loads(args.model.read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["query_id", *COLUMNS])
        for queries, hist in episode_reader(args.data / args.split):
            writer.writerows(forecast(queries, hist, model))


if __name__ == "__main__":
    main()
