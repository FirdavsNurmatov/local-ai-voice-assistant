"""Score integration-test outputs; optionally compare two runs (e.g. baseline vs candidate).

usage: python integration_score.py <run dir> [<other run dir> for comparison]
Writes <run dir>/summary.csv and per_sample.csv.
"""
import csv, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import normalize, align_ops, char_edits, repetition

def pct(xs, q):
    xs = sorted(xs); k = (len(xs) - 1) * q; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)

def load(run_dir):
    out = {}
    for f in sorted(Path(run_dir).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "results" in d:
            out[f.stem] = d
    return out

def score(run_dir):
    runs = load(run_dir); summary, per = [], []
    for name, d in runs.items():
        refs = {r["id"]: r for r in csv.DictReader(open(d["dataset"], encoding="utf-8"))}
        S = D = I = N = CE = CN = 0; ex = reps = 0; lat, langs, models, status = [], {}, {}, {}
        for r in d["results"]:
            c = refs[r["id"]]; j = r["response"]; text = j.get("text", "") if r["status"] == 200 else ""
            status[r["status"]] = status.get(r["status"], 0) + 1
            langs[j.get("language")] = langs.get(j.get("language"), 0) + 1
            models[j.get("model")] = models.get(j.get("model"), 0) + 1
            lat.append(r["latency"])
            row = {"run": name, "id": r["id"], "status": r["status"], "language": j.get("language"), "model": j.get("model"),
                   "latency_s": r["latency"], "reference": c.get("ref_raw", ""), "hypothesis": text, "error": j.get("error", "")}
            if c.get("ref_raw"):
                rw, hw = normalize(c["ref_raw"]), normalize(text)
                s, de, i = align_ops(rw, hw); S += s; D += de; I += i; N += len(rw)
                CE += char_edits(rw, hw); CN += len(" ".join(rw)); ex += rw == hw
                rp = repetition(text, rw, hw); reps += bool(rp)
                row.update(wer=round((s + de + i) / max(1, len(rw)), 4), exact=int(rw == hw), repetition=rp)
            per.append(row)
        n = len(d["results"])
        summary.append({"run": name, "language_param": d["language_param"], "multipart": d["multipart"], "n": n,
                        "status": json.dumps(status), "returned_language": json.dumps(langs), "model": json.dumps(models),
                        "micro_WER": round((S + D + I) / N, 4) if N else "", "CER": round(CE / CN, 4) if CN else "",
                        "exact": f"{ex}/{n}" if N else "", "repetition": reps if N else "",
                        "latency_median_s": round(statistics.median(lat), 2), "latency_p95_s": round(pct(lat, 0.95), 2),
                        "memory_before": json.dumps(d["health_before"].get("memory_mb")), "memory_after": json.dumps(d["health_after"].get("memory_mb"))})
    for fname, rows in (("summary.csv", summary), ("per_sample.csv", per)):
        keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
        with open(Path(run_dir) / fname, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    return summary, per

s1, p1 = score(sys.argv[1])
print(f"{'run':28} {'lang':5} {'n':>3} {'status':22} {'WER':>6} {'CER':>6} {'exact':>6} {'rep':>3} {'p50':>5} {'p95':>5} returned")
for s in s1:
    print(f"{s['run']:28} {s['language_param']:5} {s['n']:>3} {s['status']:22} {str(s['micro_WER']):>6} {str(s['CER']):>6} {s['exact']:>6} {str(s['repetition']):>3} "
          f"{s['latency_median_s']:>5} {s['latency_p95_s']:>5} {s['returned_language']}")
if len(sys.argv) > 2:
    s2, p2 = score(sys.argv[2])
    a = {(r["run"], r["id"]): r for r in p1}; b = {(r["run"], r["id"]): r for r in p2}
    common = sorted(set(a) & set(b))
    same_text = sum(a[k]["hypothesis"] == b[k]["hypothesis"] and a[k]["status"] == b[k]["status"] for k in common)
    print(f"\ncomparison: {len(common)} common requests, identical status+text: {same_text}")
    for k in common:
        if a[k]["hypothesis"] != b[k]["hypothesis"] or a[k]["status"] != b[k]["status"]:
            print(f"  DIFF {k[0]}/{k[1]}: {a[k]['status']} {a[k]['hypothesis'][:60]!r} -> {b[k]['status']} {b[k]['hypothesis'][:60]!r}")
