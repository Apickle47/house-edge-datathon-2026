"""Online alternatives for histories that differ from the training distribution."""

from functools import lru_cache
from itertools import combinations
from math import exp, lgamma, log


def normalize(values):
    peak = max(values)
    terms = [exp(x - peak) for x in values]
    total = sum(terms)
    return [x / total for x in terms], peak + log(total)


@lru_cache(maxsize=8192)
def gamma_half(count):
    return lgamma(0.5 + count) - lgamma(0.5)


def context_model(contexts, labels, classes):
    """Integrated likelihood and next probabilities for a categorical transition table.

    Contexts has one extra element for the forecast tick. An unknown lag is its
    own context. Each row uses a symmetric Dirichlet half-count prior.
    """
    counts = {}
    for context, label in zip(contexts, labels):
        if context not in counts:
            counts[context] = [0] * classes
        counts[context][label] += 1
    log_likelihood = sum(
        lgamma(classes * 0.5)
        - lgamma(sum(row) + classes * 0.5)
        + sum(gamma_half(n) for n in row)
        for row in counts.values()
    )
    target = counts.get(contexts[-1], [0] * classes)
    probs = [(0.5 + c) / (0.5 * classes + sum(target)) for c in target]
    return log_likelihood, probs


def mixture(candidates):
    weights, score = normalize([s for s, _ in candidates])
    probabilities = [
        sum(w * p for w, p in zip(weights, col))
        for col in zip(*(p for _, p in candidates))
    ]
    return score - log(len(candidates)), probabilities


def three_lag_models(lags, labels):
    """Score three-lag parity and unrestricted binary tables with bit counts."""
    n = len(labels)
    all_ticks = (1 << n) - 1

    def packed(values):
        return sum(1 << i for i, x in enumerate(values) if x)

    wins = packed(labels)
    patterns = [
        (packed(x >= 0 for x in lag[:-1]), packed(x > 0 for x in lag[:-1]), lag[-1])
        for lag in lags
    ]

    @lru_cache(maxsize=2048)
    def row(count, paid):
        return gamma_half(paid) + gamma_half(count - paid) - lgamma(count + 1), (
            paid + 0.5
        ) / (count + 1)

    def table(cells, target):
        log_score = 0.0
        next_win = 0.5
        for j, mask in enumerate(cells):
            score, p = row(mask.bit_count(), (mask & wins).bit_count())
            log_score += score
            if j == target:
                next_win = p
        return log_score, [1 - next_win, next_win]

    parities, full = [], []
    for (ma, a, xa), (mb, b, xb), (mc, c, xc) in combinations(patterns, 3):
        seen = ma & mb & mc
        missing = all_ticks ^ seen
        target = (
            -1
            if min(xa, xb, xc) < 0
            else int(xa > 0) * 4 + int(xb > 0) * 2 + int(xc > 0)
        )
        odd = seen & (a ^ b ^ c)
        parities.append(
            table(
                [missing, seen ^ odd, odd],
                0 if target < 0 else 1 + target.bit_count() % 2,
            )
        )
        cells = [seen]
        for bit in (a, b, c):
            cells = [child for mask in cells for child in (mask & ~bit, mask & bit)]
        full.append(table([missing, *cells], target + 1))
    return mixture([mixture(parities), mixture(full)])


def reversing_pairs(lags, labels, times, cutoff):
    """Integrate over two-lag rules whose high and low rates exchange once."""
    observations = (1 << len(labels)) - 1

    def pack(xs):
        return sum(1 << i for i, x in enumerate(xs) if x)

    wins = pack(labels)
    patterns = [
        (pack(v >= 0 for v in lag[:-1]), pack(v > 0 for v in lag[:-1]), lag[-1])
        for lag in lags
    ]
    changes = [
        pack(t >= cutoff * f for t in times[:-1])
        for f in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    ]

    @lru_cache(maxsize=4096)
    def row(n, y):
        return gamma_half(n - y) + gamma_half(y) - lgamma(n + 1), (y + 0.5) / (n + 1)

    def stats(mask):
        return row(mask.bit_count(), (mask & wins).bit_count())

    candidates = []
    for (ma, a, xa), (mb, b, xb) in combinations(patterns, 2):
        seen = ma & mb
        unknown_log, unknown_prob = stats(observations ^ seen)
        wanted = None if min(xa, xb) < 0 else 2 * (xa > 0) + (xb > 0)
        # Each singleton truth table and its complement share a partition.
        # This includes conjunction, disjunction and mixed-sign lag rules.
        for cell, active in enumerate((~a & ~b, ~a & b, a & ~b, a & b)):
            for change in changes:
                group = seen & (active ^ change)
                plus, p_plus = stats(group)
                minus, p_minus = stats(seen ^ group)
                # Every candidate changepoint is before the forecast cutoff.
                p = (
                    unknown_prob
                    if wanted is None
                    else (p_minus if wanted == cell else p_plus)
                )
                candidates.append((unknown_log + plus + minus, [1 - p, p]))
    return mixture(candidates)


def flexible(sequence, cutoff, size=False, allow_reversal=False):
    classes = 4 if size else 2
    ticks = sorted(t for t, v in sequence.items() if not size or v > 0)
    payout_index = {1: 0, 2: 1, 5: 2, 20: 3}
    labels = [
        payout_index[sequence[t]] if size else int(sequence[t] > 0) for t in ticks
    ]
    times = ticks + [cutoff]
    stationary = context_model([0] * len(times), labels, classes)
    breaks = [
        context_model([int(t >= fraction * cutoff) for t in times], labels, classes)
        for fraction in (0.35, 0.5, 0.65, 0.8, 0.9)
    ]
    groups = [stationary, mixture(breaks)]
    lags = [[sequence.get(t - lag, -1) for t in times] for lag in range(1, 9)]
    single = []
    for threshold in (1, 2, 5):
        for lag in lags:
            keys = [-1 if x < 0 else int(x >= threshold) for x in lag]
            single.append(context_model(keys, labels, classes))
    groups.append(mixture(single))
    if not size:
        parity, full = [], []
        for a, b in combinations(lags, 2):
            cells = [
                -1 if x < 0 or y < 0 else 2 * (x > 0) + (y > 0) for x, y in zip(a, b)
            ]
            full.append(context_model(cells, labels, classes))
            parity.append(
                context_model(
                    [-1 if x < 0 else int(x in (1, 2)) for x in cells], labels, classes
                )
            )
        groups.extend([mixture(parity), mixture(full)])
        # Keep the prior for the larger family modest in short windows.
        three_score, three_probs = three_lag_models(lags, labels)
        former_score, former_probs = mixture(groups)
        w, total = normalize([former_score + log(0.9), three_score + log(0.1)])
        probabilities = [w[0] * x + w[1] * y for x, y in zip(former_probs, three_probs)]
        if allow_reversal:
            rev_score, rev_probs = reversing_pairs(lags, labels, times, cutoff)
            mix, total = normalize([total + log(0.90), rev_score + log(0.10)])
            probabilities = [
                mix[0] * x + mix[1] * y for x, y in zip(probabilities, rev_probs)
            ]
        return total, probabilities
    return mixture(groups)


def family_weights(log_odds):
    """Use other machines as evidence for how widespread a distribution shift is.

    The episode may mix familiar and unfamiliar machines. Integrate over its
    unknown proportion, with a prior favoring the released training population.
    """
    fractions = [0.01, 0.25, 0.75, 0.99]
    priors = [0.05, 0.1, 0.15, 0.70]
    totals = [log(p) for p in priors]
    conditional = []
    for odds in log_odds:
        probs = []
        for i, fraction in enumerate(fractions):
            weights, evidence = normalize([log(1 - fraction), log(fraction) + odds])
            totals[i] += evidence
            probs.append(weights[1])
        conditional.append(probs)
    family, _ = normalize(totals)
    return [sum(w * p for w, p in zip(family, row)) for row in conditional]


def pooled_frequency(options, machines, size=False):
    """Shrink stationary rates toward other machines of the same observed type.

    Exclude the target machine. Strong temporal evidence still favors a
    transition model. The weak prior is used if no comparable peers exist.
    """
    from collections import Counter, defaultdict

    observed = [Counter(m.seq.values()) for m in machines]
    groups = defaultdict(Counter)
    for m, c in zip(machines, observed):
        groups[m.typ].update(c)
    results = []

    def counts(hist):
        if size:
            return [hist[k] for k in (1, 2, 5, 20)]
        return [hist[0], sum(hist[k] for k in (1, 2, 5, 20))]

    for m, own, option in zip(machines, observed, options):
        other = counts(groups[m.typ] - own)
        if not sum(other):
            results.append(option)
            continue
        y = counts(own)
        total = sum(y)
        d = len(y)
        prior = [(n + 0.5) / (sum(other) + d * 0.5) for n in other]
        pooled = []
        for strength in (4.0, 16.0, 64.0):
            effective = min(strength, sum(other))
            alpha = [v * effective for v in prior]
            logp = (
                lgamma(effective)
                - lgamma(total + effective)
                + sum(lgamma(a + n) - lgamma(a) for a, n in zip(alpha, y))
            )
            pooled.append(
                (logp, [(a + n) / (total + effective) for a, n in zip(alpha, y)])
            )
        score, p = mixture(pooled)
        w, ev = normalize([option[0] + log(0.8), score + log(0.2)])
        results.append((ev, [w[0] * a + w[1] * b for a, b in zip(option[1], p)]))
    return results
