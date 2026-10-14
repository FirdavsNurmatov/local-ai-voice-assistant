import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
import ctranslate2
from transformers import AutoTokenizer

BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "local_voice_chat.html"

MODEL_DIR = str(BASE_DIR / "madlad400-3b-ct2-int8")
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
TTS_URL = "http://127.0.0.1:8766/api/tts"
TTS_HEALTH_URL = "http://127.0.0.1:8766/api/health"
STT_URL = "http://127.0.0.1:8769/api/transcribe"
STT_HEALTH_URL = "http://127.0.0.1:8769/api/health"
STT_MAX_BODY = 25 * 1024 * 1024
QWEN_MODEL = "qwen3:1.7b"
HOST = "0.0.0.0"
PORT = 8765

UZ_WORDS = {
    "salom", "assalomu", "alaykum", "qayerda", "qanday",
    "qalaysan", "qandaysan", "nima", "uchun", "rahmat",
    "iltimos", "bugun", "yaxshi", "yomon", "men", "siz",
    "menga", "kerak", "mumkin", "robot", "kutubxona",
    "kutubxonada", "kutubxonaga", "joylashgan", "toshkent",
    "o'zbekiston", "ozbekiston", "bilan", "qil", "qiladi",
    "beradi", "odamlar", "mehmonlar", "chiqamizmi",
    "yordam", "qilaman", "qilasiz", "qilasan", "qilamiz",
    "qanday", "qilsa", "bo'ladi", "boladi", "qila"
}

CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    "ў": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h",
}

def detect_language(text: str) -> str:
    if any("\u0400" <= ch <= "\u04ff" for ch in text):
        return "ru"
    lower = text.lower()
    normalized = (
        lower.replace("'", "").replace("’", "")
        .replace("ʻ", "").replace("ʼ", "")
    )
    words = set(re.sub(r"[^\w]+", " ", normalized).split())
    if words & UZ_WORDS or any(mark in lower for mark in ("oʻ", "gʻ")):
        return "uz"
    return "en"

def uzbek_cyrillic_to_latin(text: str) -> str:
    result = []
    for char in text:
        converted = CYRILLIC_TO_LATIN.get(char.lower(), char)
        if char.isupper() and converted:
            converted = converted[0].upper() + converted[1:]
        result.append(converted)
    text = "".join(result)
    text = re.sub(r"\bkitobxona", "kutubxona", text, flags=re.IGNORECASE)
    text = re.sub(r"\bqaerda\b", "qayerda", text, flags=re.IGNORECASE)
    return text

print("MADLAD tokenizer yuklanmoqda...")
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_DIR, local_files_only=True, use_fast=False
)
print("MADLAD INT8 modeli yuklanmoqda...")
translator = ctranslate2.Translator(
    MODEL_DIR, device="cpu", compute_type="int8",
    inter_threads=1, intra_threads=4,
)
print("MADLAD tayyor.")
translation_lock = threading.Lock()

def translate(text: str, target: str):
    if not text.strip():
        return text, 0.0
    prompt = f"<2{target}> {text}"
    ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)
    started = time.perf_counter()
    with translation_lock:
        result = translator.translate_batch(
            [tokens], max_decoding_length=128, beam_size=1
        )
    output_tokens = result[0].hypotheses[0]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    return output, time.perf_counter() - started

def run_chat(text: str, requested_language: str):
    started = time.perf_counter()
    # An explicit language (e.g. the one detected by the STT service) wins;
    # "auto" or anything else falls back to text-based detection.
    lang = requested_language if requested_language in ("uz", "ru", "en") else detect_language(text)
    if lang == "en":
        english, input_time = text, 0.0
    else:
        english, input_time = translate(text, "en")

    qwen_started = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": QWEN_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are a helpful, friendly assistant. "
                    "Answer in English in 1-3 concise sentences. "
                    "Do not include reasoning or thinking."
                )},
                {"role": "user", "content": english},
            ],
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"num_ctx": 2048, "num_predict": 100, "temperature": 0.4},
        },
        timeout=180,
    )
    response.raise_for_status()
    answer_en = response.json()["message"]["content"].strip()
    qwen_time = time.perf_counter() - qwen_started
    if lang == "en":
        answer, output_time = answer_en, 0.0
    else:
        answer, output_time = translate(answer_en, lang)
        if lang == "uz":
            answer = uzbek_cyrillic_to_latin(answer)
    return {
        "ok": True, "language": lang, "input": text,
        "english_input": english, "answer_english": answer_en, "answer": answer,
        "timings": {
            "input_translation": round(input_time, 2),
            "qwen": round(qwen_time, 2),
            "output_translation": round(output_time, 2),
            "total": round(time.perf_counter() - started, 2),
        },
    }

class Handler(BaseHTTPRequestHandler):
    server_version = "LocalVoiceChat/1.1"

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/local_voice_chat.html"):
            if not HTML_FILE.exists():
                self._send(404, "local_voice_chat.html topilmadi", "text/plain; charset=utf-8")
                return
            self._send(200, HTML_FILE.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            try:
                tts_response = requests.get(TTS_HEALTH_URL, timeout=1.5)
                tts_ok = tts_response.ok and tts_response.json().get("ok", False)
            except requests.RequestException:
                tts_ok = False
            self._send(200, json.dumps({
                "ok": True,
                "model": QWEN_MODEL,
                "translation_model": "MADLAD-400-3B INT8",
                "local_tts": bool(tts_ok),
                "tts_model": "vits_uzbek_finetuned.onnx" if tts_ok else None,
            }, ensure_ascii=False))
            return
        if path == "/api/stt/health":
            # STT is reached through this server so it also works over HTTPS tunnels / phones.
            try:
                stt_response = requests.get(STT_HEALTH_URL, timeout=3)
                self._send(stt_response.status_code, stt_response.content,
                           stt_response.headers.get("Content-Type", "application/json; charset=utf-8"))
            except requests.RequestException as exc:
                self._send(502, json.dumps({
                    "ok": False, "ready": False,
                    "error": f"STT serveriga ulanib bo'lmadi (8769): {type(exc).__name__}",
                }, ensure_ascii=False))
            return
        self._send(404, json.dumps({"ok": False, "error": "Not found"}))

    def proxy_transcribe(self):
        """Pass the uploaded audio (raw or multipart) and ?language= to the STT server unchanged."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > STT_MAX_BODY:
            self._send(400 if length <= 0 else 413, json.dumps({
                "ok": False, "error": "Audio yuborilmadi yoki 25 MB dan katta"}, ensure_ascii=False))
            return
        body = self.rfile.read(length)
        query = urlparse(self.path).query
        try:
            stt_response = requests.post(
                STT_URL + (f"?{query}" if query else ""), data=body, timeout=300,
                headers={"Content-Type": self.headers.get("Content-Type", "application/octet-stream")})
        except requests.RequestException as exc:
            self._send(502, json.dumps({
                "ok": False,
                "error": f"STT serveriga ulanib bo'lmadi (8769): {type(exc).__name__}",
            }, ensure_ascii=False))
            return
        self._send(stt_response.status_code, stt_response.content,
                   stt_response.headers.get("Content-Type", "application/json; charset=utf-8"))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/transcribe":
            self.proxy_transcribe()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100_000:
                self._send(400, json.dumps({"ok": False, "error": "Invalid request size"}))
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))

            if path == "/api/tts":
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send(400, json.dumps({"ok": False, "error": "Matn bo'sh"}))
                    return
                if len(text) > 2000:
                    self._send(400, json.dumps({"ok": False, "error": "Matn 2000 belgidan oshmasin"}))
                    return
                try:
                    tts_response = requests.post(
                        TTS_URL, json={"text": text}, timeout=120
                    )
                except requests.RequestException as exc:
                    self._send(502, json.dumps({
                        "ok": False,
                        "error": f"Mahalliy TTS serveriga ulanib bo'lmadi: {exc}",
                    }, ensure_ascii=False))
                    return
                if not tts_response.ok:
                    self._send(tts_response.status_code, tts_response.content,
                               tts_response.headers.get("Content-Type", "application/json; charset=utf-8"))
                    return
                self._send(200, tts_response.content, "audio/wav")
                return

            if path != "/api/chat":
                self._send(404, json.dumps({"ok": False, "error": "Not found"}))
                return
            text = str(payload.get("text", "")).strip()
            language = str(payload.get("language", "auto")).lower()
            if not text:
                self._send(400, json.dumps({"ok": False, "error": "Matn bo'sh"}))
                return
            if len(text) > 5000:
                self._send(400, json.dumps({"ok": False, "error": "Matn 5000 belgidan oshmasin"}))
                return
            result = run_chat(text, language)
            self._send(200, json.dumps(result, ensure_ascii=False))
        except requests.RequestException as exc:
            self._send(502, json.dumps({
                "ok": False, "error": f"Ollama bilan ulanish xatosi: {exc}",
            }, ensure_ascii=False))
        except Exception as exc:
            self._send(500, json.dumps({
                "ok": False, "error": f"{type(exc).__name__}: {exc}",
            }, ensure_ascii=False))

    def log_message(self, fmt, *args):
        print("[HTTP] " + (fmt % args))

if __name__ == "__main__":
    print(f"\nChat server: http://localhost:{PORT}")
    print("TTS proxy: /api/tts -> http://127.0.0.1:8766/api/tts")
    print("STT proxy: /api/transcribe, /api/stt/health -> http://127.0.0.1:8769")
    print("Faqat ishonchli lokal tarmoqda ishlating; autentifikatsiya yo'q.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

