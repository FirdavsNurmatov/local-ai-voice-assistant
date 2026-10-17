"""Local speech-to-text server: Faster-Whisper `small`, CPU, int8.

Run with the isolated environment:
    .venv-stt\\Scripts\\python.exe stt_server.py

API:
    GET  /api/health
    POST /api/transcribe[?language=auto|uz|ru|en]
         body: raw audio bytes (WebM/Opus, WAV, OGG, MP3, ... anything FFmpeg/PyAV decodes)
               or multipart/form-data with one file part
         -> {"ok", "text", "language", "language_probability", "duration",
             "processing_time", "model", ...}
"""
import email
import email.policy
import io
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# The model is loaded from a local folder; never reach for the network at runtime.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = "small"
MODEL_DIR = BASE_DIR / "stt-models" / "faster-whisper-small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
CPU_THREADS = int(os.environ.get("STT_THREADS", "4"))

HOST = "127.0.0.1"
PORT = 8769
SAMPLE_RATE = 16000
MAX_BODY = 25 * 1024 * 1024     # bytes of uploaded audio
MAX_SECONDS = 180               # longest accepted recording
MIN_SECONDS = 0.3               # anything shorter is treated as empty
MAX_WAITING = 2                 # requests allowed to queue behind the running one
SUPPORTED = ("uz", "ru", "en")  # languages the chat pipeline can handle
# Whisper `small` recognises Russian and English with high confidence but almost
# never labels Uzbek as "uz" (measured: az/hy/tr instead, uz probability < 0.05).
# So: a confident ru/en wins, everything else is treated as Uzbek.
LANGUAGE_THRESHOLD = 0.5
FALLBACK_LANGUAGE = "uz"
# Biases Uzbek output towards Latin-script Uzbek spelling (measured WER 1.00 -> 0.56
# and 0.93 -> 0.79 on two reference clips; Uzbek accuracy stays low, see docs/STT.md).
INITIAL_PROMPTS = {
    "uz": "Assalomu alaykum! Bugun ob-havo yaxshi. Men o'zbek tilida gapiryapman, menga yordam bering.",
}
# Per-language decoding overrides. For Uzbek the model's own confidence is so low
# that Whisper's no-speech check discards real speech (measured no_speech_prob 0.61-0.76)
# and the low-log-probability check triggers slow temperature retries (11-40 s for a
# 3 s clip). Silence/noise is still rejected by the VAD filter, which runs for every language.
LANGUAGE_OPTIONS = {
    "uz": {"no_speech_threshold": None, "log_prob_threshold": None, "temperature": (0.0, 0.4)},
}
REQUIRED_FREE_MB = 1200         # free commit needed before loading (see docs/STT.md)
SKIP_MEMCHECK = os.environ.get("STT_SKIP_MEMCHECK") == "1"

# --- Uzbek-specialised model (NavAI), see docs/STT_EVALUATION.md -------------------
# Used ONLY for Uzbek: when ?language=uz, or in auto mode when the base model is clearly
# not hearing Russian/English. Russian and English always stay on the base model.
# STT_UZ_MODEL=off restores the previous behaviour exactly (base model for everything).
UZ_MODEL_ENABLED = os.environ.get("STT_UZ_MODEL", "navai").lower() != "off"
UZ_MODEL_NAME = "navai-whisper-small-uzbek"
UZ_MODEL_DIR = BASE_DIR / "stt-models" / "navai-whisper-small-uzbek-ct2-int8"
UZ_MODEL_SHA256 = "99e30c6de495b69ea1d9109edba240081d60c3875a9d9ee6ffed5eb11ba75d23"   # model.bin
# Auto mode hands audio to NavAI only if BOTH p(ru) and p(en) are below this value
# (NavAI turns Russian/English speech into Uzbek-looking text). Between this value and
# LANGUAGE_THRESHOLD the previous base-model Uzbek path is kept.
UZ_AUTO_MAX_RUEN = float(os.environ.get("STT_UZ_AUTO_MAX_RUEN", "0.2"))
UZ_PRELOAD = os.environ.get("STT_UZ_PRELOAD") == "1"   # default: load on the first Uzbek request
# Memory (measured 2026-10-16, CPU int8): base model alone ~2.7 GB commit, both models ~5.1 GB;
# unloading a model returns its memory and reloading takes 0.4-1.2 s.
#   auto: keep both if at least UZ_REQUIRED_FREE_MB of commit is free, otherwise hold only
#         the model that is needed and swap (so STT never needs more memory than before)
#   swap: always hold only one model;  both: always keep both (no swapping)
UZ_MEMORY_POLICY = os.environ.get("STT_UZ_MEMORY", "auto").lower()
UZ_REQUIRED_FREE_MB = int(os.environ.get("STT_UZ_REQUIRED_FREE_MB", "3000"))   # free commit needed to load NavAI
# Benchmarked decoding for NavAI: no prompt, no timestamp tokens, repetition guard.
UZ_OPTIONS = {"beam_size": 5, "vad_filter": True, "condition_on_previous_text": False,
              "without_timestamps": True, "no_repeat_ngram_size": 4}
UZ_STATE = {"loaded": False, "error": None, "load_seconds": None, "requests": 0, "fallbacks": 0, "swaps": 0}
UZ_LOAD_LOCK = threading.Lock()

STATE = {"ready": False, "loading": True, "error": None, "load_seconds": None}
ENGINE = {}
INFER_LOCK = threading.Lock()   # one transcription at a time keeps CPU and memory bounded
WAITING = threading.Semaphore(MAX_WAITING + 1)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def free_commit_mb():
    """Commit still available to this process (Windows); None elsewhere."""
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in (
                    "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                    "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return int(status.ullAvailPageFile / 1e6)
    except Exception:
        return None


def memory_mb():
    try:
        import psutil
        info = psutil.Process().memory_info()
        return {"rss": round(info.rss / 1e6), "commit": round(getattr(info, "private", info.vms) / 1e6)}
    except Exception:
        return None


def load_model():
    started = time.perf_counter()
    try:
        if not (MODEL_DIR / "model.bin").exists():
            raise FileNotFoundError(f"{MODEL_DIR}\\model.bin topilmadi")
        free = free_commit_mb()
        if not SKIP_MEMCHECK and free is not None and free < REQUIRED_FREE_MB:
            raise MemoryError(f"xotira yetarli emas: bo'sh commit {free} MB, "
                              f"kerak {REQUIRED_FREE_MB} MB")
        from faster_whisper import WhisperModel
        ENGINE["model"] = WhisperModel(
            str(MODEL_DIR), device=DEVICE, compute_type=COMPUTE_TYPE,
            cpu_threads=CPU_THREADS, num_workers=1, local_files_only=True)
        STATE["ready"] = True
        print(f"[STT] model tayyor: {MODEL_NAME} ({DEVICE}, {COMPUTE_TYPE}) "
              f"{time.perf_counter() - started:.1f}s  xotira={memory_mb()}", flush=True)
    except Exception as exc:
        STATE["error"] = f"{type(exc).__name__}: {exc}"
        print(f"[STT ERROR] model yuklanmadi: {STATE['error']}", flush=True)
        if not isinstance(exc, (MemoryError, FileNotFoundError)):
            traceback.print_exc()
    STATE["load_seconds"] = round(time.perf_counter() - started, 2)
    STATE["loading"] = False
    if UZ_MODEL_ENABLED and UZ_PRELOAD and STATE["ready"]:
        uz_model()


def _room_for_second_model():
    free = free_commit_mb()
    return SKIP_MEMCHECK or free is None or free >= UZ_REQUIRED_FREE_MB


def _unload(key):
    import gc
    ENGINE[key] = None
    gc.collect()


def base_model():
    """The multilingual base model; reloads it if it was swapped out for NavAI."""
    if ENGINE.get("model") is not None:
        return ENGINE["model"]
    with UZ_LOAD_LOCK:
        if ENGINE.get("model") is None:
            if UZ_STATE["loaded"] and UZ_MEMORY_POLICY != "both" and (
                    UZ_MEMORY_POLICY == "swap" or not _room_for_second_model()):
                _unload("uz"); UZ_STATE["loaded"] = False
            from faster_whisper import WhisperModel
            started = time.perf_counter()
            ENGINE["model"] = WhisperModel(
                str(MODEL_DIR), device=DEVICE, compute_type=COMPUTE_TYPE,
                cpu_threads=CPU_THREADS, num_workers=1, local_files_only=True)
            UZ_STATE["swaps"] += 1
            print(f"[STT] asosiy model qayta yuklandi {time.perf_counter() - started:.1f}s xotira={memory_mb()}", flush=True)
    return ENGINE["model"]


def uz_model():
    """Return the loaded NavAI model, loading it on first use; None if unavailable.

    Never raises: any problem (disabled, missing file, wrong checksum, not enough free
    commit, load error) is recorded in UZ_STATE["error"] and the caller falls back to the
    base model, i.e. to the behaviour before NavAI was added.
    """
    if not UZ_MODEL_ENABLED:
        return None
    if UZ_STATE["loaded"]:
        return ENGINE["uz"]
    if time.time() < UZ_STATE.get("retry_after", 0):
        return None                         # a recent load attempt failed; do not retry on every request
    with UZ_LOAD_LOCK:
        if UZ_STATE["loaded"]:
            return ENGINE["uz"]
        started = time.perf_counter()
        try:
            model_bin = UZ_MODEL_DIR / "model.bin"
            if not model_bin.exists():
                raise FileNotFoundError(f"{model_bin} topilmadi")
            if not UZ_STATE.get("sha_ok"):
                import hashlib
                digest = hashlib.sha256(model_bin.read_bytes()).hexdigest()
                if digest != UZ_MODEL_SHA256:
                    raise ValueError(f"model.bin SHA256 mos emas: {digest}")
                UZ_STATE["sha_ok"] = True
            if ENGINE.get("model") is not None and UZ_MEMORY_POLICY != "both" and (
                    UZ_MEMORY_POLICY == "swap" or not _room_for_second_model()):
                free = free_commit_mb()
                # unloading the base model returns ~2.3-2.7 GB of commit (measured); if even that
                # cannot reach the requirement, keep the base model and fail fast
                if not SKIP_MEMCHECK and free is not None and free + 2300 < UZ_REQUIRED_FREE_MB:
                    raise MemoryError(f"xotira yetarli emas: bo'sh commit {free} MB (+~2300 MB swap), "
                                      f"kerak {UZ_REQUIRED_FREE_MB} MB")
                _unload("model")            # swap: free the base model first (reloaded when needed)
                UZ_STATE["swaps"] += 1
            free = free_commit_mb()
            if not SKIP_MEMCHECK and free is not None and free < UZ_REQUIRED_FREE_MB:
                raise MemoryError(f"xotira yetarli emas: bo'sh commit {free} MB, kerak {UZ_REQUIRED_FREE_MB} MB")
            from faster_whisper import WhisperModel
            ENGINE["uz"] = WhisperModel(
                str(UZ_MODEL_DIR), device=DEVICE, compute_type=COMPUTE_TYPE,
                cpu_threads=CPU_THREADS, num_workers=1, local_files_only=True)
            UZ_STATE.update(loaded=True, error=None)
            print(f"[STT] o'zbekcha model tayyor: {UZ_MODEL_NAME} "
                  f"{time.perf_counter() - started:.1f}s  xotira={memory_mb()}", flush=True)
        except Exception as exc:
            UZ_STATE["error"] = f"{type(exc).__name__}: {exc}"
            UZ_STATE["retry_after"] = time.time() + 60
            print(f"[STT ERROR] o'zbekcha model yuklanmadi, asosiy model ishlatiladi: {UZ_STATE['error']}", flush=True)
        UZ_STATE["load_seconds"] = round(time.perf_counter() - started, 2)
        return ENGINE.get("uz") if UZ_STATE["loaded"] else None


def transcribe_with_uz_model(model, audio):
    segments, _ = model.transcribe(audio, language="uz", task="transcribe", **UZ_OPTIONS)
    return " ".join(segment.text.strip() for segment in segments).strip()


def extract_audio(headers, body):
    """Return the audio bytes from a raw or multipart/form-data upload."""
    content_type = headers.get("Content-Type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        return body
    message = email.message_from_bytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body,
        policy=email.policy.HTTP)
    for part in message.iter_parts():
        payload = part.get_payload(decode=True)
        if payload and (part.get_filename() or part.get_content_maintype() in ("audio", "video", "application")):
            return payload
    raise ApiError(400, "multipart so'rovda audio fayl topilmadi")


def transcribe(audio_bytes, forced_language):
    import numpy as np
    from faster_whisper import decode_audio
    started = time.perf_counter()
    try:
        audio = decode_audio(io.BytesIO(audio_bytes), sampling_rate=SAMPLE_RATE)
    except Exception as exc:
        print(f"[STT] decode xatosi: {type(exc).__name__}: {exc}", flush=True)
        raise ApiError(422, f"Audio faylni o'qib bo'lmadi ({type(exc).__name__}). "
                            "WebM/Opus, WAV, OGG yoki MP3 yuboring.")
    duration = len(audio) / SAMPLE_RATE
    if duration < MIN_SECONDS:
        raise ApiError(422, f"Audio bo'sh yoki juda qisqa ({duration:.2f} s)")
    if duration > MAX_SECONDS:
        raise ApiError(413, f"Audio {MAX_SECONDS} soniyadan oshmasin ({duration:.0f} s)")
    if float(np.abs(audio).max()) < 1e-3:
        raise ApiError(422, "Audio jim: ovoz yozilmagan")

    # ?language=uz: straight to the Uzbek model, no language detection (saves ~1.7 s).
    if forced_language == "uz":
        uz = uz_model()
        if uz is not None:
            UZ_STATE["requests"] += 1
            text = transcribe_with_uz_model(uz, audio)
            if not text:
                raise ApiError(422, "Nutq aniqlanmadi (faqat sukunat yoki shovqin)")
            return {
                "ok": True, "text": text, "language": "uz", "language_probability": None,
                "language_forced": True, "detected_language": None,
                "detected_language_probability": None, "language_probabilities": {},
                "duration": round(duration, 2),
                "processing_time": round(time.perf_counter() - started, 2),
                "model": UZ_MODEL_NAME,
            }
        if UZ_MODEL_ENABLED:
            UZ_STATE["fallbacks"] += 1      # NavAI unavailable: previous behaviour below

    # Whisper's own language detection over the first 30 s, then mapped onto the
    # three languages the chat pipeline supports (see LANGUAGE_THRESHOLD above).
    model = base_model()
    detected, detected_prob, all_probs = model.detect_language(audio)
    probs = dict(all_probs)
    supported_probs = {lang: round(float(probs.get(lang, 0.0)), 4) for lang in SUPPORTED}
    if forced_language:
        language = forced_language
    else:
        language = max(("ru", "en"), key=lambda lang: supported_probs[lang])
        if supported_probs[language] < LANGUAGE_THRESHOLD:
            language = FALLBACK_LANGUAGE
    language_prob = supported_probs[language]

    used_model, text = MODEL_NAME, None
    if (not forced_language and language == "uz"
            and max(supported_probs["ru"], supported_probs["en"]) < UZ_AUTO_MAX_RUEN):
        model = None                        # drop our reference so a swap really frees the base model
        uz = uz_model()
        if uz is not None:
            UZ_STATE["requests"] += 1
            used_model, text = UZ_MODEL_NAME, transcribe_with_uz_model(uz, audio)
        elif UZ_MODEL_ENABLED:
            UZ_STATE["fallbacks"] += 1
    if text is None:
        model = base_model()                # may have been swapped out while NavAI loaded
        segments, info = model.transcribe(
            audio, language=language, task="transcribe", beam_size=5,
            vad_filter=True, condition_on_previous_text=False,
            initial_prompt=INITIAL_PROMPTS.get(language), **LANGUAGE_OPTIONS.get(language, {}))
        text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise ApiError(422, "Nutq aniqlanmadi (faqat sukunat yoki shovqin)")
    return {
        "ok": True,
        "text": text,
        "language": language,
        "language_probability": language_prob,
        "language_forced": bool(forced_language),
        "detected_language": detected,
        "detected_language_probability": round(float(detected_prob), 4),
        "language_probabilities": supported_probs,
        "duration": round(duration, 2),
        "processing_time": round(time.perf_counter() - started, 2),
        "model": used_model,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalSTT/1.0"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(204, {})

    def do_GET(self):
        if urlparse(self.path).path != "/api/health":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        self.send_json(200, {
            "ok": STATE["ready"],
            "service": "Local Faster-Whisper STT",
            "ready": STATE["ready"],
            "loading": STATE["loading"],
            "error": STATE["error"],
            "model": MODEL_NAME,
            "model_path": str(MODEL_DIR),
            "device": DEVICE,
            "compute_type": COMPUTE_TYPE,
            "cpu_threads": CPU_THREADS,
            "language_detection": f"auto (Whisper): ru/en if probability >= {LANGUAGE_THRESHOLD}, "
                                  f"otherwise {FALLBACK_LANGUAGE}; override with ?language=",
            "supported_languages": list(SUPPORTED),
            "load_seconds": STATE["load_seconds"],
            "memory_mb": memory_mb(),
            "free_commit_mb": free_commit_mb(),
            "uz_model": {
                "enabled": UZ_MODEL_ENABLED,
                "model": UZ_MODEL_NAME,
                "model_path": str(UZ_MODEL_DIR),
                "loaded": UZ_STATE["loaded"],
                "base_model_loaded": ENGINE.get("model") is not None,
                "load_policy": "preload" if UZ_PRELOAD else "on first Uzbek request",
                "memory_policy": UZ_MEMORY_POLICY,
                "model_swaps": UZ_STATE["swaps"],
                "routing": f"?language=uz always; auto only if p(ru) and p(en) < {UZ_AUTO_MAX_RUEN}; never ru/en",
                "decoding": {k: v for k, v in UZ_OPTIONS.items()},
                "error": UZ_STATE["error"],
                "load_seconds": UZ_STATE["load_seconds"],
                "requests": UZ_STATE["requests"],
                "fallbacks_to_base_model": UZ_STATE["fallbacks"],
            },
        })

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/transcribe":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        try:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ApiError(400, "So'rov hajmi noto'g'ri")
            if size <= 0:
                raise ApiError(400, "Audio yuborilmadi (bo'sh so'rov)")
            if size > MAX_BODY:
                raise ApiError(413, "Audio fayl juda katta (25 MB dan oshmasin)")
            body = self.rfile.read(size)
            language = (parse_qs(url.query).get("language", ["auto"])[0] or "auto").lower()
            if language not in SUPPORTED + ("auto",):
                raise ApiError(400, "language: auto, uz, ru yoki en bo'lishi kerak")
            if not STATE["ready"]:
                detail = STATE["error"] or "model hali yuklanmoqda"
                raise ApiError(503, f"STT modeli tayyor emas: {detail}")
            audio_bytes = extract_audio(self.headers, body)
            if not audio_bytes:
                raise ApiError(400, "Audio yuborilmadi (bo'sh fayl)")

            if not WAITING.acquire(blocking=False):
                raise ApiError(503, "STT band, birozdan keyin urinib ko'ring")
            try:
                with INFER_LOCK:
                    result = transcribe(audio_bytes, None if language == "auto" else language)
            finally:
                WAITING.release()
            print(f"[STT] {result['duration']}s audio -> {result['language']} "
                  f"({result['language_probability']}), {len(result['text'])} belgi, "
                  f"{result['processing_time']}s", flush=True)
            self.send_json(200, result)
        except ApiError as exc:
            self.send_json(exc.status, {"ok": False, "error": str(exc)})
        except (BrokenPipeError, ConnectionError):
            pass
        except Exception as exc:
            print("[STT ERROR] transcribe:", flush=True)
            traceback.print_exc()
            self.send_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):
        print("[STT HTTP] " + (fmt % args), flush=True)


if __name__ == "__main__":
    # Bind first so a port clash fails fast; load once, in the background,
    # so /api/health answers while the model is loading.
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local STT: http://{HOST}:{PORT}  model={MODEL_NAME} {DEVICE}/{COMPUTE_TYPE}", flush=True)
    threading.Thread(target=load_model, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
