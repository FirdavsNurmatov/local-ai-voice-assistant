"""Write dataset CSVs for the synthetic Uzbek set and the RU/EN regression set (kept separate from FLEURS)."""
import csv, hashlib, json, sys, wave
from pathlib import Path
EVAL = Path(sys.argv[1]); ROOT = EVAL.parent
fields = ["id", "file", "dataset", "speech", "lang", "kind", "seconds", "sha256", "ref_raw"]

def secs(p):
    with wave.open(str(p)) as w:
        return round(w.getnframes() / w.getframerate(), 3)

syn = []
for c in json.loads((EVAL / "synthetic" / "subset.json").read_text(encoding="utf-8")):
    p = Path(c["file"])
    syn.append({"id": c["id"], "file": str(p), "dataset": "synthetic_uz_tts", "speech": "synthetic (project Uzbek VITS ONNX TTS)",
                "lang": "uz", "kind": c["kind"], "seconds": secs(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "ref_raw": c["ref"]})
refs = json.loads((ROOT / "stt-test-audio" / "references.json").read_text(encoding="utf-8"))
rue = []
for k in ("ru_req", "ru_short", "ru_long", "ru_req_noise", "en_req", "en_short", "en_long", "en_req_noise"):
    p = ROOT / "stt-test-audio" / f"{k}.wav"
    rue.append({"id": k, "file": str(p), "dataset": "synthetic_ru_en_kokoro", "speech": "synthetic (Kokoro masha/af_heart)",
                "lang": k[:2], "kind": "noise" if "noise" in k else k.split("_")[1], "seconds": secs(p),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "ref_raw": refs[k.replace("_noise", "")]})
for name, rows in (("synthetic_uz.csv", syn), ("regression_ru.csv", [r for r in rue if r["lang"] == "ru"]),
                   ("regression_en.csv", [r for r in rue if r["lang"] == "en"])):
    with open(EVAL / "datasets" / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(name, len(rows))
