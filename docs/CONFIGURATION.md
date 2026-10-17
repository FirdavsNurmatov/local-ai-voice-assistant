# Configuration

- **Last verified:** 2026-10-13 · **Status:** `SOURCE-CODE CONFIRMED` (line numbers as of this date; they will drift — search for the constant name)
- **Related:** [ARCHITECTURE.md](ARCHITECTURE.md), [API_REFERENCE.md](API_REFERENCE.md)

There is **no configuration file and no `.env`**. Everything is a constant in source code, except
two optional environment variables read by the Kokoro server. Changing a value means editing the
file and restarting that service.

## Environment variables

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `KOKORO_LANGS` | `kokoro_tts_server.py:77` | `en,ru` | Comma-separated languages to load. Unknown values are ignored. A disabled language reports `errors.<lang> = "RuntimeError: KOKORO_LANGS orqali o'chirilgan"` and answers `503`. |
| `KOKORO_SKIP_MEMCHECK` | `kokoro_tts_server.py:79` | unset | `1` disables the free-commit check. Dangerous next to other services. |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | set **by** `kokoro_tts_server.py` (`setdefault` → `1`) | `1` | Forces Hugging Face libraries to use local files only. Exporting `0` beforehand would override it. |
| `PYTHONUTF8` | set by `kokoro_tts_server.py` for its re-launched child | `1` | Part of the Windows UTF-8 workaround. |

No other service reads environment variables (`SOURCE-CODE CONFIRMED`). Ollama has its own variables
(e.g. `OLLAMA_HOST`); none were set at user or machine level on 2026-10-13 (`VERIFIED`).

## `server.py` (chat backend)

| Constant / literal | Line | Value | Meaning |
|---|---|---|---|
| `MODEL_DIR` | 16 | `<repo>/madlad400-3b-ct2-int8` | MADLAD CTranslate2 model folder |
| `OLLAMA_URL` | 17 | `http://127.0.0.1:11434/api/chat` | LLM endpoint |
| `TTS_URL`, `TTS_HEALTH_URL` | 18–19 | `http://127.0.0.1:8766/api/…` | Uzbek TTS (proxy target) |
| `CHAT_MODEL` | 28 | `gemma3:4b` | Ollama model tag (was `QWEN_MODEL = qwen3:1.7b` until 2026-10-17) |
| `HOST` | 21 | `0.0.0.0` | listens on all interfaces |
| `PORT` | 22 | `8765` | |
| `UZ_WORDS` | 24 | ≈ 45 Uzbek words | language-detection keywords |
| `CYRILLIC_TO_LATIN` | 36 | char map | Uzbek output transliteration |
| translator options | 77–80 | `device="cpu"`, `compute_type="int8"`, `inter_threads=1`, `intra_threads=4` | CTranslate2 |
| translate options | 92–94 | `max_decoding_length=128`, `beam_size=1` | output cap and greedy decoding |
| Ollama payload | `run_chat` | `stream=False`, `keep_alive=-1` (`OLLAMA_KEEP_ALIVE`: never unload; was `"10m"` until 2026-10-17), `OLLAMA_OPTIONS` = `num_ctx=2048`, `num_predict=100`, `temperature=0.4`, system prompt | LLM behaviour |
| Model preload | `__main__` | at start a background thread sends an empty chat request with the same options, so Ollama loads `gemma3:4b` before the first question (≈ 12 s) | first-answer latency |
| Ollama timeout | 126 | 180 s | |
| request limits | 188, 198, 226 | body ≤ 100 000 bytes; TTS text ≤ 2000; chat text ≤ 5000 chars | |
| TTS proxy timeout | 203 | 120 s | |
| TTS health timeout | 170 | 1.5 s | |

## `tts_onnx_server.py` (Uzbek TTS)

| Constant | Line | Value |
|---|---|---|
| `TTS_DIR` | 13 | `<repo>/stt-tts-uz` (also added to `sys.path` for the `text` package) |
| `MODEL_PATH` | 14 | `stt-tts-uz/models/vits_uzbek_finetuned.onnx` |
| `CONFIG_PATH` | 15 | `stt-tts-uz/models/uz_tts_base.json` |
| `HOST` / `PORT` | 16–17 | `127.0.0.1` / `8766` |
| `SAMPLE_RATE` | 18, 28 | 22050, overridden by `data.sampling_rate` in the config (also 22050) |
| synthesis parameters | 63–65 | `noise_scale=0.667`, `noise_scale_w=0.8`, `length_scale=1.0` (fixed) |
| limits | 110, 118 | body ≤ 20 000 bytes; text ≤ 2000 chars |

From `uz_tts_base.json`: `text_cleaners = ["uzbek_cleaners"]`, `add_blank = true`, `n_speakers = 0` (single speaker).

## `piper_tts_server.py` (Piper)

| Constant | Line | Value |
|---|---|---|
| `PYTHON` | 9 | `<repo>/.venv-piper/Scripts/python.exe` (interpreter used for `-m piper`) |
| `MODELS` | 10 | `ru → ru_RU-irina-medium.onnx`, `en → en_US-lessac-medium.onnx` (config = same name + `.json`) |
| `PORT` | 14 | `8767`; host `127.0.0.1` is a literal in the last line |
| limits | 52, 63 | body ≤ 20 000 bytes; text ≤ 2000 chars |
| subprocess timeout | 85 | 120 s |

Because the interpreter path is a constant, the server script itself may be started with any Python 3; it always synthesizes with `.venv-piper`.

## `kokoro_tts_server.py` (Kokoro)

| Constant | Line | Value | Meaning |
|---|---|---|---|
| `MODELS_DIR`, `RU_DIR`, `EN_DIR` | 40–42 | `<repo>/kokoro-models[/kokoro-ru|/kokoro-82m]` | model locations |
| `HOST` / `PORT` | 44–45 | `127.0.0.1` / `8768` | |
| `SAMPLE_RATE` | 46 | 24000 | Kokoro output rate |
| `MAX_TEXT` / `MAX_BODY` | 47–48 | 2000 chars / 20 000 bytes | → `413` |
| `MAX_PHONEMES` | 49 | 510 | per-chunk limit for Russian |
| `MAX_WAITING` | 50 | 4 | queued requests behind the running one; more → `503` |
| `SENTENCE_GAP` | 51 | 0.12 s | silence between Russian sentences |
| `VOICES` | 53 | per language: voice name, upstream model id, checkpoint, config, voicepack path, **voicepack SHA256** | changing a voice means changing path **and** hash |
| `REQUIRED_FREE_MB` | 76 | `{"en": 2200, "ru": 4000}` | memory guard thresholds |
| speed clamp | in `do_POST` | 0.5–2.0 | |

## `local_voice_chat.html` (frontend)

| Item | Value |
|---|---|
| Chat / Uzbek TTS / health URLs | relative: `/api/chat`, `/api/tts`, `/api/health` (same origin as the page) |
| Kokoro URL | relative `/api/tts/kokoro` (proxied by `server.py` to `127.0.0.1:8768`; until 2026-10-17 the literal `http://127.0.0.1:8768/api/tts`) |
| Piper URL | relative `/api/tts/piper` (proxied to `127.0.0.1:8767`; until 2026-10-17 the literal `http://127.0.0.1:8767/api/tts`) |
| Default voice system | `<option value="kokoro" selected>` |
| Default chat language | first option, `uz` |
| Voice systems | `kokoro` (Uzbek ONNX + Kokoro RU/EN, default) and `piper` (Uzbek ONNX + Piper RU/EN); no browser voice since 2026-10-17 |
| Sliders | rate 0.65–1.35, volume 0–1 |
| Test sentences | one per language in the `testVoice` handler |

## Start scripts

| Script | What it does |
|---|---|
| `start_tts.ps1` | `Set-Location "C:\local-ai-translator"` (hard-coded), verifies `stt-tts-uz\.venv-tts\Scripts\python.exe` exists, runs `tts_onnx_server.py` |
| `start_kokoro_tts.ps1` | `Set-Location $PSScriptRoot`, runs `.venv-kokoro\Scripts\python.exe -X utf8 kokoro_tts_server.py` |

There are no start scripts for `server.py` or `piper_tts_server.py`.

## Machine-specific values to be aware of

- `C:\local-ai-translator` is hard-coded in `start_tts.ps1` and in several legacy scripts (`chat_int8.py`, `chat_madlad.py`, `test_*.py`, `compare_nllb.py`). The four services themselves resolve paths relative to their own file.
- Each venv's `pyvenv.cfg` records the absolute base interpreter path (`C:\Users\<user>\AppData\Local\Programs\Python\Python312`); venvs are not relocatable.
