"""Overall paired CI: resample independent episodes within each scenario, keeping all four masks of an
episode together. Statistic = equal-weight mean over scenario x mask cells of (candidate - baseline)."""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import read_truth, read_forecast, episode_errors
bench = os.path.dirname(os.path.abspath(__file__)); st = sys.argv[1]; base, cand = sys.argv[2], sys.argv[3]
T = read_truth(bench, st)
combos = sorted({(s, m) for s, m, _ in T})
diff = {}  # (scn, mask) -> {episode_index: diff}
for scn, mask in combos:
    e = {}
    for n in (base, cand):
        e[n], _ = episode_errors(T, read_forecast(os.path.join(bench, "results", st, n, scn, mask + ".csv")), scn, mask)
    # key episodes by their index within scenario (episode ids are shared across masks)
    diff[(scn, mask)] = {ep: e[cand][ep] - e[base][ep] for ep in e[base]}
scns = sorted({s for s, _ in combos}); masks = sorted({m for _, m in combos})
eps = {s: sorted(diff[(s, masks[0])]) for s in scns}
def stat(sample):
    vals = []
    for s in scns:
        for m in masks:
            d = diff[(s, m)]
            vals.append(sum(d[e] for e in sample[s]) / len(sample[s]))
    return sum(vals) / len(vals)
point = stat(eps)
rng = random.Random(11); reps = []
for _ in range(4000):
    reps.append(stat({s: [rng.choice(eps[s]) for _ in eps[s]] for s in scns}))
reps.sort()
print(f"overall paired diff ({cand} - {base}) = {point:+.5f}  95% CI [{reps[99]:+.5f}, {reps[3899]:+.5f}]  (4000 resamples, stratified by scenario, masks kept together)")
# per-scenario (all masks pooled)
for s in scns:
    def st1(sample):
        return sum(sum(diff[(s, m)][e] for e in sample) / len(sample) for m in masks) / len(masks)
    r = sorted(st1([rng.choice(eps[s]) for _ in eps[s]]) for _ in range(2000))
    print(f"  {s:11s} {st1(eps[s]):+.5f} [{r[49]:+.5f}, {r[1949]:+.5f}]")
