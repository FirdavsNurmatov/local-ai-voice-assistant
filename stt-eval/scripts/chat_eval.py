r"""Evaluate the current /api/chat (server.py on 8765) on the llm_compare question sets and compare it with a
stored llm_compare run.

usage: .venv-stt-eval\Scripts\python.exe stt-eval\scripts\chat_eval.py <name> [uz ru en]
Writes stt-eval\chat_eval\<name>_<lang>.json and prints a comparison with the baselines below
(same model gemma3:4b and pipeline, previous prompt and keep_alive "10m").
"""
import json, re, statistics as st, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[2]; D = R / "stt-eval" / "llm_compare"; OUT = R / "stt-eval" / "chat_eval"
BASELINE = {"uz": "gemma4b_hybrid", "ru": "gemma4b_hybrid_ru", "en": "gemma4b_server_en"}
name = sys.argv[1]; langs = sys.argv[2:] or ["uz", "ru", "en"]


def norm(s):
    return re.sub(r"[‘’'`ʻʼ´]", "'", s.lower().replace("ё", "е"))


def ok(answer, kws):
    a = norm(answer or "")
    for k in map(norm, kws):
        if k.startswith("="):
            if re.search(r"(?<![\w'])" + re.escape(k[1:]) + r"(?![\w'])", a): return True
        elif re.search(r"(?<![\w'])" + re.escape(k), a): return True
    return False


def post(payload):
    req = urllib.request.Request("http://127.0.0.1:8765/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def summarize(rows, lang):
    s = {"n": len(rows), "correct": sum(r["correct"] for r in rows)}
    for inp in ("clean", "stt"):
        sub = [r for r in rows if r["input"] == inp]
        if sub and lang == "uz":
            s[f"{inp}_correct"] = sum(r["correct"] for r in sub)
    lat = [r["latency"] for r in rows if not r.get("first_call")]
    s["latency_median"] = round(st.median(lat), 2); s["latency_mean"] = round(st.mean(lat), 2)
    s["latency_p95"] = round(sorted(lat)[min(len(lat) - 1, round(0.95 * (len(lat) - 1)))], 2)
    toks = [r["output_tokens"] for r in rows if r.get("output_tokens")]
    s["output_tokens_median"] = st.median(toks) if toks else None
    if lang != "en":
        en_ok = [ok(r["answer_english"], r["keywords_en"]) for r in rows if r.get("keywords_en")]
        if en_ok:
            s["english_answer_correct"] = sum(en_ok)
            s["lost_in_output_translation"] = sum(ok(r["answer_english"], r["keywords_en"]) and not r["correct"] for r in rows)
    return s


OUT.mkdir(parents=True, exist_ok=True)
report = {}
for lang in langs:
    qs = json.loads((D / f"questions_{lang}.json").read_text(encoding="utf-8"))
    items = []
    for q in qs:
        items.append((q, "clean", q["text"]))
        if lang == "uz" and q.get("stt_text"):
            items.append((q, "stt", q["stt_text"]))
    rows = []
    for k, (q, inp, text) in enumerate(items):
        t = time.perf_counter()
        j = post({"text": text, "language": lang})
        latency = time.perf_counter() - t
        rows.append({"id": q["id"], "input": inp, "text": text, "answer": j["answer"], "answer_english": j.get("answer_english"),
                     "keywords": q["answer_keywords"], "keywords_en": q.get("answer_keywords_en"),
                     "correct": ok(j["answer"], q["answer_keywords"]), "latency": round(latency, 2),
                     "timings": j.get("timings"), "output_tokens": (j.get("llm") or {}).get("output_tokens"),
                     "first_call": k == 0})
        print(f"{lang} {q['id']} {inp:5} {'OK ' if rows[-1]['correct'] else 'BAD'} {latency:5.2f}s | {j['answer'][:90]}", flush=True)
    summary = summarize(rows, lang)
    (OUT / f"{name}_{lang}.json").write_text(json.dumps({"name": name, "language": lang, "date": time.strftime("%Y-%m-%d %H:%M"),
                                                        "summary": summary, "results": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    base = json.loads((D / "runs" / f"{BASELINE[lang]}.json").read_text(encoding="utf-8"))["results"]
    bq = [{"id": x["id"], "input": x["input"], "answer": x["answer"], "answer_english": x.get("answer_english"),
           "keywords_en": next((q.get("answer_keywords_en") for q in qs if q["id"] == x["id"]), None),
           "correct": ok(x["answer"], next(q["answer_keywords"] for q in qs if q["id"] == x["id"])),
           "latency": x["latency"], "first_call": x.get("first_call"),
           "output_tokens": (x.get("llm") or {}).get("output_tokens")} for x in base if x["kind"] == "question"]
    report[lang] = {"baseline": summarize(bq, lang), "new": summary}
    print(lang, json.dumps(report[lang], ensure_ascii=False), flush=True)
(OUT / f"{name}_comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
