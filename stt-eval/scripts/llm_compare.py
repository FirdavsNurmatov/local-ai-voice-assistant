"""Compare chat pipelines on Uzbek questions and commands (clean text and real STT transcripts).

usage: python llm_compare.py <pipeline> <out.json>
pipelines:
  server            current chat server (/api/chat): MADLAD in -> model -> MADLAD out (model = server's CHAT_MODEL)
  server_dual       same + original Uzbek text given next to the translation (dual_input=true)
  direct:<model>    Ollama model gets the Uzbek text directly and must answer in Uzbek (no MADLAD)
  server_direct     hybrid: model reads the Uzbek text directly, answers in English, MADLAD translates the
                    answer to Uzbek (/api/chat with direct_input=true; model = server's CHAT_MODEL)
Measures: answer correctness (keywords in the final Uzbek answer), answer language, command understanding
(model restates the command in English; action keyword check), latency.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[2]; D = R / "stt-eval" / "llm_compare"
pipeline, out = sys.argv[1], Path(sys.argv[2])
LANG = sys.argv[3] if len(sys.argv) > 3 else "uz"     # uz: questions + STT versions + commands; ru: questions only
CHAT, OLLAMA = "http://127.0.0.1:8765/api/chat", "http://127.0.0.1:11434/api/chat"
DIRECT_SYSTEM = ("You are a helpful, friendly assistant. The user writes in Uzbek; the text may come from speech "
                 "recognition and contain recognition errors. Answer ONLY in Uzbek using the Latin alphabet, "
                 "in 1-3 concise sentences. Do not include reasoning or thinking.")
RESTATE_SYSTEM = ("Restate in ONE short English sentence what the user said or asked. "
                  "Output only that sentence. Do not answer the question.")
DUAL_TEMPLATE = ("Original message in Uzbek (may come from speech recognition; may contain recognition or spelling errors):\n"
                 "{original}\n\nMachine translation into English (may contain translation errors):\n{translation}\n\n"
                 "If the translation and the original disagree, trust the meaning of the original.")
COMMAND_KEYWORDS = {"cmd_01": [["stop"]], "cmd_02": [["left"]], "cmd_03": [["right"]], "cmd_04": [["forward", "ahead", "front"]],
                    "cmd_05": [["back", "backward", "reverse"]], "cmd_06": [["slow"]], "cmd_07": [["fast", "speed", "quick"]],
                    "cmd_08": [["library"]], "cmd_09": [["open"], ["door"]], "cmd_10": [["yes"]], "cmd_11": [["no", "not"]], "cmd_12": [["stop"]]}

def post(url, payload, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

THINK = pipeline.startswith("direct-think:")      # thinking models: reasoning is returned separately

def ollama(model, system, user, temperature, num_predict):
    payload = {"model": model, "stream": False, "keep_alive": "30m",
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "options": {"temperature": temperature, "num_ctx": 4096 if THINK else 2048,
                           "num_predict": 2048 if THINK else num_predict}}
    if model.startswith("qwen3"):
        payload["think"] = THINK
    j = post(OLLAMA, payload)
    LAST_TOKENS.update(model=model, prompt_tokens=j.get("prompt_eval_count"), output_tokens=j.get("eval_count"),
                       thinking_chars=len(j["message"].get("thinking") or ""),
                       generation_s=round((j.get("eval_duration") or 0) / 1e9, 2))
    return j["message"]["content"].strip()
LAST_TOKENS = {}

DIRECT_SYSTEM_EN = ("You are a helpful, friendly assistant. Answer in English in 1-3 concise sentences. "
                    "Do not include reasoning or thinking.")
DIRECT_SYSTEM_RU = ("You are a helpful, friendly assistant. The user writes in Russian. Answer ONLY in Russian "
                    "(Cyrillic alphabet), in 1-3 concise sentences. Do not include reasoning or thinking.")

def norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[‘’'`ʻʼ´]", "'", s)
    return s

def answer_ok(answer, keywords):
    a = norm(answer)
    for kw in keywords:
        k = norm(kw)
        if k.startswith("="):
            if re.search(r"(?<![\w'])" + re.escape(k[1:]) + r"(?![\w'])", a): return True
        elif re.search(r"(?<![\w'])" + re.escape(k), a):
            return True
    return False

EN_WORDS = set("the is are a an of to and in it you i this that for with what which how be your can".split())
def answer_language(answer):
    if LANG == "en":
        if re.search(r"[Ѐ-ӿ]", answer): return "cyrillic"
        words = re.findall(r"[a-zA-Z']+", answer.lower())
        return "empty" if not words else ("english" if sum(w in EN_WORDS for w in words) / len(words) > 0.1 else "other")
    if LANG == "ru":
        cyr = len(re.findall(r"[Ѐ-ӿ]", answer)); lat = len(re.findall(r"[A-Za-z]", answer))
        return "empty" if cyr + lat == 0 else ("russian" if cyr >= 0.8 * (cyr + lat) else "mixed/latin")
    if re.search(r"[Ѐ-ӿ]", answer): return "cyrillic"
    words = re.findall(r"[a-zA-Z']+", answer.lower())
    if not words: return "empty"
    en = sum(w in EN_WORDS for w in words) / len(words)
    return "english" if en > 0.2 else "uzbek-latin"

def has_keywords(text, groups):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return all(any(any(w.startswith(k) for w in words) for k in g) for g in groups)

server_model = None
if pipeline.startswith("server"):
    server_model = json.loads(urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=10).read())["model"]

qs = json.loads((D / f"questions_{LANG}.json").read_text(encoding="utf-8"))
import csv
items = []
for q in qs:
    items.append({"id": q["id"], "kind": "question", "input": "clean", "text": q["text"], "keywords": q["answer_keywords"]})
    if q.get("stt_text"):
        items.append({"id": q["id"], "kind": "question", "input": "stt", "text": q["stt_text"], "keywords": q["answer_keywords"]})
if LANG == "uz" and not THINK:     # thinking model: questions only (commands use command_compare.py)
    cmds ={r["id"]: r for r in csv.DictReader(open(R / "stt-eval/datasets/uz_commands_synthetic.csv", encoding="utf-8"))}
    cmd_stt = {r["id"]: r["response"].get("text", "") for r in json.load(open(R / "stt-eval/integration/production/uz_commands_uz.json", encoding="utf-8"))["results"]}
    for cid, c in cmds.items():
        items.append({"id": cid, "kind": "command", "input": "clean", "text": c["ref_raw"]})
        if cmd_stt.get(cid):
            items.append({"id": cid, "kind": "command", "input": "stt", "text": cmd_stt[cid]})

results = []
first = True
# resume: keep items already finished in an earlier, interrupted run of the same pipeline
if out.exists():
    try:
        prev = json.loads(out.read_text(encoding="utf-8"))
        if prev.get("pipeline") == pipeline and prev.get("language", "uz") == LANG:
            results = prev["results"]; first = False
            print(f"resuming after {len(results)} finished items", flush=True)
    except Exception:
        results = []
done_keys = {(r["id"], r["kind"], r["input"]) for r in results}
for k, it in enumerate(items, 1):
    if (it["id"], it["kind"], it["input"]) in done_keys:
        continue
    t = time.perf_counter()
    if it["kind"] == "question":
        if pipeline.startswith("server"):
            j = post(CHAT, {"text": it["text"], "language": LANG, "dual_input": pipeline == "server_dual",
                            "direct_input": pipeline == "server_direct"})
            it.update(answer=j["answer"], answer_english=j["answer_english"], english_input=j["english_input"],
                      timings=j["timings"], dual_input=j.get("dual_input"), direct_input=j.get("direct_input"),
                      llm=j.get("llm"))
        else:
            it["answer"] = ollama(pipeline.split(":", 1)[1], {"ru": DIRECT_SYSTEM_RU, "en": DIRECT_SYSTEM_EN}.get(LANG, DIRECT_SYSTEM), it["text"], 0.4, 160)
            it["llm"] = dict(LAST_TOKENS)
        it["correct"] = answer_ok(it["answer"], it["keywords"])
        it["answer_language"] = answer_language(it["answer"])
    else:
        model = server_model if pipeline.startswith("server") else pipeline.split(":", 1)[1]
        if pipeline.startswith("server") and pipeline != "server_direct":
            tr = post(CHAT, {"text": it["text"], "language": "uz", "dual_input": False})["english_input"]
            it["english_input"] = tr
            user = DUAL_TEMPLATE.format(original=it["text"], translation=tr) if pipeline == "server_dual" else tr
        else:
            user = it["text"]          # direct and hybrid: the model reads the Uzbek command itself
        it["restated"] = ollama(model, RESTATE_SYSTEM, user, 0, 60)
        it["understood"] = has_keywords(it["restated"], COMMAND_KEYWORDS[it["id"]])
    it["latency"] = round(time.perf_counter() - t, 2)
    it["first_call"] = first; first = False
    results.append(it)
    flag = it.get("correct", it.get("understood"))
    print(f"{k:2}/{len(items)} {it['id']} {it['input']:5} {'OK ' if flag else 'BAD'} {it['latency']:6.2f}s | "
          f"{(it.get('answer') or it.get('restated') or '')[:90]}", flush=True)
    out.write_text(json.dumps({"pipeline": pipeline, "language": LANG, "server_model": server_model, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
