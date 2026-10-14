"""Checksum manifest of models and datasets used in the evaluation -> stt-eval/manifest_sha256.csv"""
import csv, hashlib, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); EVAL = ROOT / "stt-eval"
SOURCES = {
    "stt-models/faster-whisper-small": "https://huggingface.co/Systran/faster-whisper-small @ 536b0662742c02347bc0e980a01041f333bce120",
    "stt-models/navai-whisper-small-uzbek-hf": "https://huggingface.co/navai-uz/whisper-small-uzbek @ 4b432caf21c2752bca3384b5df1d41cf0da2801d (+ tokenizer.json written locally by transformers)",
    "stt-models/navai-whisper-small-uzbek-ct2-int8": "converted locally: ct2-transformers-converter --quantization int8 (ctranslate2 4.8.3, transformers 5.19.0)",
    "stt-eval/fleurs": "https://huggingface.co/datasets/google/fleurs data/uz_uz (test split) @ 70bb2e84b976b7e960aa89f1c648e09c59f894dd, CC-BY-4.0",
    "stt-eval/synthetic": "generated locally with tts_onnx_server.py (Uzbek VITS ONNX)",
}
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
rows = []
for rel, src in SOURCES.items():
    base = ROOT / rel
    for p in sorted(x for x in base.rglob("*") if x.is_file()):
        if "sample" in p.parts or p.suffix == ".json" and base.name == "synthetic":
            continue   # per-clip hashes of extracted samples are in datasets/*.csv
        rows.append({"path": str(p.relative_to(ROOT)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha(p), "source": src})
with open(EVAL / "manifest_sha256.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["path", "bytes", "sha256", "source"]); w.writeheader(); w.writerows(rows)
print(len(rows), "files hashed")
