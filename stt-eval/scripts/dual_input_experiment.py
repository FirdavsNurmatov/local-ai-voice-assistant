"""Does giving the LLM the original Uzbek text next to the machine translation reduce misunderstandings?

usage: python dual_input_experiment.py <out.json>
Uses only running services: chat server :8765 (MADLAD translation via /api/chat) and Ollama :11434 (qwen3:1.7b).
For every item we have the CORRECT Uzbek text (reference) and the STT transcript (NavAI, with real recognition errors).
The LLM is asked to restate what the user meant, deterministically (temperature 0, fixed seed), in three modes:
  translation_only  - what the pipeline does today: English machine translation of the transcript
  dual              - original transcript + its translation (proposed "solution 2")
  reference_upper   - translation of the correct text (upper bound)
"""
import csv, json, re, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[2]; OUT = Path(sys.argv[1])
SYSTEM = ("Restate in ONE short English sentence what the user said or asked. "
          "Output only that sentence. Do not answer the question.")
DUAL_TEMPLATE = ("Original message in Uzbek (from speech recognition; may contain recognition or spelling errors):\n"
                 "{original}\n\n"
                 "Machine translation into English (may contain translation errors):\n"
                 "{translation}\n\n"
                 "If the translation and the original disagree, trust the meaning of the original.")

def post(url, payload, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def translate(text):
    return post("http://127.0.0.1:8765/api/chat", {"text": text, "language": "uz"})["english_input"]

def restate(user_content):
    j = post("http://127.0.0.1:11434/api/chat", {
        "model": "qwen3:1.7b", "stream": False, "think": False, "keep_alive": "10m",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_content}],
        "options": {"temperature": 0, "seed": 42, "num_ctx": 2048, "num_predict": 60}})
    return j["message"]["content"].strip()

def chrf(hyp, ref, n=6, beta=2.0):
    """chrF (character n-gram F-score, Popovic 2015), lower-cased, spaces removed."""
    h, r = re.sub(r"\s+", "", hyp.lower()), re.sub(r"\s+", "", ref.lower())
    ps, rs = [], []
    for k in range(1, n + 1):
        hg = [h[i:i + k] for i in range(len(h) - k + 1)]; rg = [r[i:i + k] for i in range(len(r) - k + 1)]
        if not hg or not rg: continue
        from collections import Counter
        hc, rc = Counter(hg), Counter(rg); m = sum((hc & rc).values())
        ps.append(m / len(hg)); rs.append(m / len(rg))
    if not ps: return 0.0
    p, rr = sum(ps) / len(ps), sum(rs) / len(rs)
    return 0.0 if p + rr == 0 else (1 + beta ** 2) * p * rr / (beta ** 2 * p + rr)

COMMAND_KEYWORDS = {"cmd_01": [["stop"]], "cmd_02": [["left"]], "cmd_03": [["right"]], "cmd_04": [["forward", "ahead", "front"]],
                    "cmd_05": [["back", "backward", "reverse"]], "cmd_06": [["slow"]], "cmd_07": [["fast", "speed", "quick"]],
                    "cmd_08": [["library"]], "cmd_09": [["open"], ["door"]], "cmd_10": [["yes"]], "cmd_11": [["no", "not"]], "cmd_12": [["stop"]]}
def has_keywords(text, groups):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return all(any(any(w.startswith(k) for w in words) for k in g) for g in groups)

items = []
refs = {r["id"]: r for r in csv.DictReader(open(R / "stt-eval/datasets/fleurs_uz_holdout.csv", encoding="utf-8"))}
for r in json.load(open(R / "stt-eval/integration/production/uz_holdout_uz.json", encoding="utf-8"))["results"]:
    items.append({"id": r["id"], "set": "fleurs_holdout", "reference": refs[r["id"]]["ref_raw"], "transcript": r["response"].get("text", "")})
crefs = {r["id"]: r for r in csv.DictReader(open(R / "stt-eval/datasets/uz_commands_synthetic.csv", encoding="utf-8"))}
for r in json.load(open(R / "stt-eval/integration/production/uz_commands_uz.json", encoding="utf-8"))["results"]:
    items.append({"id": r["id"], "set": "commands", "reference": crefs[r["id"]]["ref_raw"], "transcript": r["response"].get("text", "")})

results = []
for k, it in enumerate(items, 1):
    if not it["transcript"]:
        it["skipped"] = "empty transcript"; results.append(it); continue
    t0 = time.perf_counter()
    it["translation_ref"] = translate(it["reference"])
    it["translation_hyp"] = translate(it["transcript"])
    it["restate_translation_only"] = restate(it["translation_hyp"])
    it["restate_dual"] = restate(DUAL_TEMPLATE.format(original=it["transcript"], translation=it["translation_hyp"]))
    it["restate_reference_upper"] = restate(it["translation_ref"])
    ref_en = it["translation_ref"]
    it["chrf_translation_hyp_vs_ref"] = round(chrf(it["translation_hyp"], ref_en), 2)
    for m in ("translation_only", "dual", "reference_upper"):
        it[f"chrf_{m}"] = round(chrf(it[f"restate_{m}"], ref_en), 2)
    if it["set"] == "commands":
        for m in ("translation_only", "dual", "reference_upper"):
            it[f"command_ok_{m}"] = has_keywords(it[f"restate_{m}"], COMMAND_KEYWORDS[it["id"]])
        it["command_ok_translation_hyp"] = has_keywords(it["translation_hyp"], COMMAND_KEYWORDS[it["id"]])
    it["seconds"] = round(time.perf_counter() - t0, 1)
    results.append(it)
    print(f"{k:2}/{len(items)} {it['id']:11} chrF trans {it['chrf_translation_hyp_vs_ref']:5.1f} | only {it['chrf_translation_only']:5.1f} dual {it['chrf_dual']:5.1f} upper {it['chrf_reference_upper']:5.1f}"
          + (f" | cmd only={it['command_ok_translation_only']} dual={it['command_ok_dual']}" if it["set"] == "commands" else ""), flush=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
