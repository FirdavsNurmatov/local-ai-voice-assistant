# API reference

- **Last verified:** 2026-10-13 · **Status:** routes and schemas `SOURCE-CODE CONFIRMED`; responses marked ✔ were also observed in tests on 2026-10-13 (`HISTORICAL TEST RESULT`)
- **Related source:** `server.py`, `tts_onnx_server.py`, `piper_tts_server.py`, `kokoro_tts_server.py`, `stt_server.py` (added 2026-10-14)
- **Related:** [ARCHITECTURE.md](ARCHITECTURE.md), [TESTING.md](TESTING.md)

Only routes that exist in the code are listed. None of the services uses authentication, TLS,
cookies or API keys. All JSON is UTF-8. Error messages are in Uzbek (a few in English).

## Conventions for the examples

Windows PowerShell 5.1 sends non-ASCII request bodies in the wrong encoding unless the body is
passed as UTF-8 bytes. The examples use this helper:

```powershell
function Send-Json($Url, $Object, $OutFile) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Object | ConvertTo-Json -Compress))
    if ($OutFile) { Invoke-WebRequest $Url -Method Post -Body $bytes -ContentType 'application/json' -UseBasicParsing -OutFile $OutFile }
    else          { Invoke-RestMethod  $Url -Method Post -Body $bytes -ContentType 'application/json' }
}
```

With `curl.exe`, put the JSON in a UTF-8 file to avoid PowerShell quoting problems:

```powershell
Set-Content -Encoding utf8 body.json '{"text":"Hello! This is a test.","language":"en"}'
curl.exe -s -X POST http://127.0.0.1:8768/api/tts -H "Content-Type: application/json" --data-binary "@body.json" -o out.wav
```

(Windows PowerShell's `Set-Content -Encoding utf8` writes a BOM; the Kokoro, Piper and Uzbek
servers decode with `utf-8` and `json.loads` rejects a BOM. If you get "JSON noto'g'ri", create the
file with `[IO.File]::WriteAllText("$PWD\body.json", '…')` instead, which writes no BOM.)

---

## Chat backend — `server.py`, port 8765

Bind `0.0.0.0`. No CORS headers. No `OPTIONS` handler. Every response has `Cache-Control: no-store`.

### `GET /` and `GET /local_voice_chat.html`

Returns the frontend. `200 text/html; charset=utf-8` ✔, or `404 text/plain` (`local_voice_chat.html topilmadi`) if the file is missing.

### `GET /api/health`

Always `200` while the process is up. Probes the Uzbek TTS health endpoint with a 1.5 s timeout.

```json
{"ok": true, "model": "qwen3:1.7b", "translation_model": "MADLAD-400-3B INT8",
 "local_tts": true, "tts_model": "vits_uzbek_finetuned.onnx"}
```

✔ `local_tts` is `false` and `tts_model` is `null` when 8766 is unreachable. `ok` and `model` are
constants: this endpoint does **not** check that Ollama is running or that the model exists.

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

### `POST /api/chat`

Runs the full pipeline (detect → translate → LLM → translate). Readiness: MADLAD loaded (always true once the port is open) and Ollama reachable.

Request (`Content-Type: application/json`, body 1–100 000 bytes):

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | trimmed; 1–5000 characters |
| `language` | string | no | `"uz"`, `"ru"` or `"en"` forces that language for both translation directions and the reply (the page sends the STT-detected language here); any other value or omission (default `"auto"`) → detect from the text. Changed 2026-10-14; before that the field was ignored. ✔ |

Response `200` ✔:

| Field | Type | Notes |
|---|---|---|
| `ok` | bool | `true` |
| `language` | string | language actually used: `"ru"`, `"uz"` or `"en"` (requested or detected) |
| `input` | string | original text |
| `english_input` | string | text sent to the LLM |
| `answer_english` | string | raw LLM answer |
| `answer` | string | answer in the user's language |
| `timings` | object | seconds, 2 decimals: `input_translation`, `qwen`, `output_translation`, `total` |

Errors — body `{"ok": false, "error": "…"}`:

| Status | When |
|---|---|
| `400` | body missing or > 100 000 bytes (`Invalid request size`); empty text (`Matn bo'sh`); text > 5000 chars |
| `502` | Ollama unreachable, timed out (180 s) or returned an HTTP error (`Ollama bilan ulanish xatosi: …`) |
| `500` | anything else, e.g. malformed JSON (`JSONDecodeError: …`), non-object JSON, unexpected Ollama payload, translation failure |
| `404` | other POST path (after the size check) |

```powershell
Send-Json http://127.0.0.1:8765/api/chat @{ text = 'Hello, how are you?'; language = 'en' }
```

### `POST /api/tts`

Proxy to the Uzbek TTS service; always Uzbek, no `language` field.

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | trimmed; 1–2000 characters |

`200 audio/wav` ✔ (WAV, 22 050 Hz, mono, 16-bit PCM). Errors: `400` (size / empty / too long),
`502` (`Mahalliy TTS serveriga ulanib bo'lmadi: …`, including the 120 s timeout), or the upstream
status and body passed through unchanged (e.g. `422`).

```powershell
Send-Json http://127.0.0.1:8765/api/tts @{ text = 'Assalomu alaykum! Xush kelibsiz.' } -OutFile uz.wav
```

### `POST /api/transcribe` (STT proxy, added 2026-10-14)

Forwards the request body unchanged (raw audio or `multipart/form-data`, with its `Content-Type`)
and the query string (`?language=…`) to `http://127.0.0.1:8769/api/transcribe`, and returns the STT
server's status code and JSON unchanged (`text`, `language`, … — see [STT](#stt--stt_serverpy-port-8769)).
This lets the page use voice input from any origin that reaches port 8765, including an HTTPS tunnel on a phone.
Own errors: `400` empty body, `413` > 25 MB, `502` STT server unreachable (`STT serveriga ulanib bo'lmadi (8769): …`), timeout 300 s. ✔ (locally and through a Cloudflare tunnel)

### `GET /api/stt/health` (added 2026-10-14)

Returns `GET http://127.0.0.1:8769/api/health` unchanged (timeout 3 s), or `502 {"ok": false, "ready": false, "error": …}`. The page calls it once at load and appends `+ STT ✓` to the header. ✔

---

## Uzbek TTS — `tts_onnx_server.py`, port 8766

Bind `127.0.0.1`. No CORS headers (a browser page cannot call it cross-origin). No `OPTIONS` handler.

### `GET /api/health`

```json
{"ok": true, "model": "vits_uzbek_finetuned.onnx", "provider": ["CPUExecutionProvider"], "sample_rate": 22050}
```

✔ The port only opens after the model has loaded, so a response means the model is ready.

### `POST /api/tts`

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | trimmed; 1–2000 characters; body 1–20 000 bytes |

`200 audio/wav` ✔ — 22 050 Hz, mono, 16-bit PCM. Characters outside the model's symbol table are dropped silently.

| Status | When |
|---|---|
| `400` | bad size (`Noto'g'ri so'rov hajmi`), empty text, text > 2000 chars, malformed JSON (`JSONDecodeError: …`) |
| `422` | synthesis failed, e.g. nothing pronounceable left (`ValueError: Matn bo'sh yoki model qo'llaydigan belgilar qolmadi.`) |
| `404` | other path |

```powershell
Send-Json http://127.0.0.1:8766/api/tts @{ text = 'Salom, dunyo!' } -OutFile uz.wav
```

---

## Piper TTS — `piper_tts_server.py`, port 8767

Bind `127.0.0.1`. CORS: `Access-Control-Allow-Origin: *`, methods `GET, POST, OPTIONS`, header `Content-Type`.

### `GET /api/health`

```json
{"ok": true, "service": "Local Piper TTS", "models": {"ru": "ru_RU-irina-medium.onnx", "en": "en_US-lessac-medium.onnx"}}
```

✔ Static: it does not check that the model files or `.venv-piper` exist.

### `OPTIONS *`

`204`, CORS headers (preflight).

### `POST /api/tts`

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | trimmed; 1–2000 characters; body 1–20 000 bytes |
| `language` | string | yes | `"ru"` or `"en"` (case-insensitive) |

`200 audio/wav` ✔ — 22 050 Hz. Each request starts a new Piper process (seconds of latency).

**All** failures return `422` with `{"ok": false, "error": "<ExceptionType>: <message>"}`: bad size,
bad JSON, wrong language (`Til ru yoki en bo'lishi kerak`), empty text, text too long, missing
Python/model/config (`FileNotFoundError`), Piper non-zero exit (`RuntimeError`, last 3000 chars of
its stderr), 120 s timeout. Other POST paths: `404`.

```powershell
Send-Json http://127.0.0.1:8767/api/tts @{ text = 'Здравствуйте! Это тест голоса.'; language = 'ru' } -OutFile piper_ru.wav
```

---

## Kokoro TTS — `kokoro_tts_server.py`, port 8768

Bind `127.0.0.1`. CORS as Piper, plus `Access-Control-Expose-Headers: X-TTS-Voice, X-TTS-Model, X-TTS-Duration, X-TTS-Elapsed`.

### `GET /api/health`

Answers as soon as the process has bound the port, **including while models are still loading**.

```json
{
  "ok": false, "enabled": ["en", "ru"], "free_commit_mb": 1654, "loading": false,
  "service": "Local Kokoro TTS",
  "ready": {"ru": false, "en": true}, "languages": ["en"],
  "voices": {"ru": "masha", "en": "af_heart"},
  "models": {"ru": "zaakirio/kokoro-ru", "en": "hexgrad/Kokoro-82M"},
  "errors": {"ru": "MemoryError: xotira yetarli emas: bo'sh commit 1653 MB, kerak 4000 MB (…)"},
  "sample_rate": 24000, "load_seconds": 9.58, "memory_mb": 1385
}
```

(Real response, 2026-10-13.)

| Field | Meaning |
|---|---|
| `ok` | `true` only if **every enabled** language is ready |
| `loading` | `true` until the background loader has finished (successfully or not) |
| `enabled` | languages allowed by `KOKORO_LANGS` |
| `ready` | per-language readiness — **check this, not `ok`, to know whether a given voice works** |
| `languages` | list of ready languages |
| `voices`, `models` | configured voice and upstream model id per language (static, shown even if not loaded) |
| `errors` | per-language load error text, if any |
| `free_commit_mb` | commit currently available to the process (Windows); `null` elsewhere |
| `memory_mb` | RSS of the server process |
| `load_seconds` | total load time; `null` while loading |

### `OPTIONS *`

`204`, CORS headers ✔.

### `POST /api/tts`

| Field | Type | Required | Notes |
|---|---|---|---|
| `text` | string | yes | trimmed; 1–2000 characters; body 1–20 000 bytes |
| `language` | string | yes | `"ru"` → `masha`, `"en"` → `af_heart` |
| `speed` | number | no | default `1.0`, clamped to 0.5–2.0 |

`200 audio/wav` ✔ — 24 000 Hz, mono, 16-bit PCM, with headers:

| Header | Example |
|---|---|
| `X-TTS-Voice` | `masha` / `af_heart` |
| `X-TTS-Model` | `zaakirio/kokoro-ru` / `hexgrad/Kokoro-82M` |
| `X-TTS-Duration` | audio seconds, e.g. `2.920` |
| `X-TTS-Elapsed` | synthesis seconds, e.g. `1.120` |

Errors — `{"ok": false, "error": "…"}` (all ✔ observed 2026-10-13 except `500`):

| Status | When |
|---|---|
| `400` | empty/invalid body, malformed JSON (`JSON noto'g'ri`), non-object JSON, missing/empty text (`Matn bo'sh`), language not `ru`/`en` (`Til ru yoki en bo'lishi kerak`), non-numeric `speed` |
| `413` | body > 20 000 bytes or text > 2000 characters |
| `422` | nothing pronounceable in the text (`Matnda talaffuz qilinadigan belgi topilmadi`) |
| `503` | language not ready: still loading (`…model hali yuklanmoqda`), disabled, files/hash problem, or not enough memory; **or** queue full (`Server band…`) |
| `500` | unexpected inference error (traceback printed to the server console) |
| `404` | other path |

```powershell
Invoke-RestMethod http://127.0.0.1:8768/api/health | ConvertTo-Json -Depth 4
Send-Json http://127.0.0.1:8768/api/tts @{ text = "That's wonderful! Let me explain it to you."; language = 'en' } -OutFile kokoro_en.wav
Send-Json http://127.0.0.1:8768/api/tts @{ text = 'Здравствуйте! Меня зовут Маша.'; language = 'ru'; speed = 1.0 } -OutFile kokoro_ru.wav
```

The Russian call returns `503` whenever `ready.ru` is `false`.

---

## STT — `stt_server.py`, port 8769

Bind `127.0.0.1`. CORS: `Access-Control-Allow-Origin: *`, methods `GET, POST, OPTIONS`, header `Content-Type`.
All responses are JSON. Tested 2026-10-14 (✔). Background: [STT.md](STT.md).

### `GET /api/health`

Answers as soon as the port is bound, including while the model loads.

```json
{"ok": true, "service": "Local Faster-Whisper STT", "ready": true, "loading": false, "error": null,
 "model": "small", "model_path": "C:\\local-ai-translator\\stt-models\\faster-whisper-small",
 "device": "cpu", "compute_type": "int8", "cpu_threads": 4,
 "language_detection": "auto (Whisper): ru/en if probability >= 0.5, otherwise uz; override with ?language=",
 "supported_languages": ["uz", "ru", "en"], "load_seconds": 1.46,
 "memory_mb": {"rss": 380, "commit": 2587}, "free_commit_mb": 6141}
```

`ok` = `ready`. `error` holds the load failure (missing model, not enough memory, …); the server never substitutes another model.

### `OPTIONS *`

`204` with CORS headers (the browser's preflight for an `audio/webm` upload).

### `POST /api/transcribe`

Query: `language=auto` (default) | `uz` | `ru` | `en`. Forcing a language that does not match the speech makes Whisper translate; leave it on `auto` unless sure.

Body — either:

- raw audio bytes with any `Content-Type` (the page sends `audio/webm;codecs=opus`), or
- `multipart/form-data` with one file part.

Limits: 25 MB, 0.3–180 s of audio. Formats verified: WebM/Opus, WAV, OGG/Vorbis, MP3.

Response `200`:

| Field | Type | Meaning |
|---|---|---|
| `ok` | bool | `true` |
| `text` | string | transcript in the spoken language (never translated) |
| `language` | string | `uz`, `ru` or `en` — the language used for transcription and to pass to `/api/chat` |
| `language_probability` | number | Whisper's probability for that language; near 0 when `uz` was chosen by the exclusion rule |
| `language_forced` | bool | `true` if `?language=` was given |
| `detected_language`, `detected_language_probability` | string, number | Whisper's raw best guess over all its languages (e.g. `hy`, `az` for Uzbek speech) |
| `language_probabilities` | object | probabilities for `uz`, `ru`, `en` |
| `duration` | number | seconds of audio |
| `processing_time` | number | seconds spent decoding, detecting and transcribing |
| `model` | string | `small` |

Example (real response, Russian test clip):

```json
{"ok": true, "text": "Привет. Расскажи мне короткую интересную историю.", "language": "ru",
 "language_probability": 0.9419, "language_forced": false, "detected_language": "ru",
 "detected_language_probability": 0.9419, "language_probabilities": {"uz": 0.0, "ru": 0.9419, "en": 0.0089},
 "duration": 5.14, "processing_time": 3.87, "model": "small"}
```

Errors — `{"ok": false, "error": "…"}` (all observed except `500`):

| Status | When |
|---|---|
| `400` | empty body; bad `Content-Length`; `language` not one of `auto/uz/ru/en`; multipart without a file |
| `413` | body > 25 MB or audio > 180 s |
| `422` | undecodable file (`Audio faylni o'qib bo'lmadi (…)`); shorter than 0.3 s; digitally silent (`Audio jim`); no speech found (`Nutq aniqlanmadi`) |
| `503` | model still loading or failed to load (reason included); or busy (1 running + 2 waiting) |
| `500` | unexpected error (traceback in the server console) |
| `404` | other path |

```powershell
Invoke-RestMethod http://127.0.0.1:8769/api/health
Invoke-RestMethod http://127.0.0.1:8769/api/transcribe -Method Post -InFile .\recording.webm -ContentType 'audio/webm'
curl.exe -s -X POST "http://127.0.0.1:8769/api/transcribe?language=ru" -H "Content-Type: audio/wav" --data-binary "@recording.wav"
curl.exe -s -X POST http://127.0.0.1:8769/api/transcribe -F "file=@recording.webm;type=audio/webm"
```

These four command lines were not executed as written (the tests used a Python client and the browser); the raw-body and multipart upload paths they exercise were tested.
In Windows PowerShell 5.1 the console may show Cyrillic text from `Invoke-RestMethod` incorrectly; the JSON itself is UTF-8.

---

## Ollama (external), port 11434

Not part of this repository. The backend uses only `POST /api/chat`. Useful read-only calls:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version      # {"version":"0.40.3"} on 2026-10-13
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models | Select-Object name   # installed models
(Invoke-RestMethod http://127.0.0.1:11434/api/ps).models   | Select-Object name   # currently loaded
```
