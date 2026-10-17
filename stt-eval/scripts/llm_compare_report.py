"""Summarises stt-eval/llm_compare/runs/*.json and commands/*.json into RESULTS.md and summary.json.
Answers are re-scored with the current keyword lists in questions_<lang>.json (spelling variants added
after the first runs), so all runs use the same scoring."""
import json, re, statistics as st
from pathlib import Path

R = Path(__file__).resolve().parents[2]; D = R / "stt-eval" / "llm_compare"
KW = {l: {q["id"]: q["answer_keywords"] for q in json.loads((D / f"questions_{l}.json").read_text(encoding="utf-8"))}
      for l in ("uz", "ru", "en")}
KW_EN = {q["id"]: q["answer_keywords_en"] for q in json.loads((D / "questions_uz.json").read_text(encoding="utf-8"))}
TARGET = {"uz": "uzbek-latin", "ru": "russian", "en": "english"}
PIPE = {"server": "madlad", "server_dual": "dual", "server_direct": "hybrid"}

def norm(s):
    return re.sub(r"[‘’'`ʻʼ´]", "'", s.lower().replace("ё", "е"))

def ok(answer, kws):
    a = norm(answer)
    for k in map(norm, kws):
        if k.startswith("="):
            if re.search(r"(?<![\w'])" + re.escape(k[1:]) + r"(?![\w'])", a): return True
        elif re.search(r"(?<![\w'])" + re.escape(k), a): return True
    return False

def p95(v):
    v = sorted(v); return v[min(len(v) - 1, round(0.95 * (len(v) - 1)))] if v else None

def model_tokens(x):
    """(output tokens, generation seconds) of the chat model call, if recorded"""
    llm = x.get("llm") or {}
    out = llm.get("output_tokens")
    gen = llm.get("generation_s")
    return out, gen

rows = []
for f in sorted((D / "runs").glob("*.json")):
    r = json.loads(f.read_text(encoding="utf-8")); lang = r.get("language", "uz")
    p = r["pipeline"]
    if p.startswith("direct-think:"): model, pipe = p.split(":", 1)[1] + " (thinking)", "direct"
    elif p.startswith("direct:"): model, pipe = p.split(":", 1)[1], "direct"
    else: model, pipe = r["server_model"], PIPE[p] if lang != "en" else "server"
    if f.stem.endswith("_dual_v1"): pipe = "dual (prompt v1)"
    q = [x for x in r["results"] if x["kind"] == "question"]
    row = {"run": f.stem, "lang": lang, "model": model, "pipeline": pipe, "n": len(q)}
    for inp in ("clean", "stt"):
        s = [x for x in q if x["input"] == inp]
        if s:
            row[f"{inp}_correct"] = sum(ok(x["answer"], KW[lang][x["id"]]) for x in s)
            row[f"{inp}_n"] = len(s)
    if lang == "en":
        # the stop-word heuristic used during the runs calls one-word answers ("Tashkent.") "other";
        # for English the meaningful check is only "no Cyrillic / non-empty"
        row["target_language"] = sum(bool(x["answer"].strip()) and not re.search(r"[Ѐ-ӿ]", x["answer"]) for x in q)
    else:
        row["target_language"] = sum(x["answer_language"] == TARGET[lang] for x in q)
    if lang == "uz" and any(x.get("answer_english") for x in q):
        # the model's own English answer (before MADLAD) and answers lost by the output translation
        en_ok = [ok(x["answer_english"] or "", KW_EN[x["id"]]) for x in q]
        fin_ok = [ok(x["answer"], KW[lang][x["id"]]) for x in q]
        row["english_answer_correct"] = sum(en_ok)
        row["lost_in_output_translation"] = sum(e and not f for e, f in zip(en_ok, fin_ok))
    lat = [x["latency"] for x in q if not x.get("first_call")]
    row["latency_median"] = round(st.median(lat), 2) if lat else None
    row["latency_p95"] = p95(lat)
    toks = [model_tokens(x)[0] for x in q if model_tokens(x)[0]]
    row["output_tokens_median"] = st.median(toks) if toks else None
    rate = [o / g for o, g in map(model_tokens, q) if o and g]
    row["gen_tok_s"] = round(st.median(rate), 1) if rate else None
    think = [(x.get("llm") or {}).get("thinking_chars") or 0 for x in q]
    row["thinking_chars_median"] = st.median(think) if any(think) else None
    tm = [x["timings"] for x in q if x.get("timings") and not x.get("first_call")]
    if tm:
        row["madlad_s_median"] = round(st.median(t["input_translation"] + t["output_translation"] for t in tm), 2)
        row["llm_s_median"] = round(st.median(t["qwen"] for t in tm), 2)
    rows.append(row)

cmds = []
for f in sorted((D / "commands").glob("*.json")) if (D / "commands").exists() else []:
    c = json.loads(f.read_text(encoding="utf-8")); res = c["results"]
    lat = [x["latency"] for x in res if not x.get("first_call")]
    cmds.append({"run": f.stem, "model": c["model"] + (" (thinking)" if c["think"] else ""), "mode": c["mode"],
                 "clean": sum(x["correct"] for x in res if x["input"] == "clean"),
                 "clean_n": sum(x["input"] == "clean" for x in res),
                 "stt": sum(x["correct"] for x in res if x["input"] == "stt"),
                 "stt_n": sum(x["input"] == "stt" for x in res),
                 "latency_median": round(st.median(lat), 2) if lat else None})

(D / "summary.json").write_text(json.dumps({"questions": rows, "commands": cmds}, ensure_ascii=False, indent=1), encoding="utf-8")

def fmt(v): return "–" if v is None else str(v)
md = ["# LLM pipeline comparison — results", "",
      "Generated by `stt-eval/scripts/llm_compare_report.py`. Correct = expected keyword in the final answer.",
      "Latency = end-to-end text→text time per request, first (model-loading) request excluded.", ""]
for lang, title in (("uz", "Uzbek"), ("ru", "Russian"), ("en", "English (performance baseline)")):
    lr = [r for r in rows if r["lang"] == lang]
    if not lr: continue
    stt = lang == "uz"
    md += [f"## {title} questions", "",
           "| Model | Pipeline | Clean correct | " + ("STT correct | " if stt else "") + "Answer in target language | "
           "Median s | p95 s | Median output tokens | Gen tok/s |",
           "|---|---|---|" + ("---|" if stt else "") + "---|---|---|---|---|"]
    for r in sorted(lr, key=lambda r: (-(r.get("clean_correct", 0) + r.get("stt_correct", 0)), r["latency_median"] or 0)):
        md.append(f"| {r['model']} | {r['pipeline']} | {r.get('clean_correct')}/{r.get('clean_n')} | "
                  + (f"{r.get('stt_correct')}/{r.get('stt_n')} | " if stt else "")
                  + f"{r['target_language']}/{r['n']} | {fmt(r['latency_median'])} | {fmt(r['latency_p95'])} | "
                  f"{fmt(r['output_tokens_median'])} | {fmt(r['gen_tok_s'])} |")
    md.append("")
    if lang == "uz":
        md += ["### Where the Uzbek answers are lost (pipelines that end with MADLAD)", "",
               "English answer correct = the model's own English answer (before the output translation) contains the "
               "expected English keyword; lost = English answer correct but the Uzbek answer after MADLAD is not.", "",
               "| Model | Pipeline | English answer correct | Lost in output translation | Final Uzbek correct | "
               "Median MADLAD s (in+out) | Median LLM s |", "|---|---|---|---|---|---|---|"]
        for r in sorted([r for r in lr if "english_answer_correct" in r], key=lambda r: -r["english_answer_correct"]):
            md.append(f"| {r['model']} | {r['pipeline']} | {r['english_answer_correct']}/{r['n']} | "
                      f"{r['lost_in_output_translation']} | {r.get('clean_correct', 0) + r.get('stt_correct', 0)}/{r['n']} | "
                      f"{fmt(r.get('madlad_s_median'))} | {fmt(r.get('llm_s_median'))} |")
        md.append("")
if cmds:
    md += ["## Robot commands (action label)", "",
           "| Model | Input given to the model | Clean | STT | Median s |", "|---|---|---|---|---|"]
    for c in sorted(cmds, key=lambda c: -(c["clean"] + c["stt"])):
        md.append(f"| {c['model']} | {c['mode']} | {c['clean']}/{c['clean_n']} | {c['stt']}/{c['stt_n']} | {fmt(c['latency_median'])} |")
    md.append("")
(D / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))
