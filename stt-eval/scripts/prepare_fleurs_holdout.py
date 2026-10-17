"""Extract FLEURS uz test recordings whose SENTENCES were not used in the 120-clip benchmark sample.

usage: python -I prepare_fleurs_holdout.py <stt-eval dir> [N=40] [seed=20261015]
Writes <dir>/fleurs/holdout/*.wav and <dir>/datasets/fleurs_uz_holdout.csv
"""
import csv, hashlib, random, struct, sys, tarfile
from pathlib import Path

EVAL = Path(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 20261015
FL = EVAL / "fleurs"; OUT = FL / "holdout"; OUT.mkdir(parents=True, exist_ok=True)

used = {r["sentence_id"] for r in csv.DictReader(open(EVAL / "datasets" / "fleurs_uz_test_sample.csv", encoding="utf-8"))}
rows = []
with open(FL / "test.tsv", encoding="utf-8", newline="") as f:
    for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
        if r[0] not in used:
            rows.append({"sentence_id": r[0], "file": r[1], "ref_raw": r[2], "num_samples": int(r[5]), "gender": r[6]})
rng = random.Random(SEED)
by_sid = {}
for r in rows:
    by_sid.setdefault(r["sentence_id"], []).append(r)
sids = sorted(by_sid)
chosen = [rng.choice(sorted(by_sid[s], key=lambda x: x["file"])) for s in rng.sample(sids, N)]
want = {r["file"]: r for r in chosen}
found = {}
with tarfile.open(FL / "test.tar.gz", "r:gz") as tar:
    for m in tar:
        base = m.name.replace("\\", "/").split("/")[-1]
        if m.isfile() and base in want:
            data = tar.extractfile(m).read(); (OUT / base).write_bytes(data); found[base] = data

def wav_info(data):
    pos = 12
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            tag, ch, sr, _, block, bits = struct.unpack("<HHIIHH", data[pos + 8:pos + 24]); fmt = (ch, sr, block)
        elif cid == b"data":
            return fmt[1], fmt[0], size // fmt[2]
        pos += 8 + size + (size & 1)

out = []
for i, r in enumerate(sorted(chosen, key=lambda x: x["num_samples"]), 1):
    data = found[r["file"]]; sr, ch, n = wav_info(data)
    assert sr == 16000 and ch == 1 and abs(n - r["num_samples"]) <= 1, r["file"]
    out.append({"id": f"holdout_{i:02d}", "file": str(OUT / r["file"]), "dataset": "fleurs_uz_holdout", "speech": "human",
                "lang": "uz", "stratum": "", "sentence_id": r["sentence_id"], "gender": r["gender"],
                "seconds": round(n / sr, 3), "sha256": hashlib.sha256(data).hexdigest(), "ref_raw": r["ref_raw"]})
with open(EVAL / "datasets" / "fleurs_uz_holdout.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
assert not ({r["sentence_id"] for r in out} & used)
print(f"holdout: {len(out)} recordings from {len(sids)} unused sentences (seed {SEED}); "
      f"{min(r['seconds'] for r in out):.1f}-{max(r['seconds'] for r in out):.1f}s; overlap with benchmark sentences: 0")
