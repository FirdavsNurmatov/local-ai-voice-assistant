"""Local Kokoro TTS server: Russian (Kokoro-RU, masha / male dima) + English (Kokoro-82M, af_heart / male am_michael).

Run with the isolated environment:
    .venv-kokoro\\Scripts\\python.exe kokoro_tts_server.py

API (same shape as piper_tts_server.py):
    GET  /api/health
    POST /api/tts   {"text": "...", "language": "ru"|"en", "speed": 1.0 (optional),
                     "voice": "female" (default) | "male"}
                    -> audio/wav (24 kHz, mono, PCM16)
"""
import os
import subprocess
import sys

# ru_g2p.py and its dependencies read UTF-8 files with the default encoding,
# which fails on Windows locales such as cp1251. Restart once in UTF-8 mode.
if not sys.flags.utf8_mode:
    env = dict(os.environ, PYTHONUTF8="1")
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv], env=env))

# Everything is loaded from local files; never reach for the network at runtime.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import hashlib
import io
import json
import re
import threading
import time
import traceback
import warnings
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "kokoro-models"
RU_DIR = MODELS_DIR / "kokoro-ru"
EN_DIR = MODELS_DIR / "kokoro-82m"

HOST = "127.0.0.1"
PORT = 8768
SAMPLE_RATE = 24000
MAX_TEXT = 2000
MAX_BODY = 20000
MAX_PHONEMES = 510          # Kokoro context limit (voicepack has 510 rows)
MAX_WAITING = 4             # requests allowed to queue behind the running one
SENTENCE_GAP = 0.12         # seconds of silence between Russian sentences

VOICES = {
    "ru": {
        "voice": "masha",
        "model": "zaakirio/kokoro-ru",
        "checkpoint": RU_DIR / "kokoro-ru-v2-base.pth",
        "config": RU_DIR / "config.json",
        "voicepack": RU_DIR / "voices" / "masha.pt",
        "voicepack_sha256": "464d64ae793647c3b3f9d1f08ce5b11c641a61799f0bca65f111e6aad5d0a362",
        # "voice": "male" in the request (added 2026-10-17, same commit of zaakirio/kokoro-ru)
        "male_voice": "dima",
        "male_voicepack": RU_DIR / "voices" / "dima.pt",
        "male_voicepack_sha256": "80d4d216b5906c232ede48f2c07ab3aee0785e34d1df6ec6dc8cf44767d74c69",
    },
    "en": {
        "voice": "af_heart",
        "model": "hexgrad/Kokoro-82M",
        "checkpoint": EN_DIR / "kokoro-v1_0.pth",
        "config": EN_DIR / "config.json",
        "voicepack": EN_DIR / "voices" / "af_heart.pt",
        "voicepack_sha256": "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff",
        # "voice": "male" (added 2026-10-17, hexgrad/Kokoro-82M @ f3ff3571)
        "male_voice": "am_michael",
        "male_voicepack": EN_DIR / "voices" / "am_michael.pt",
        "male_voicepack_sha256": "9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37",
    },
}

# Free commit (RAM + pagefile) each language needs before it may load, in MB.
# Measured on Windows/CPU: English ~1.7 GB peak; Russian adds ~3.5 GB (RUAccent
# stress models + dictionary are the bulk). Loading without that headroom
# exhausts system commit and crashes OTHER processes, so we refuse instead.
REQUIRED_FREE_MB = {"en": 2200, "ru": 4000}
ENABLED = [lang.strip() for lang in os.environ.get("KOKORO_LANGS", "en,ru").lower().split(",")
           if lang.strip() in VOICES]
SKIP_MEMCHECK = os.environ.get("KOKORO_SKIP_MEMCHECK") == "1"

STATE = {"ready": {"ru": False, "en": False}, "errors": {}, "load_seconds": None}
ENGINE = {}
INFER_LOCK = threading.Lock()       # the models are not safe for parallel inference
WAITING = threading.Semaphore(MAX_WAITING + 1)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _check_files(lang):
    spec = VOICES[lang]
    for key in ("checkpoint", "config", "voicepack", "male_voicepack"):
        if not spec[key].exists():
            raise FileNotFoundError(f"{spec[key]} topilmadi")
    for key in ("voicepack", "male_voicepack"):
        digest = hashlib.sha256(spec[key].read_bytes()).hexdigest()
        if digest != spec[key + "_sha256"]:
            raise RuntimeError(f"{spec[key].name} SHA256 mos kelmadi: {digest}")


def _load_packs(spec):
    import torch
    return {gender: torch.load(str(spec[key]), map_location="cpu", weights_only=True)
            for gender, key in (("female", "voicepack"), ("male", "male_voicepack"))}


def load_english():
    import torch
    from kokoro import KModel, KPipeline
    _check_files("en")
    spec = VOICES["en"]
    model = KModel(repo_id=spec["model"], config=str(spec["config"]),
                   model=str(spec["checkpoint"])).eval()
    pipeline = KPipeline(lang_code="a", repo_id=spec["model"], model=model)
    ENGINE["en"] = {"pipeline": pipeline, "packs": _load_packs(spec)}


def load_russian():
    import torch
    from kokoro import KModel
    _check_files("ru")
    spec = VOICES["ru"]
    sys.path.insert(0, str(RU_DIR))
    from ru_g2p import RuG2P        # ships with zaakirio/kokoro-ru, used unmodified
    g2p = RuG2P()
    model = KModel(repo_id=spec["model"], config=str(spec["config"]),
                   model=str(spec["checkpoint"])).eval()
    ENGINE["ru"] = {"g2p": g2p, "model": model, "packs": _load_packs(spec)}


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


def load_models():
    started = time.perf_counter()
    # English first: its espeak fallback must initialise with the stock espeak
    # data before RuG2P switches the data path to the acute-aware Russian build.
    for lang, loader in (("en", load_english), ("ru", load_russian)):
        try:
            if lang not in ENABLED:
                raise RuntimeError("KOKORO_LANGS orqali o'chirilgan")
            free = free_commit_mb()
            if not SKIP_MEMCHECK and free is not None and free < REQUIRED_FREE_MB[lang]:
                raise MemoryError(
                    f"xotira yetarli emas: bo'sh commit {free} MB, kerak "
                    f"{REQUIRED_FREE_MB[lang]} MB (pagefile'ni kattalashtiring yoki "
                    "boshqa modellarni yoping)")
            t = time.perf_counter()
            loader()
            STATE["ready"][lang] = True
            print(f"[Kokoro] {lang} tayyor: {VOICES[lang]['voice']} "
                  f"({time.perf_counter() - t:.1f}s)", flush=True)
        except Exception as exc:
            STATE["errors"][lang] = f"{type(exc).__name__}: {exc}"
            print(f"[Kokoro ERROR] {lang} yuklanmadi: {STATE['errors'][lang]}", flush=True)
            if not isinstance(exc, (MemoryError, RuntimeError)):
                traceback.print_exc()
    STATE["load_seconds"] = round(time.perf_counter() - started, 2)


_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n+")


def _ru_phoneme_chunks(g2p, text):
    """Split Russian text into phoneme strings that fit the model context."""
    chunks = []

    def add(piece):
        piece = piece.strip()
        if not piece:
            return
        ipa, _oov = g2p(piece)
        ipa = "".join(c for c in ipa if c in g2p.vocab).strip()
        if not ipa:
            return
        if len(ipa) <= MAX_PHONEMES:
            chunks.append(ipa)
            return
        words = piece.split()
        if len(words) < 2:
            chunks.append(ipa[:MAX_PHONEMES])
            return
        # Prefer the comma nearest the middle, otherwise split on a word boundary.
        middle = len(words) // 2
        commas = [i + 1 for i, w in enumerate(words[:-1]) if w[-1] in ",;:—"]
        cut = min(commas, key=lambda i: abs(i - middle)) if commas else middle
        add(" ".join(words[:cut]))
        add(" ".join(words[cut:]))

    for sentence in _SENTENCE_RE.split(text):
        add(sentence)
    return chunks


def synthesize(lang, text, speed, gender="female"):
    import numpy as np
    import torch
    engine = ENGINE[lang]
    pack = engine["packs"][gender]
    parts = []
    with torch.no_grad():
        if lang == "ru":
            gap = np.zeros(int(SAMPLE_RATE * SENTENCE_GAP), dtype=np.float32)
            for ipa in _ru_phoneme_chunks(engine["g2p"], text):
                out = engine["model"](ipa, pack[len(ipa) - 1], speed,
                                      return_output=True)
                if parts:
                    parts.append(gap)
                parts.append(out.audio.cpu().numpy())
        else:
            for result in engine["pipeline"](text, voice=pack, speed=speed):
                if result.audio is not None:
                    parts.append(result.audio.cpu().numpy())
    if not parts:
        raise ApiError(422, "Matnda talaffuz qilinadigan belgi topilmadi")
    audio = np.nan_to_num(np.concatenate(parts).astype(np.float32))
    if audio.size == 0 or float(np.abs(audio).max()) < 1e-4:
        raise RuntimeError("Model bo'sh yoki jim audio qaytardi")
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue(), len(pcm) / SAMPLE_RATE


def memory_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6)
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalKokoroTTS/1.0"

    def send_bytes(self, status, body, content_type, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Expose-Headers",
                         "X-TTS-Voice, X-TTS-Model, X-TTS-Duration, X-TTS-Elapsed")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8")

    def do_OPTIONS(self):
        self.send_bytes(204, b"", "text/plain")

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/api/health":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        ready = STATE["ready"]
        self.send_json(200, {
            "ok": bool(ENABLED) and all(ready[lang] for lang in ENABLED),
            "enabled": ENABLED,
            "free_commit_mb": free_commit_mb(),
            "loading": STATE["load_seconds"] is None,
            "service": "Local Kokoro TTS",
            "ready": ready,
            "languages": [lang for lang, ok in ready.items() if ok],
            "voices": {lang: spec["voice"] for lang, spec in VOICES.items()},
            "male_voices": {lang: spec["male_voice"] for lang, spec in VOICES.items()},
            "models": {lang: spec["model"] for lang, spec in VOICES.items()},
            "errors": STATE["errors"],
            "sample_rate": SAMPLE_RATE,
            "load_seconds": STATE["load_seconds"],
            "memory_mb": memory_mb(),
        })

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/tts":
            self.send_json(404, {"ok": False, "error": "Not found"})
            return
        try:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ApiError(400, "So'rov hajmi noto'g'ri")
            if size <= 0:
                raise ApiError(400, "So'rov bo'sh")
            if size > MAX_BODY:
                raise ApiError(413, "So'rov hajmi juda katta")
            try:
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "JSON noto'g'ri")
            if not isinstance(payload, dict):
                raise ApiError(400, "JSON obyekt bo'lishi kerak")

            lang = str(payload.get("language", "")).strip().lower()
            text = str(payload.get("text", "")).strip()
            if lang not in VOICES:
                raise ApiError(400, "Til ru yoki en bo'lishi kerak")
            if not text:
                raise ApiError(400, "Matn bo'sh")
            if len(text) > MAX_TEXT:
                raise ApiError(413, f"Matn {MAX_TEXT} belgidan oshmasin")
            try:
                speed = float(payload.get("speed", 1.0))
            except (TypeError, ValueError):
                raise ApiError(400, "speed son bo'lishi kerak")
            speed = min(2.0, max(0.5, speed))
            gender = str(payload.get("voice", "female")).strip().lower()
            if gender not in ("female", "male"):
                raise ApiError(400, "voice female yoki male bo'lishi kerak")
            if not STATE["ready"][lang]:
                detail = STATE["errors"].get(lang, "model hali yuklanmoqda")
                raise ApiError(503, f"{lang} modeli tayyor emas: {detail}")

            if not WAITING.acquire(blocking=False):
                raise ApiError(503, "Server band, birozdan keyin urinib ko'ring")
            try:
                with INFER_LOCK:
                    started = time.perf_counter()
                    audio, seconds = synthesize(lang, text, speed, gender)
                    elapsed = time.perf_counter() - started
            finally:
                WAITING.release()

            spec = VOICES[lang]
            voice_name = spec["male_voice"] if gender == "male" else spec["voice"]
            print(f"[Kokoro] {lang}/{voice_name}: {len(text)} belgi -> "
                  f"{seconds:.2f}s audio, {elapsed:.2f}s generatsiya", flush=True)
            self.send_bytes(200, audio, "audio/wav", {
                "X-TTS-Voice": voice_name,
                "X-TTS-Model": spec["model"],
                "X-TTS-Duration": f"{seconds:.3f}",
                "X-TTS-Elapsed": f"{elapsed:.3f}",
            })
        except ApiError as exc:
            self.send_json(exc.status, {"ok": False, "error": str(exc)})
        except (BrokenPipeError, ConnectionError):
            pass
        except Exception as exc:
            print("[Kokoro ERROR] inference:", flush=True)
            traceback.print_exc()
            self.send_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):
        print("[Kokoro HTTP] " + (fmt % args), flush=True)


if __name__ == "__main__":
    # Bind first so a port clash fails fast, before gigabytes of models load.
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local Kokoro TTS: http://{HOST}:{PORT}", flush=True)
    print("Kokoro modellari yuklanmoqda...", flush=True)

    def _load():
        load_models()
        print(f"[Kokoro] ready={STATE['ready']}  xotira={memory_mb()}MB", flush=True)

    # Load once at startup, in the background, so /api/health answers meanwhile.
    threading.Thread(target=_load, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
