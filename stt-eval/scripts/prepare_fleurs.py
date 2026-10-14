"""Verify the FLEURS uz_uz test archive and extract a reproducible, length-stratified sample.

usage: python -I prepare_fleurs.py <stt-eval dir> [N=120] [seed=20261014]
Writes <dir>/fleurs/sample/*.wav and <dir>/datasets/fleurs_uz_test_sample.csv
"""
import csv, hashlib, io, json, random, sys, tarfile, wave
from pathlib import Path

EVAL = Path(sys.argv[1]); N = int(sys.argv[2]) if len(sys.argv) > 2 else 120
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 20261014
FL = EVAL / "fleurs"; OUT = FL / "sample"; OUT.mkdir(parents=True, exist_ok=True)
(EVAL / "datasets").mkdir(exist_ok=True)
EXPECTED_TAR_SHA256 = sys.argv[4] if len(sys.argv) > 4 else None

h = hashlib.sha256()
with open(FL / "test.tar.gz", "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
tar_sha = h.hexdigest()
print("test.tar.gz sha256", tar_sha, "match" if tar_sha == EXPECTED_TAR_SHA256 else f"(expected {EXPECTED_TAR_SHA256})")

rows = []
with open(FL / "test.tsv", encoding="utf-8", newline="") as f:
    for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
        rows.append({"sentence_id": r[0], "file": r[1], "ref_raw": r[2], "ref_fleurs_norm": r[3],
                     "num_samples": int(r[5]), "gender": r[6]})
print("tsv rows", len(rows), "sentences", len({r["sentence_id"] for r in rows}),
      "genders", sorted({r["gender"] for r in rows}))

# one recording per sentence (random speaker), then stratify by duration terciles
rng = random.Random(SEED)
by_sid = {}
for r in rows:
    by_sid.setdefault(r["sentence_id"], []).append(r)
pool = [rng.choice(sorted(v, key=lambda x: x["file"])) for _, v in sorted(by_sid.items())]
pool.sort(key=lambda r: (r["num_samples"], r["file"]))
k = len(pool) // 3
strata = {"short": pool[:k], "medium": pool[k:2 * k], "long": pool[2 * k:]}
chosen = []
for name, s in strata.items():
    for r in rng.sample(s, N // 3 + (1 if name == "long" and N % 3 else 0) + (1 if name == "medium" and N % 3 == 2 else 0)):
        chosen.append(dict(r, stratum=name))
chosen.sort(key=lambda r: r["num_samples"])
want = {r["file"]: r for r in chosen}

found = {}
with tarfile.open(FL / "test.tar.gz", "r:gz") as tar:
    for m in tar:
        base = m.name.replace("\\", "/").split("/")[-1]
        if m.isfile() and base in want:
            data = tar.extractfile(m).read()
            (OUT / base).write_bytes(data)          # written under our own name only
            found[base] = data

def wav_info(data):
    """RIFF header parser that also handles IEEE-float WAV (format 3, used by FLEURS)."""
    import struct
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE", "not a RIFF/WAVE file"
    pos, fmt = 12, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            tag, ch, sr, _, block, bits = struct.unpack("<HHIIHH", data[pos + 8:pos + 24]); fmt = (tag, ch, sr, block, bits)
        elif cid == b"data":
            return fmt[2], fmt[1], size // fmt[3], f"tag{fmt[0]}/{fmt[4]}bit"
        pos += 8 + size + (size & 1)
    raise ValueError("no data chunk")


bad = []
out_rows = []
for i, r in enumerate(chosen, 1):
    data = found.get(r["file"])
    if data is None:
        bad.append((r["file"], "missing")); continue
    sr, ch, n, fmt = wav_info(data)
    if sr != 16000 or ch != 1 or abs(n - r["num_samples"]) > 1:
        bad.append((r["file"], f"sr={sr} ch={ch} frames={n} tsv={r['num_samples']}"))
    out_rows.append({"id": f"fleurs_{i:03d}", "file": str(OUT / r["file"]), "dataset": "fleurs_uz_test",
                     "speech": "human", "lang": "uz", "stratum": r["stratum"], "sentence_id": r["sentence_id"],
                     "gender": r["gender"], "seconds": round(n / sr, 3), "sample_rate": sr, "channels": ch, "wav_format": fmt,
                     "sha256": hashlib.sha256(data).hexdigest(), "ref_raw": r["ref_raw"]})
with open(EVAL / "datasets" / "fleurs_uz_test_sample.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
secs = [r["seconds"] for r in out_rows]
print(f"selected {len(out_rows)} recordings (seed {SEED}); integrity problems: {bad or 'none'}")
for s in ("short", "medium", "long"):
    xs = [r["seconds"] for r in out_rows if r["stratum"] == s]
    print(f"  {s:6} n={len(xs)}  {min(xs):.1f}-{max(xs):.1f}s")
print(f"  total audio {sum(secs)/60:.1f} min, mean {sum(secs)/len(secs):.1f}s; refs with digits: {sum(any(c.isdigit() for c in r['ref_raw']) for r in out_rows)}")
json.dump({"tar_sha256": tar_sha, "seed": SEED, "n": len(out_rows)}, open(EVAL / "datasets" / "fleurs_sample_info.json", "w"))
