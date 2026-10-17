"""Black-box test of a running STT endpoint (stt_server.py or the server.py proxy).

usage: python integration_test.py <base_url> <dataset.csv> <language|auto|none> <out.json> [multipart]
  base_url  e.g. http://127.0.0.1:8769 (direct) or http://127.0.0.1:8765 (proxy)
  language  value for ?language= ; 'none' sends no parameter (what the page does in "Avto" mode)
Records the full JSON response, HTTP status and latency of every clip, plus /api/health before and after.
"""
import csv, json, mimetypes, sys, time, urllib.request, urllib.error, uuid
from pathlib import Path

base, ds, lang, out = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
multipart = len(sys.argv) > 5 and sys.argv[5] == "multipart"
health_url = base + ("/api/stt/health" if base.endswith(":8765") else "/api/health")
CTYPES = {".wav": "audio/wav", ".webm": "audio/webm;codecs=opus", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".mp3": "audio/mpeg"}

def health():
    try:
        with urllib.request.urlopen(health_url, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def post(data, ctype):
    url = base + "/api/transcribe" + ("" if lang == "none" else f"?language={lang}")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read()), time.perf_counter() - t
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), time.perf_counter() - t

results = []
h0 = health()
for c in csv.DictReader(open(ds, encoding="utf-8")):
    p = Path(c["file"]); data = p.read_bytes() if p.exists() else b""
    ctype = CTYPES.get(p.suffix.lower(), "application/octet-stream")
    if multipart:
        b = uuid.uuid4().hex
        data = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{p.name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
        ctype = f"multipart/form-data; boundary={b}"
    st, j, dt = post(data, ctype)
    results.append({"id": c["id"], "status": st, "latency": round(dt, 3), "response": j})
    print(f"{c['id']:14} {st} {dt:5.2f}s lang={j.get('language')} model={j.get('model')} | {(j.get('text') or j.get('error') or '')[:90]}", flush=True)
h1 = health()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"base": base, "dataset": str(ds), "language_param": lang, "multipart": multipart,
                           "health_before": h0, "health_after": h1, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
