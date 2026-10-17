"""Separate STT test instance (never touches port 8769 or the production process).

usage: python stt_test_instance.py <mode> [port=8779] [peak_file]
  baseline   production code (stt_server, imported unchanged) + production model -> reference behaviour
  navai-uz   prototype of the PROPOSED Uzbek path: NavAI CT2 model, no prompt, without_timestamps=True,
             no_repeat_ngram_size=4, no language detection when ?language=uz. Only for testing; it does not
             change stt_server.py. Requests for other languages are rejected with 400.
A background sampler writes the peak RSS / commit of this process to <peak_file> once per second.
"""
import json, os, sys, threading, time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
mode = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8779
assert port != 8769, "the test instance must not use the production port"
peak_file = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "stt-eval" / "integration" / f"peak_{mode}.json"

import psutil
if os.environ.get("STT_TEST_MODULE"):
    # e.g. STT_TEST_MODULE=stt_server.py.before_navai.bak -> the exact pre-integration code
    import importlib.util
    from importlib.machinery import SourceFileLoader
    _path = str(ROOT / os.environ["STT_TEST_MODULE"])
    _loader = SourceFileLoader("stt_server", _path)
    _spec = importlib.util.spec_from_loader("stt_server", _loader)
    stt_server = importlib.util.module_from_spec(_spec); sys.modules["stt_server"] = stt_server; _loader.exec_module(stt_server)
    print("using module", _path, flush=True)
else:
    import stt_server                               # production module, imported read-only

P = psutil.Process()
peak = {"mode": mode, "pid": os.getpid(), "rss_mb": 0, "commit_mb": 0, "samples": 0}
def sampler():
    while True:
        m = P.memory_info()
        peak["rss_mb"] = max(peak["rss_mb"], round(m.rss / 1e6)); peak["commit_mb"] = max(peak["commit_mb"], round(m.private / 1e6))
        peak["samples"] += 1
        peak["now_rss_mb"], peak["now_commit_mb"] = round(m.rss / 1e6), round(m.private / 1e6)
        peak["windows_peak_commit_mb"] = round(m.peak_pagefile / 1e6)
        if peak["samples"] % 20 == 0:
            peak_file.parent.mkdir(parents=True, exist_ok=True)
            peak_file.write_text(json.dumps(peak), encoding="utf-8")
        time.sleep(0.05)
threading.Thread(target=sampler, daemon=True).start()

if mode == "navai-uz":
    NAVAI = ROOT / "stt-models" / "navai-whisper-small-uzbek-ct2-int8"
    stt_server.MODEL_DIR = NAVAI
    stt_server.MODEL_NAME = "navai-whisper-small-uzbek"
    original = stt_server.transcribe

    def transcribe_uz(audio_bytes, forced_language):
        if forced_language != "uz":
            raise stt_server.ApiError(400, "test instance navai-uz: only ?language=uz is served")
        import io, numpy as np
        from faster_whisper import decode_audio
        started = time.perf_counter()
        try:
            audio = decode_audio(io.BytesIO(audio_bytes), sampling_rate=stt_server.SAMPLE_RATE)
        except Exception as exc:
            raise stt_server.ApiError(422, f"Audio faylni o'qib bo'lmadi ({type(exc).__name__}). WebM/Opus, WAV, OGG yoki MP3 yuboring.")
        duration = len(audio) / stt_server.SAMPLE_RATE
        if duration < stt_server.MIN_SECONDS:
            raise stt_server.ApiError(422, f"Audio bo'sh yoki juda qisqa ({duration:.2f} s)")
        if duration > stt_server.MAX_SECONDS:
            raise stt_server.ApiError(413, f"Audio {stt_server.MAX_SECONDS} soniyadan oshmasin ({duration:.0f} s)")
        if float(np.abs(audio).max()) < 1e-3:
            raise stt_server.ApiError(422, "Audio jim: ovoz yozilmagan")
        segments, info = stt_server.ENGINE["model"].transcribe(
            audio, language="uz", task="transcribe", beam_size=5, vad_filter=True,
            condition_on_previous_text=False, without_timestamps=True, no_repeat_ngram_size=4)
        text = " ".join(s.text.strip() for s in segments).strip()
        if not text:
            raise stt_server.ApiError(422, "Nutq aniqlanmadi (faqat sukunat yoki shovqin)")
        return {"ok": True, "text": text, "language": "uz", "language_probability": None, "language_forced": True,
                "detected_language": None, "detected_language_probability": None, "language_probabilities": {},
                "duration": round(duration, 2), "processing_time": round(time.perf_counter() - started, 2),
                "model": stt_server.MODEL_NAME}
    stt_server.transcribe = transcribe_uz
elif mode != "baseline":
    raise SystemExit(f"unknown mode {mode}")

server = ThreadingHTTPServer(("127.0.0.1", port), stt_server.Handler)
print(f"STT test instance mode={mode} http://127.0.0.1:{port} model_dir={stt_server.MODEL_DIR}", flush=True)
threading.Thread(target=stt_server.load_model, daemon=True).start()
server.serve_forever()
