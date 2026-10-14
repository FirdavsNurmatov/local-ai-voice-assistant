"""Score run files -> per-sample CSV + summary CSV (+ console table).

usage: python score.py <runs dir> <datasets dir> <out dir>
Every run JSON in <runs dir> named <dataset>__<config>__<lang>__<device>.json is scored
against the dataset CSV it names. Smoke/parity files are skipped unless named that way.
"""
import csv, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import normalize, align_ops, char_edits, repetition, has_cyrillic, has_digit

runs_dir, ds_dir, out_dir = (Path(a) for a in sys.argv[1:4])
out_dir.mkdir(parents=True, exist_ok=True)
datasets = {p.stem: {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))} for p in ds_dir.glob("*.csv")}

def pct(xs, q):
    xs = sorted(xs); k = (len(xs) - 1) * q; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)

per_sample, summary = [], []
for f in sorted(runs_dir.glob("*__*__*__*.json")):
    ds_name, cfg, lang, dev = f.stem.split("__")
    run = json.loads(f.read_text(encoding="utf-8")); refs = datasets[ds_name]
    S = D = I = N = CE = CN = 0; wers, exact, reps, wrong, cyr, errs, lat, dur = [], 0, 0, 0, 0, 0, [], []
    S_nd = D_nd = I_nd = N_nd = 0
    for r in run["results"]:
        c = refs[r["id"]]
        rw, hw = normalize(c["ref_raw"]), normalize(r.get("text", ""))
        s, d, i = align_ops(rw, hw); ce = char_edits(rw, hw); cn = len(" ".join(rw))
        S += s; D += d; I += i; N += len(rw); CE += ce; CN += cn
        if not has_digit(c["ref_raw"]):
            S_nd += s; D_nd += d; I_nd += i; N_nd += len(rw)
        w = (s + d + i) / max(1, len(rw)); wers.append(w)
        ex = rw == hw; exact += ex
        rp = repetition(r.get("text", ""), rw, hw); reps += bool(rp)
        wl = (r.get("language") not in (None, c["lang"])); wrong += wl
        cy = has_cyrillic(r.get("text", "")) and not has_cyrillic(c["ref_raw"]); cyr += cy
        errs += bool(r.get("error")); lat.append(r["latency"]); dur.append(float(c["seconds"]))
        per_sample.append({"dataset": ds_name, "config": cfg, "lang_mode": lang, "device": dev, "id": c["id"],
                           "speech": c["speech"], "stratum": c.get("stratum") or c.get("kind", ""), "seconds": c["seconds"],
                           "reference_raw": c["ref_raw"], "hypothesis_raw": r.get("text", ""), "error": r.get("error", ""),
                           "returned_language": r.get("language"), "raw_detected_language": r.get("raw_language", ""),
                           "raw_detected_p": r.get("raw_language_p", ""), "ref_words": len(rw), "sub": s, "del": d, "ins": i,
                           "wer": round(w, 4), "cer": round(ce / max(1, cn), 4), "exact_match": int(ex),
                           "repetition": rp, "wrong_language": int(wl), "cyrillic_output": int(cy),
                           "ref_has_digits": int(has_digit(c["ref_raw"])), "latency_s": r["latency"],
                           "rtf": round(r["latency"] / float(c["seconds"]), 3),
                           "reference_norm": " ".join(rw), "hypothesis_norm": " ".join(hw)})
    n = len(run["results"])
    gpu_delta = (run["gpu_peak_mb"] - run["gpu_base_mb"]) if run.get("gpu_peak_mb") and run.get("gpu_base_mb") is not None else ""
    summary.append({"dataset": ds_name, "config": cfg, "lang_mode": lang, "device": dev, "n": n,
                    "micro_WER": round((S + D + I) / max(1, N), 4), "macro_WER": round(statistics.mean(wers), 4),
                    "micro_CER": round(CE / max(1, CN), 4), "WER_no_digit_refs": round((S_nd + D_nd + I_nd) / max(1, N_nd), 4),
                    "sub": S, "del": D, "ins": I, "ref_words": N,
                    "exact_match_rate": round(exact / n, 4), "repetition_rate": round(reps / n, 4), "repetition_n": reps,
                    "wrong_language_rate": round(wrong / n, 4) if lang == "auto" else "n/a (forced)",
                    "cyrillic_output_n": cyr, "empty_or_error_n": errs,
                    "latency_median_s": round(statistics.median(lat), 2), "latency_p95_s": round(pct(lat, 0.95), 2),
                    "audio_s": round(sum(dur), 1), "RTF": round(sum(lat) / sum(dur), 3),
                    "load_s": run["load_s"], "rss_after_load_mb": run["rss_after_load_mb"],
                    "peak_rss_inference_mb": run["peak_rss_inference_mb"], "peak_commit_process_mb": run["peak_commit_process_mb"],
                    "peak_rss_process_mb": run["peak_rss_process_mb"], "gpu_vram_delta_mb": gpu_delta,
                    "gpu_util_mean": run.get("gpu_util_mean") or "", "gpu_util_max": run.get("gpu_util_max") or "",
                    "services_running": ",".join(k for k, v in run["services_at_start"].items() if v)})

for name, rows in (("per_sample_results.csv", per_sample), ("summary.csv", summary)):
    with open(out_dir / name, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"{'dataset':24} {'config':14} {'lang':4} {'dev':4} {'n':>3} {'microWER':>8} {'macroWER':>8} {'CER':>6} {'exact':>6} {'rep':>4} {'wrongL':>7} {'p50':>5} {'p95':>5} {'RTF':>5} {'load':>5} {'RSSinf':>6} {'commit':>6} {'VRAM':>5}")
for s in summary:
    print(f"{s['dataset']:24} {s['config']:14} {s['lang_mode']:4} {s['device']:4} {s['n']:>3} {s['micro_WER']:>8.3f} {s['macro_WER']:>8.3f} {s['micro_CER']:>6.3f} "
          f"{s['exact_match_rate']:>6.2f} {s['repetition_n']:>4} {str(s['wrong_language_rate'])[:7]:>7} {s['latency_median_s']:>5} {s['latency_p95_s']:>5} {s['RTF']:>5} "
          f"{s['load_s']:>5} {s['peak_rss_inference_mb']:>6} {s['peak_commit_process_mb']:>6} {str(s['gpu_vram_delta_mb']):>5}")
