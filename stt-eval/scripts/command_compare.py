"""Robot command understanding: the model maps each Uzbek command to one action label.

usage: python command_compare.py <model> <mode> <out.json> [--think]
modes:
  madlad    model sees only the MADLAD English translation (production madlad pipeline)
  dual      model sees the original Uzbek text and the MADLAD translation (dual_input)
  original  model reads the Uzbek text itself (hybrid and direct pipelines)
Inputs: 12 clean commands + 11 NavAI STT transcripts of the TTS audio. The MADLAD translations are the ones
stored by the qwen1.7b_madlad run (translation does not depend on the chat model).
The free-text restatement check in llm_compare.py was not usable for the original-text modes: the models
echoed the Uzbek text or asked for the question, so this label task replaces it for all modes.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[2]; D = R / "stt-eval" / "llm_compare"
model, mode, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
THINK = "--think" in sys.argv
LABELS = ["stop", "turn_left", "turn_right", "forward", "backward", "slow_down", "speed_up",
          "go_to_library", "open_door", "yes", "no", "unknown"]
EXPECTED = {"cmd_01": "stop", "cmd_02": "turn_left", "cmd_03": "turn_right", "cmd_04": "forward",
            "cmd_05": "backward", "cmd_06": "slow_down", "cmd_07": "speed_up", "cmd_08": "go_to_library",
            "cmd_09": "open_door", "cmd_10": "yes", "cmd_11": "no", "cmd_12": "stop"}
SOURCE = {"madlad": "an English machine translation of a command spoken in Uzbek (the translation may be wrong)",
          "dual": "a command spoken in Uzbek, given as the original text and as an English machine translation",
          "original": "a command spoken in Uzbek"}[mode]
SYSTEM = (f"You control a small robot. The user message is {SOURCE}; it comes from speech recognition and may "
          "contain recognition errors. Reply with exactly one label from this list and nothing else: "
          + ", ".join(LABELS) + ". Use unknown if the command is unclear.")
DUAL_TEMPLATE = ("Original message in Uzbek (may come from speech recognition; may contain recognition or spelling errors):\n"
                 "{original}\n\nMachine translation into English (may contain translation errors):\n{translation}\n\n"
                 "If the translation and the original disagree, trust the meaning of the original.")

madlad = json.load(open(D / "runs" / "qwen1.7b_madlad.json", encoding="utf-8"))["results"]
items = [{"id": x["id"], "input": x["input"], "text": x["text"], "english_input": x["english_input"]}
         for x in madlad if x["kind"] == "command"]

def post(url, payload, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

results, first = [], True
for it in items:
    user = {"madlad": it["english_input"], "original": it["text"],
            "dual": DUAL_TEMPLATE.format(original=it["text"], translation=it["english_input"])}[mode]
    payload = {"model": model, "stream": False, "keep_alive": "30m",
               "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
               "options": {"temperature": 0, "num_ctx": 4096 if THINK else 2048, "num_predict": 2048 if THINK else 12}}
    if model.startswith("qwen3"):
        payload["think"] = THINK
    t = time.perf_counter()
    j = post("http://127.0.0.1:11434/api/chat", payload)
    raw = j["message"]["content"].strip()
    found = [l for l in LABELS if re.search(r"(?<![a-z_])" + l + r"(?![a-z_])", raw.lower())]
    label = found[0] if len(found) == 1 else ("invalid" if not found else "ambiguous")
    it.update(raw=raw, label=label, expected=EXPECTED[it["id"]], correct=label == EXPECTED[it["id"]],
              latency=round(time.perf_counter() - t, 2), first_call=first,
              llm={"prompt_tokens": j.get("prompt_eval_count"), "output_tokens": j.get("eval_count"),
                   "thinking_chars": len(j["message"].get("thinking") or "")})
    first = False
    results.append(it)
    print(f"{it['id']} {it['input']:5} {'OK ' if it['correct'] else 'BAD'} {label:14} {it['latency']:6.2f}s | {it['text']!r}", flush=True)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"model": model, "mode": mode, "think": THINK, "system": SYSTEM, "results": results},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{model} {mode}: {sum(r['correct'] for r in results)}/{len(results)} correct")
