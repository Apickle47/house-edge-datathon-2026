"""Score mock adaptation test forecasts against sealed truth with the kit's official contest scorer.
Usage: python score_sealed.py A=path.csv B=path.csv C=path.csv   (run from the sealed/ folder; kit at ../kit)"""
import sys, csv, json, random, collections, math, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kit"))
from slot_forecasting.contest import contest_score
from slot_forecasting.io import read_submission, read_targets, read_queries
P = ["p_0", "p_1", "p_2", "p_5", "p_20"]
qs = {q.query_id: q for q in read_queries(HERE.parent / "kit/public/test/queries.csv")}
targets = read_targets(HERE / "test_targets.csv")
groups = {r["query_id"]: r["condition"] for r in csv.DictReader(open(HERE / "test_conditions.csv"))}
reference = read_submission(HERE / "test_reference.csv", set(qs))
entries = dict(a.split("=", 1) for a in sys.argv[1:])
preds, report = {}, {}
for name, path in entries.items():
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    ids = [r["query_id"] for r in rows]
    missing, extra, dup = set(qs) - set(ids), set(ids) - set(qs), len(ids) - len(set(ids))
    bad = [r["query_id"] for r in rows if any(not math.isfinite(float(r[k])) or float(r[k]) < 0 or float(r[k]) > 1 for k in P)
           or abs(sum(float(r[k]) for k in P) - 1) > 1e-6]
    print(f"{name}: {path}\n  sha256 {hashlib.sha256(open(path,'rb').read()).hexdigest()}  rows {len(rows)}  missing {len(missing)}  extra {len(extra)}  duplicates {dup}  invalid {len(bad)}")
    preds[name] = read_submission(path, set(qs))
    res = contest_score(preds[name], targets, groups, reference, max_points=40)
    report[name] = res
    print(f"  points {res['technical_points']:.4f} / 40   " + json.dumps({k: round(v, 5) for k, v in res.items() if isinstance(v, (int, float)) and k != 'technical_points'})[:400])
    for k, v in res.items():
        if isinstance(v, dict): print("  ", k, {c: (round(x, 5) if isinstance(x, float) else x) for c, x in v.items()})
if "B" in preds and "C" in preds:
    tmap = {t.query_id: t for t in targets}
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for qid, t in tmap.items(): by[groups[qid]][t.episode_id].append(qid)
    def pts(name, sample):
        ids = [q for c in sample for e in sample[c] for q in by[c][e]]
        # resampled episodes may repeat: give each copy a unique id
        T, G, Pr, Rf, k = [], {}, {}, {}, 0
        for c in sample:
            for e in sample[c]:
                k += 1
                for q in by[c][e]:
                    nid = f"{q}.r{k}"; t = tmap[q]
                    T.append(type(t)(nid, f"{t.episode_id}.r{k}", t.probabilities, t.outcome)); G[nid] = c
                    Pr[nid] = preds[name][q]; Rf[nid] = reference[q]
        return contest_score(Pr, T, G, Rf, max_points=40)["technical_points"]
    full = {c: sorted(by[c]) for c in by}
    d0 = pts("C", full) - pts("B", full)
    rng = random.Random(20261107); ds = []
    for _ in range(400):
        s = {c: [rng.choice(full[c]) for _ in full[c]] for c in full}
        ds.append(pts("C", s) - pts("B", s))
    ds.sort()
    print(f"\nPaired C - B points: {d0:+.4f}  95% CI [{ds[9]:+.4f}, {ds[389]:+.4f}]  (400 resamples of whole episodes within condition)")
