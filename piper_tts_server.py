import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON = BASE_DIR / ".venv-piper" / "Scripts" / "python.exe"
MODELS = {
    "ru": BASE_DIR / "ru_RU-irina-medium.onnx",
    "en": BASE_DIR / "en_US-lessac-medium.onnx",
}
# "voice": "male" in the request (added 2026-10-17; rhasspy/piper-voices @ c10ece1a)
MALE_MODELS = {
    "ru": BASE_DIR / "ru_RU-dmitri-medium.onnx",
    "en": BASE_DIR / "en_US-ryan-medium.onnx",
}
PORT = 8767


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_bytes(204, b"", "text/plain")

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/health":
            result = {
                "ok": True,
                "service": "Local Piper TTS",
                "models": {lang: path.name for lang, path in MODELS.items()},
                "male_models": {lang: path.name for lang, path in MALE_MODELS.items()},
            }
            self.send_bytes(200, json.dumps(result).encode(), "application/json")
        else:
            self.send_bytes(404, b'{"ok":false,"error":"Not found"}',
                            "application/json")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/tts":
            self.send_bytes(404, b'{"ok":false,"error":"Not found"}',
                            "application/json")
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 20000:
                raise ValueError("So'rov hajmi noto'g'ri")

            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            lang = str(payload.get("language", "")).lower()
            text = str(payload.get("text", "")).strip()

            if lang not in MODELS:
                raise ValueError("Til ru yoki en bo'lishi kerak")
            if not text:
                raise ValueError("Matn bo'sh")
            if len(text) > 2000:
                raise ValueError("Matn 2000 belgidan oshmasin")
            gender = str(payload.get("voice", "female")).lower()
            if gender not in ("female", "male"):
                raise ValueError("voice female yoki male bo'lishi kerak")

            model = (MALE_MODELS if gender == "male" else MODELS)[lang]
            config = Path(str(model) + ".json")
            if not PYTHON.exists() or not model.exists() or not config.exists():
                raise FileNotFoundError("Piper Python, model yoki config topilmadi")

            with tempfile.TemporaryDirectory(prefix="local_piper_") as temp:
                temp_dir = Path(temp)
                input_file = temp_dir / "input.txt"
                output_file = temp_dir / "output.wav"
                input_file.write_text(text, encoding="utf-8")

                command = [
                    str(PYTHON), "-m", "piper",
                    "-m", str(model), "-c", str(config),
                    "-i", str(input_file), "-f", str(output_file),
                ]
                result = subprocess.run(
                    command, cwd=str(BASE_DIR),
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=120,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )

                if result.returncode != 0 or not output_file.exists():
                    detail = (result.stderr or result.stdout or "Piper xatosi")[-3000:]
                    raise RuntimeError(detail)
                audio = output_file.read_bytes()
                if len(audio) < 44:
                    raise RuntimeError("Piper bo'sh yoki noto'g'ri WAV qaytardi")

            print(f"[Piper] {lang}/{model.stem}: {len(text)} belgi -> {len(audio)} bayt")
            self.send_bytes(200, audio, "audio/wav")

        except Exception as exc:
            print(f"[Piper ERROR] {exc}")
            body = json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_bytes(422, body, "application/json")

    def log_message(self, fmt, *args):
        print("[Piper HTTP] " + (fmt % args))


if __name__ == "__main__":
    print(f"Local Piper TTS: http://127.0.0.1:{PORT}")
    print("Models:", {k: v.name for k, v in MODELS.items()}, "male:", {k: v.name for k, v in MALE_MODELS.items()})
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
