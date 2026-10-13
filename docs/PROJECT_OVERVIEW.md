# Project overview

- **Last verified:** 2026-10-13 · **Status:** `VERIFIED` (inventory), purposes `SOURCE-CODE CONFIRMED`
- **Related:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md)

## Purpose

A local voice-chat assistant for Uzbek, Russian and English. The user types a message in a
browser; the system answers in the same language, as text and as synthesized speech. A small LLM
that is only prompted in English is used, so non-English messages are translated in and out.

Evidence of the intended use case: the Uzbek keyword list and benchmark sentences in the source
revolve around a library-assistant robot ("kutubxona", "robot", "mehmonlar"). This is an
inference from `server.py` and `benchmarks/`; no written requirements document exists (`NOT VERIFIED`).

## What is active

Only these files take part in the running system (`SOURCE-CODE CONFIRMED`):

| File | Role |
|---|---|
| `local_voice_chat.html` | Single-page frontend (HTML + inline CSS + inline JS, no build step, no external assets) |
| `server.py` | Chat backend: serves the page, language detection, MADLAD translation, Ollama call, Uzbek TTS proxy |
| `tts_onnx_server.py` | Uzbek VITS ONNX TTS service |
| `piper_tts_server.py` | Piper TTS service (Russian, English) |
| `kokoro_tts_server.py` | Kokoro TTS service (English `af_heart`, Russian `masha`) |
| `start_tts.ps1` | Starts the Uzbek TTS service |
| `start_kokoro_tts.ps1` | Starts the Kokoro TTS service |
| `stt-tts-uz\text\` | Text cleaner / symbol table imported by `tts_onnx_server.py` |
| `stt-tts-uz\models\` | Uzbek model and its config |
| `madlad400-3b-ct2-int8\` | Translation model |
| `ru_RU-irina-medium.onnx(.json)`, `en_US-lessac-medium.onnx(.json)` | Piper voices |
| `kokoro-models\` | Kokoro weights, voicepacks, Russian G2P and espeak data |

## Full top-level inventory (`VERIFIED` 2026-10-13)

| Path | Size | Kind | Notes |
|---|---|---|---|
| `server.py` | 9.8 KB | active source | |
| `tts_onnx_server.py` | 5.4 KB | active source | |
| `piper_tts_server.py` | 4.5 KB | active source | |
| `kokoro_tts_server.py` | 15 KB | active source | |
| `local_voice_chat.html` | 19 KB | active source | |
| `start_tts.ps1`, `start_kokoro_tts.ps1` | <1 KB | active scripts | |
| `KOKORO_TTS.md` | 4.8 KB | earlier notes (Uzbek) | superseded by `docs/` |
| `README.txt` | 2.1 KB | legacy install note | predates Piper and Kokoro; says RU/EN use browser TTS, which is no longer the default |
| `.venv\` | 879 MB | Python env | chat backend |
| `.venv-piper\` | 157 MB | Python env | Piper CLI |
| `.venv-kokoro\` | 1807 MB | Python env | Kokoro; includes 693 MB of RUAccent models |
| `stt-tts-uz\` | 659 MB | nested git repo (third party) + env + model | origin `github.com/3936010/STT-TTS-Uz`, commit `a2d726f`, **locally modified** (see [patches/](patches/README.md)) |
| `madlad400-3b-ct2-int8\` | 2839 MB | model | active |
| `kokoro-models\` | 635 MB | models | active |
| `ru_RU-irina-medium.onnx`, `en_US-lessac-medium.onnx` (+`.json`) | 63 MB each | models | active (Piper) |
| `nllb-int8\` | 600 MB | model | **legacy** – NLLB-200 experiment, not used by any service |
| `Uzbek_TTS-test\` | 7111 MB | nested git repo + its own `.venv` + checkpoints | **legacy experiment**, origin `github.com/Saidakmal02/Uzbek_TTS`, locally modified; not used by any service |
| `tts-test-code\` | <1 MB | nested git repo | **legacy experiment**, origin `github.com/firdavsus/T5-speech`; not used |
| `benchmarks\` | 10 KB | CSV results | NLLB vs MADLAD translation comparison |
| `chat.py`, `chat_int8.py`, `chat_int8_nllb_backup.py`, `chat_madlad.py` | 3–6 KB | legacy CLI prototypes | earlier terminal versions of the chat loop (NLLB → NLLB INT8 → MADLAD). `chat_int8.py` and `chat_int8_nllb_backup.py` are byte-identical |
| `benchmark_translation.py`, `compare_nllb.py` | | legacy scripts | produced `benchmarks\` |
| `test_translate.py`, `test_int8.py`, `test_madlad*.py`, `test_translit.py` | ~1 KB each | ad-hoc experiment scripts | **not** an automated test suite; several hard-code `C:\local-ai-translator\…` |
| `local_voice_chat.html.before_piper.bak`, `…before_kokoro.bak`, `server.py.before_auto_language.bak` | | backups | snapshots taken before earlier changes |
| `kokoro-test-output\` | 9 MB | WAV test outputs | from the 2026-10-13 Kokoro tests |
| `test_en.wav`, `test_ru.wav`, `test_ru.txt`, `piper_api_test.wav` | | test artifacts | Piper trials |
| `logs\` | 1 KB | logs | only `kokoro_tts.out.log` is non-empty; contains request lines, **no user text** |
| `docs\`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `.gitignore` | | documentation | created 2026-10-13 |

Discrepancies with the previously "known" list: there is no root `requirements.txt`, no `.env`,
and no test suite (`VERIFIED`). At audit time there was also no `LICENSE` and the root was not a git
repository; both were added later the same day (MIT license, GitHub repository).

## Supported languages

| Language | Input detection | Translation | TTS |
|---|---|---|---|
| English | default when nothing else matches | none (passes through) | Kokoro `af_heart` / Piper `lessac` / browser |
| Russian | any Cyrillic character | MADLAD `<2en>` / `<2ru>` | Kokoro `masha` / Piper `irina` / browser |
| Uzbek (Latin) | keyword list or `oʻ` / `gʻ` | MADLAD `<2en>` / `<2uz>` + Cyrillic→Latin conversion | VITS ONNX |

Uzbek written in Cyrillic is detected as Russian (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).

## Non-goals / not implemented

Speech-to-text, conversation history (each request is independent: only system prompt + current
message are sent to Ollama), streaming responses, authentication, multi-user handling, GPU inference.
