r"""Russian/English TTS: female vs male voices on the running Kokoro (8768) and Piper (8767) services.

usage (services running): .venv-stt-eval\Scripts\python.exe stt-eval\scripts\tts_ruen_benchmark.py
Writes stt-eval\tts_ruen\results.json (+ WAVs, not tracked by git). One warm-up request per engine/voice is not counted.
"""
import io, json, statistics, time, urllib.request, wave
from pathlib import Path

R = Path(__file__).resolve().parents[2]
OUT = R / "stt-eval" / "tts_ruen"
TEXTS = {
    "ru": ["Здравствуйте! Чем я могу вам помочь?",
           "Столица Узбекистана — город Ташкент.",
           "В неделе семь дней: понедельник, вторник, среда, четверг, пятница, суббота и воскресенье."],
    "en": ["Hello! How can I help you today?",
           "The capital of Uzbekistan is Tashkent.",
           "There are seven days in a week. Would you like to know something else?"],
}
ENGINES = {"kokoro": "http://127.0.0.1:8768/api/tts", "piper": "http://127.0.0.1:8767/api/tts"}
# Piper sends no X-TTS-Voice header; its voices per piper_tts_server.py
PIPER_VOICES = {("ru", "female"): "irina", ("ru", "male"): "dmitri", ("en", "female"): "lessac", ("en", "male"): "ryan"}


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read(), r.headers.get("X-TTS-Voice")


OUT.mkdir(parents=True, exist_ok=True)
rows = []
for engine, url in ENGINES.items():
    for lang, texts in TEXTS.items():
        for gender in ("female", "male"):
            post(url, {"text": "Test.", "language": lang, "voice": gender})       # warm-up
            for i, text in enumerate(texts):
                t = time.perf_counter()
                data, voice = post(url, {"text": text, "language": lang, "voice": gender})
                elapsed = time.perf_counter() - t
                with wave.open(io.BytesIO(data)) as w:
                    audio_s = w.getnframes() / w.getframerate(); sr = w.getframerate()
                (OUT / f"{engine}_{lang}_{gender}_{i}.wav").write_bytes(data)
                voice = voice or PIPER_VOICES[(lang, gender)]
                rows.append({"engine": engine, "language": lang, "gender": gender, "voice": voice, "text": text,
                             "audio_s": round(audio_s, 2), "generation_s": round(elapsed, 2),
                             "real_time_factor": round(elapsed / audio_s, 2), "sample_rate": sr})
                print(rows[-1], flush=True)
summary = {}
for r in rows:
    summary.setdefault(f"{r['engine']}/{r['language']}/{r['gender']}", []).append(r)
summary = {k: {"voice": v[0]["voice"], "median_generation_s": statistics.median(x["generation_s"] for x in v),
               "median_real_time_factor": statistics.median(x["real_time_factor"] for x in v)} for k, v in summary.items()}
(OUT / "results.json").write_text(json.dumps({"date": time.strftime("%Y-%m-%d"), "summary": summary, "requests": rows},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
