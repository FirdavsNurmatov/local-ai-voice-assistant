r"""Uzbek male voice TTS service (port 8770).

Runs the Uzbek_TTS model (F5-TTS style flow matching, `Uzbek_TTS-test\ckpts\UZ.safetensors`) with exactly
the settings of `Uzbek_TTS-test\test_generate.py`, which produced the owner-approved sample
`Uzbek_TTS-test\test_uzbek_tts.wav`: reference voice `test_data\test_erkak.wav` + its transcript,
nfe_step=8, speed 1.0, CUDA. The model clones the voice of the reference recording.

Start with the experiment's own environment (torch + CUDA):
    Uzbek_TTS-test\.venv\Scripts\python.exe uz_male_tts_server.py
The local code changes this needs in `Uzbek_TTS-test\` are in docs\patches\uzbek-tts-male-voice.patch.

API (same shape as the female Uzbek TTS on 8766):
    GET  /api/health -> {"ok", "ready", "loading", "voice": "male", "model", "device", "sample_rate", "error"}
    POST /api/tts {"text": "..."} -> audio/wav (24 kHz, mono, 16-bit PCM)
"""
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "Uzbek_TTS-test"
HOST = "127.0.0.1"
PORT = 8770
# settings of test_generate.py (the approved sample)
REF_AUDIO = MODEL_DIR / "test_data" / "test_erkak.wav"
REF_TEXT = "Jizzax kollejlarida infraqizil aniqlagichli turniketlar o'rnatilmoqda."
CKPT = MODEL_DIR / "ckpts" / "UZ.safetensors"
CKPT_SHA256 = "27e7dc127b78453f539cfe5c5b23d4b542c5537ac179f3aa2c877d8cece2ca12"
REF_AUDIO_SHA256 = "900b63375177b0fcaeaff65d245ae0e6ab439053878c4e426f8ba88c2f599b2c"
NFE_STEP = 8
SPEED = 1.0
# The model handles ~30 s (reference + output) per pass; longer answers are generated sentence by sentence.
MAX_CHUNK_BYTES = 160
PAUSE_S = 0.15

os.environ.setdefault("HF_HUB_OFFLINE", "1")   # the Vocos vocoder must already be in the Hugging Face cache
os.chdir(MODEL_DIR)                            # the model code uses paths relative to its folder
sys.path.insert(0, str(MODEL_DIR))

state = {"ready": False, "loading": True, "error": None, "device": None, "sample_rate": 24000, "load_s": None}
tts = None


def load_model():
    global tts
    started = time.perf_counter()
    try:
        import torch
        from hydra.utils import get_class
        from omegaconf import OmegaConf
        from tts import TTS
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU topilmadi (erkak ovozi modeli GPU talab qiladi)")
        for path, expected in ((CKPT, CKPT_SHA256), (REF_AUDIO, REF_AUDIO_SHA256)):
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise RuntimeError(f"{path.name} SHA256 mos kelmadi (boshqa fayl?)")
        cfg = OmegaConf.load("config/UZTTS_conf.yaml")
        with contextlib.redirect_stdout(io.StringIO()):
            tts = TTS(ref_audio_path=str(REF_AUDIO), ref_text=REF_TEXT, model_cfg=cfg,
                      model_cls=get_class(f"uz_tts.model.{cfg.model.backbone}"), vocab="config/uz_vocab.txt",
                      ckpt_path=str(CKPT), device="cuda", preload_models=True, speed=SPEED, nfe_step=NFE_STEP)
        state.update(ready=True, device=torch.cuda.get_device_name(0), sample_rate=tts.target_sample_rate)
        print(f"Erkak ovozi modeli tayyor ({time.perf_counter() - started:.1f}s, {state['device']})", flush=True)
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        print("Erkak ovozi modeli yuklanmadi:", state["error"], flush=True)
    finally:
        state.update(loading=False, load_s=round(time.perf_counter() - started, 1))


def split_text(text):
    """Sentences, merged up to MAX_CHUNK_BYTES; a single long sentence is split at commas/spaces."""
    sentences = [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]
    pieces = []
    for s in sentences:
        while len(s.encode("utf-8")) > MAX_CHUNK_BYTES:
            cut = max(s.rfind(", ", 0, MAX_CHUNK_BYTES), s.rfind(" ", 0, MAX_CHUNK_BYTES))
            if cut <= 0:
                break
            pieces.append(s[:cut + 1].strip()); s = s[cut + 1:].strip()
        pieces.append(s)
    chunks, current = [], ""
    for p in pieces:
        candidate = f"{current} {p}".strip()
        if current and len(candidate.encode("utf-8")) > MAX_CHUNK_BYTES:
            chunks.append(current); current = p
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def make_audio(text):
    started = time.perf_counter()
    sr = state["sample_rate"]
    parts = []
    for chunk in split_text(text):
        with contextlib.redirect_stdout(io.StringIO()):     # the model code prints debug lines
            audio, sr = tts.generate_speech(chunk)
        audio = np.nan_to_num(np.asarray(audio, dtype=np.float32).squeeze())
        if parts:
            parts.append(np.zeros(int(PAUSE_S * sr), dtype=np.float32))
        parts.append(audio)
    pcm = (np.clip(np.concatenate(parts), -1.0, 1.0) * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    print(f"TTS (erkak): {len(text)} belgi -> {len(pcm)/sr:.2f}s audio, {time.perf_counter()-started:.2f}s", flush=True)
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalUzbekMaleTTS/1.0"

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/health":
            self._send(200, json.dumps({"ok": True, "voice": "male", "model": CKPT.name, "ref_audio": REF_AUDIO.name,
                                        "nfe_step": NFE_STEP, **state}, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"ok": False, "error": "Not found"}))

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/tts":
            self._send(404, json.dumps({"ok": False, "error": "Not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20000:
                self._send(400, json.dumps({"ok": False, "error": "Noto'g'ri so'rov hajmi"}))
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(payload.get("text", "")).strip()
            if not text:
                self._send(400, json.dumps({"ok": False, "error": "Matn bo'sh"}))
                return
            if len(text) > 2000:
                self._send(400, json.dumps({"ok": False, "error": "Matn 2000 belgidan oshmasin"}))
                return
            if not state["ready"]:
                error = state["error"] or "model hali yuklanmoqda"
                self._send(503, json.dumps({"ok": False, "error": f"Erkak ovozi tayyor emas: {error}"}, ensure_ascii=False))
                return
            try:
                self._send(200, make_audio(text), "audio/wav")
            except Exception as exc:
                print(f"[TTS ERROR] {len(text)} belgi: {type(exc).__name__}: {exc}", flush=True)
                self._send(422, json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        except Exception as exc:
            self._send(400, json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))

    def log_message(self, fmt, *args):
        print("[TTS HTTP] " + (fmt % args), flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)     # bind first, then load (health shows "loading")
    threading.Thread(target=load_model, daemon=True).start()
    print(f"Uzbek male TTS server: http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
