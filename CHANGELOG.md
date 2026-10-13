# Changelog

The project was put under version control on 2026-10-13. Everything before that is
**reconstructed** from file modification times on the reference machine, backup files, and the
recorded work of 2026-10-13 — inferences from timestamps and file contents, not from commit history.
No version numbers have been assigned.

## 2026-10-13 — First publication

- Repository created at <https://github.com/FirdavsNurmatov/local-ai-voice-assistant> with an MIT `LICENSE`.
- Sources, start scripts, documentation and legacy experiment scripts committed; environments,
  model weights, audio, logs, backups and the nested third-party repositories are excluded by `.gitignore`.

## 2026-10-13 — Documentation

- Added `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `.gitignore` and the `docs/` tree
  (architecture, API reference, runbook, memory, testing, troubleshooting, security, licensing, decisions, ADRs).
- Added `docs/requirements/*.freeze.txt` (`pip freeze --all` of the four environments) and
  `docs/patches/stt-tts-uz-text-cleaners.patch` (export of the existing local modification).
- No application source file was changed by this work.

## 2026-10-13 — Kokoro TTS integration

- Added `kokoro_tts_server.py` (port 8768): English `af_heart` (Kokoro-82M) and Russian `masha` (Kokoro-RU);
  background loading, per-language readiness, voicepack SHA256 check, inference lock and queue limit,
  UTF-8 re-launch workaround for Windows.
- Added memory guard (`REQUIRED_FREE_MB`), `KOKORO_LANGS`, `KOKORO_SKIP_MEMCHECK` after the first
  full load coincided with the other three services stopping.
- Added `start_kokoro_tts.ps1`, `.venv-kokoro\`, `kokoro-models\`, `kokoro-test-output\`, `logs\`, `KOKORO_TTS.md`.
- `local_voice_chat.html`: new default voice system "UZ + Kokoro RU Masha / EN Heart"; Kokoro → Piper
  fallback for Russian/English; playback errors no longer trigger fallback; help text updated.
  Previous version kept as `local_voice_chat.html.before_kokoro.bak`.

## 2026-10-13 (earlier) — Piper server and auto language detection

- Added `piper_tts_server.py` (port 8767) and a "UZ + Piper RU/EN" mode in the page (file times ≈ 21:40–22:00).
- `server.py`: the backend now always detects the language itself; previously it honoured the
  language chosen in the page when it was `uz`/`ru`/`en` (one-line difference from `server.py.before_auto_language.bak`).

## 2026-10-12 — Local Uzbek TTS and browser UI; Piper voices

- `server.py`, `local_voice_chat.html`, `tts_onnx_server.py`, `start_tts.ps1`, `README.txt`: browser chat
  with a fine-tuned Uzbek VITS ONNX voice behind a `/api/tts` proxy (files dated 00:57–01:13).
- `stt-tts-uz\` cloned; `.venv-tts` created; `text/cleaners.py` patched to make `phonemizer` optional.
- Piper environment and voices downloaded (`ru_RU-irina-medium`, `en_US-lessac-medium`, ≈ 19:35); CLI tests (`test_ru.wav`, `test_en.wav`).

## 2026-10-11/12 — Translation prototypes

- `test_translate.py`, `chat.py`: NLLB-200 distilled 600M (transformers) + Ollama `qwen3:1.7b` in a terminal loop.
- `test_int8.py`, `chat_int8.py`, `nllb-int8\`: NLLB converted to CTranslate2 INT8.
- `test_madlad*.py`, `chat_madlad.py`, `madlad400-3b-ct2-int8\`: MADLAD-400 3B INT8; Uzbek Cyrillic→Latin transliteration (`test_translit.py`).
- `benchmark_translation.py`, `compare_nllb.py`, `benchmarks\*.csv`: NLLB vs MADLAD comparison.
