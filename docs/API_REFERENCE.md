# API reference

- **Last verified:** 2026-10-13 · **Status:** routes and schemas `SOURCE-CODE CONFIRMED`; responses marked ✔ were also observed in tests on 2026-10-13 (`HISTORICAL TEST RESULT`)
- **Related source:** `server.py`, `tts_onnx_server.py`, `piper_tts_server.py`, `kokoro_tts_server.py`
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
| `language` | string | no | default `"auto"`; **accepted but ignored** |

Response `200` ✔:

| Field | Type | Notes |
|---|---|---|
| `ok` | bool | `true` |
| `language` | string | detected: `"ru"`, `"uz"` or `"en"` |
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

## Ollama (external), port 11434

Not part of this repository. The backend uses only `POST /api/chat`. Useful read-only calls:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version      # {"version":"0.40.3"} on 2026-10-13
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models | Select-Object name   # installed models
(Invoke-RestMethod http://127.0.0.1:11434/api/ps).models   | Select-Object name   # currently loaded
```
