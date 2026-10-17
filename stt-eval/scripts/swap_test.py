"""Alternate Russian / Uzbek / English requests to check model routing and swapping.

usage: python swap_test.py <base_url> <out.json>
"""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
R = Path(__file__).resolve().parents[2]; A = R / "stt-test-audio"; C = R / "stt-eval" / "commands"
base, out = sys.argv[1].rstrip("/"), Path(sys.argv[2])
if ":8769" in base and "--allow-production" not in sys.argv:
    raise SystemExit("refusing production port")
seq = [("ru_req.wav", None), (C / "cmd_04.wav", "uz"), ("en_req.wav", None), (C / "cmd_02.wav", "uz"),
       ("ru_req.wav", "ru"), ("uz_long.wav", "uz"), ("en_short.wav", "en"), ("uz_long.wav", None), ("ru_short.wav", None)]
def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as r: return json.loads(r.read())
rows = []
for f, lang in seq:
    p = f if isinstance(f, Path) else A / f
    url = base + "/api/transcribe" + (f"?language={lang}" if lang else "")
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=p.read_bytes(), headers={"Content-Type": "audio/wav"}), timeout=300) as r:
            st, j = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        st, j = e.code, json.loads(e.read())
    h = get("/api/health")
    row = {"file": p.name, "language_param": lang or "auto", "status": st, "latency": round(time.perf_counter() - t, 2),
           "language": j.get("language"), "model": j.get("model"), "text": (j.get("text") or j.get("error") or "")[:80],
           "uz_loaded": h["uz_model"]["loaded"], "base_loaded": h["uz_model"]["base_model_loaded"],
           "swaps": h["uz_model"]["model_swaps"], "memory": h["memory_mb"], "free_commit_mb": h["free_commit_mb"]}
    rows.append(row); print(row, flush=True)
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
