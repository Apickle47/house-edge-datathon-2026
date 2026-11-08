"""Compile small conditional probability tables for gaps in observed histories."""

from itertools import product
import numpy as np


def compile_tables(model):
    result = {}
    for a, b, _ in model["pairs"]:
        rules = model.get("size_by_pair", {}).get(str((a, b)), model["size_rules"])
        for r, r2, threshold, threshold2, op, _, _ in rules:
            if r != r2 or threshold != threshold2 or op == 0:
                continue
            depth = max(b, r)
            radices = [3] * r + [2] * (depth - r)
            if np.prod(radices) > 2500:
                continue
            key = f"{a},{b},{r},{threshold}"
            if key in result:
                continue
            states = np.array(
                list(product(*(range(k) for k in radices))), dtype=np.int8
            )
            size = len(states)
            shifts = []
            for digit in range(3):
                digits = np.column_stack([np.full(size, digit), states[:, :-1]])
                if r < depth:
                    digits[:, r] = digits[:, r] > 0
                shifts.append(np.ravel_multi_index(digits.T, radices))
            truth = np.array(
                [
                    states[:, a - 1] > 0,
                    states[:, b - 1] > 0,
                    states[:, r - 1] == 2,
                    states[:, 0] > 0,
                ]
            )
            # 0 = missing, 1 = false, 2 = true. Add a one-spin context to
            # retain some information even if both interaction lags are hidden.
            index = np.arange(81)
            flags = (index[:, None] // np.array([1, 3, 9, 27])) % 3
            compatible = np.all(
                (flags[:, :, None] == 0) | (flags[:, :, None] == truth[None, :, :] + 1),
                axis=1,
            )
            table = {}
            for typ in model["sizes"]:
                if typ == "*":
                    continue
                sz_dist = np.asarray(model["sizes"][typ])
                large = sz_dist[:, np.array([1, 2, 5, 20]) >= threshold].sum(axis=1)
                for signal, sign, orientation in product([-1, 0, 1], [1, -1], [1, -1]):
                    on = (truth[0] ^ truth[1]) ^ (sign < 0)
                    sz = truth[2] ^ (orientation < 0)
                    regime = 2 * on.astype(int) + sz.astype(int)
                    logits = (
                        np.asarray(model["levels"][typ])[on.astype(int)]
                        + model["slope"] * signal
                        + (sz.astype(float) - 0.5) * model["size_effect"][typ]
                    )
                    win = 1 / (1 + np.exp(-logits))
                    big = win * large[sz.astype(int)]
                    probs = [1 - win, win - big, big]
                    dist = np.full(size, 1 / size)
                    for _ in range(1800):
                        nxt = sum(
                            np.bincount(s, weights=dist * p, minlength=size)
                            for s, p in zip(shifts, probs)
                        )
                        if np.max(abs(nxt - dist)) < 1e-10:
                            break
                        dist = nxt
                    joint = np.column_stack(
                        [
                            np.sum(
                                compatible[:, regime == j] * dist[regime == j], axis=1
                            )
                            for j in range(4)
                        ]
                    )
                    joint /= np.maximum(joint.sum(axis=1, keepdims=True), 1e-20)
                    table[f"{typ},{signal},{sign},{orientation}"] = np.round(
                        joint, 10
                    ).tolist()
            result[key] = table
    return result
