r"""End-to-end voice test through server.py (8765): audio -> /api/transcribe -> /api/chat -> /api/tts.

usage (services 8765, 8766, 8769 and optionally 8770 running):
  .venv-stt-eval\Scripts\python.exe stt-eval\scripts\e2e_voice_test.py [male]
Uses the Uzbek question recordings in stt-eval\llm_compare\audio (TTS audio of questions_uz.json).
Writes stt-eval\e2e\results[_male].json (+ answer WAVs, not tracked by git).
"""
import io, json, statistics, sys, time, urllib.request, wave
from pathlib import Path

R = Path(__file__).resolve().parents[2]
D = R / "stt-eval" / "llm_compare"
OUT = R / "stt-eval" / "e2e"
BASE = "http://127.0.0.1:8765"
VOICE = "male" if "male" in sys.argv[1:] else "female"
IDS = ["q01", "q02", "q05", "q06", "q11", "q22"] if VOICE == "female" else ["q01", "q02", "q11"]
questions = {q["id"]: q for q in json.loads((D / "questions_uz.json").read_text(encoding="utf-8"))}


def call(path, body, content_type):
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": content_type})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = r.read()
    return data, time.perf_counter() - t


OUT.mkdir(parents=True, exist_ok=True)
rows = []
for qid in IDS:
    audio = (D / "audio" / f"{qid}.wav").read_bytes()
    stt, t_stt = call("/api/transcribe?language=uz", audio, "audio/wav")
    stt = json.loads(stt)
    chat, t_chat = call("/api/chat", json.dumps({"text": stt["text"], "language": stt["language"]}).encode(), "application/json")
    chat = json.loads(chat)
    wav, t_tts = call("/api/tts", json.dumps({"text": chat["answer"], "voice": VOICE}).encode(), "application/json")
    with wave.open(io.BytesIO(wav)) as w:
        answer_audio_s = w.getnframes() / w.getframerate()
    (OUT / f"{VOICE}_{qid}.wav").write_bytes(wav)
    kw = [k.lower() for k in questions[qid]["answer_keywords"]]
    rows.append({"id": qid, "question": questions[qid]["text"], "transcript": stt["text"], "stt_model": stt.get("model"),
                 "answer": chat["answer"], "answer_english": chat.get("answer_english"),
                 "correct": any(k.lstrip("=") in chat["answer"].lower().replace("ʻ", "'") for k in kw),
                 "stt_s": round(t_stt, 2), "chat_s": round(t_chat, 2), "chat_timings": chat.get("timings"),
                 "tts_s": round(t_tts, 2), "answer_audio_s": round(answer_audio_s, 2),
                 "total_s": round(t_stt + t_chat + t_tts, 2)})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
summary = {k: round(statistics.median(r[k] for r in rows), 2) for k in ("stt_s", "chat_s", "tts_s", "total_s")}
summary.update(voice=VOICE, n=len(rows), correct=sum(r["correct"] for r in rows), date=time.strftime("%Y-%m-%d"),
               mean_total_s=round(statistics.mean(r["total_s"] for r in rows), 2))
(OUT / f"results{'_male' if VOICE == 'male' else ''}.json").write_text(
    json.dumps({"summary": summary, "requests": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
