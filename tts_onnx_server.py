from email.mime import text
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import onnxruntime as ort
from scipy.io import wavfile

BASE_DIR = Path(__file__).resolve().parent
TTS_DIR = BASE_DIR / "stt-tts-uz"
MODEL_PATH = TTS_DIR / "models" / "vits_uzbek_finetuned.onnx"
CONFIG_PATH = TTS_DIR / "models" / "uz_tts_base.json"
HOST = "127.0.0.1"
PORT = 8766
SAMPLE_RATE = 22050

# Import repository text cleaners/tokenizer without importing torch-based utils.py.
sys.path.insert(0, str(TTS_DIR))
from text import text_to_sequence
from text.symbols import symbols

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG = json.load(f)
DATA_CONFIG = CONFIG["data"]
SAMPLE_RATE = int(DATA_CONFIG.get("sampling_rate", SAMPLE_RATE))

print("Fine-tuned Uzbek ONNX TTS modeli yuklanmoqda...")
SESSION = ort.InferenceSession(
    str(MODEL_PATH), providers=["CPUExecutionProvider"]
)
print("TTS modeli tayyor:", MODEL_PATH)
print("Provider:", SESSION.get_providers())

def make_audio(text: str) -> bytes:
    # Model lug'atida mavjud bo'lmagan belgilarni olib tashlash.
    # O'zbekcha harflar va tinish belgilarini imkon qadar saqlaymiz.
    allowed_chars = set(symbols)
    text = "".join(ch for ch in text if ch in allowed_chars or ch.isspace())
    text = text.strip()

    text = text.replace("🎉", "").replace("🎊", "").replace("😊", "").replace("😂", "")
    sequence = text_to_sequence(text, DATA_CONFIG["text_cleaners"])
    if DATA_CONFIG.get("add_blank", False):
        sequence = [0] + [
            value
            for pair in zip(sequence, [0] * len(sequence))
            for value in pair
        ]
    if not sequence:
        raise ValueError("Matn bo'sh yoki model qo'llaydigan belgilar qolmadi.")
    if min(sequence) < 0 or max(sequence) >= len(symbols):
        raise ValueError("Matnda model qo'llamaydigan belgi bor.")
    x = np.asarray(sequence, dtype=np.int64)[None, :]
    x_lengths = np.asarray([x.shape[1]], dtype=np.int64)

    started = time.perf_counter()
    result = SESSION.run(None, {
        "x": x,
        "x_lengths": x_lengths,
        "noise_scale": np.asarray(0.667, dtype=np.float32),
        "noise_scale_w": np.asarray(0.8, dtype=np.float32),
        "length_scale": np.asarray(1.0, dtype=np.float32),
    })
    elapsed = time.perf_counter() - started

    audio = np.nan_to_num(np.asarray(result[0]).squeeze())
    if audio.size == 0:
        raise RuntimeError("Model bo'sh audio qaytardi.")
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)

    import io
    buffer = io.BytesIO()
    wavfile.write(buffer, SAMPLE_RATE, pcm)
    print(f"TTS: {len(text)} belgi -> {len(pcm)/SAMPLE_RATE:.2f}s audio, {elapsed:.2f}s generatsiya")
    return buffer.getvalue()

class Handler(BaseHTTPRequestHandler):
    server_version = "LocalUzbekTTS/1.0"

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
            self._send(200, json.dumps({
                "ok": True, "model": MODEL_PATH.name,
                "provider": SESSION.get_providers(),
                "sample_rate": SAMPLE_RATE,
            }))
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
            try:
                audio = make_audio(text)
                self._send(200, audio, "audio/wav")
            except Exception as exc:
                print(f"[TTS ERROR] Matn: {text!r}")
                import traceback
                traceback.print_exc()
                self._send(422, json.dumps({
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}"
                }, ensure_ascii=False))
        except Exception as exc:
            self._send(400, json.dumps({
                "ok": False, "error": f"{type(exc).__name__}: {exc}"
            }, ensure_ascii=False))

    def log_message(self, fmt, *args):
        print("[TTS HTTP] " + (fmt % args))

if __name__ == "__main__":
    print(f"Local Uzbek TTS server: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
