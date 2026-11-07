"""Run a frozen House Edge entry on every benchmark data root.

Usage: python run_entry.py --entry path/to/entry.zip --name baseline --set dev [--bench .] [--python python]
For each data/<set>/<scenario>/<mask>/ it runs, from the unpacked entry folder:
    <python> predict.py --data <root> --out results/<set>/<name>/<scenario>/<mask>.csv
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time, zipfile, hashlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--set", default="dev", choices=["dev", "sealed"])
    ap.add_argument("--bench", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()
    bench = os.path.abspath(a.bench)
    work = tempfile.mkdtemp(prefix="he_entry_")
    if a.entry.endswith(".zip"):
        zipfile.ZipFile(a.entry).extractall(work)
        sha = hashlib.sha256(open(a.entry, "rb").read()).hexdigest()
    else:
        shutil.copytree(a.entry, work, dirs_exist_ok=True)
        sha = None
    out_dir = os.path.join(bench, "results", a.set, a.name)
    os.makedirs(out_dir, exist_ok=True)
    log = {"entry": os.path.abspath(a.entry), "entry_sha256": sha, "set": a.set, "runs": {}}
    data_set = os.path.join(bench, "data", a.set)
    for scn in sorted(os.listdir(data_set)):
        for mask in sorted(os.listdir(os.path.join(data_set, scn))):
            root = os.path.join(data_set, scn, mask)
            out = os.path.join(out_dir, scn, f"{mask}.csv")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            t0 = time.time()
            r = subprocess.run([a.python, "predict.py", "--data", root, "--out", out], cwd=work,
                               capture_output=True, text=True, timeout=a.timeout)
            log["runs"][f"{scn}/{mask}"] = {"seconds": round(time.time() - t0, 2), "returncode": r.returncode,
                                           "stderr_tail": r.stderr[-500:]}
            print(f"{scn}/{mask}: rc={r.returncode} {time.time()-t0:.1f}s", flush=True)
    with open(os.path.join(out_dir, "run_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
