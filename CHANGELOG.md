# Changelog

The project was put under version control on 2026-10-13. Everything before that is
**reconstructed** from file modification times on the reference machine, backup files, and the
recorded work of 2026-10-13 — inferences from timestamps and file contents, not from commit history.
No version numbers have been assigned.

## 2026-10-17 — LLM pipeline comparison (evaluation)

- `server.py` (evaluation version): `CHAT_MODEL` env (default still `qwen3:1.7b`); request flags
  `dual_input` (the LLM also sees the original text next to the MADLAD translation; `CHAT_DUAL_INPUT`) and
  `direct_input` (no input translation, the LLM reads the original and answers in English for MADLAD;
  `CHAT_DIRECT_INPUT`); `think:false` sent only to Qwen3; response has `llm` token counts.
  Backups: `server.py.before_navai.bak`, `server.py.before_dual_input.bak`.
- `stt-eval/dual_input/`: first dual-input experiment (qwen3:1.7b; no gain).
- `stt-eval/llm_compare/`: qwen3:1.7b, qwen3:4b-instruct and gemma3:4b × madlad / dual / hybrid / direct on
  25 Uzbek questions (clean + STT text), 20 Russian, 20 English, 12 robot commands (clean + STT); the
  Qwen3-4B Thinking model on 17 Uzbek questions. Scripts `llm_compare*.py/ps1`, `command_compare*.py/ps1`,
  `llm_compare_report.py`. Winner: gemma3:4b with the hybrid pipeline (see
  `docs/LLM_COMPARISON.md`).

## 2026-10-16 — NavAI Uzbek STT integrated

- `stt_server.py`: Uzbek routing. `?language=uz` → `navai-whisper-small-uzbek` (CT2 int8; no prompt,
  `without_timestamps=True`, `no_repeat_ngram_size=4`, no language detection). `?language=ru|en` and
  Russian/English in auto mode stay on the base `small` model with unchanged settings. Auto mode uses NavAI
  only when the base model says Uzbek and p(ru), p(en) < 0.2. NavAI is loaded on first use after a SHA256
  check; memory policy `auto` keeps both models when ≥ 3 GB commit is free, otherwise swaps; any NavAI
  problem falls back to the previous behaviour (`/api/health` → `uz_model`). Switches: `STT_UZ_MODEL`,
  `STT_UZ_MEMORY`, `STT_UZ_PRELOAD`, `STT_UZ_AUTO_MAX_RUEN`, `STT_UZ_REQUIRED_FREE_MB`.
  Backup: `stt_server.py.before_navai.bak`.
- `local_voice_chat.html`: STT language selector next to the microphone (Avto / O‘zbekcha / Русский / English;
  default Avto = previous behaviour); "(tanlangan)" shown for a chosen language. Backup: `local_voice_chat.html.before_navai.bak`.
- Tests (`stt-eval/integration/`): Russian/English and edge cases identical to the pre-integration code
  (52/52); 40 new FLEURS Uzbek recordings WER 1.164 → 0.223; synthetic robot commands WER 3.70 → 0.91
  (still unreliable); real service identical to the test process (111/111). Not tested: male voices.
  iPhone Safari through the HTTPS tunnel was tested by the owner on 2026-10-16 (works). STT next to chat +
  Ollama on the 8 GB PC exceeds the measured memory budget; the owner accepted the risk and runs them together.
- Docs: `docs/STT.md`, `docs/API_REFERENCE.md` (backups `*.before_navai.bak`).

## 2026-10-14 — Uzbek STT evaluation and hardware notes (no production change)

- Evaluated `navai-uz/whisper-small-uzbek` (CTranslate2 int8) against the production Faster-Whisper `small`
  on 120 real human Uzbek recordings (FLEURS test), 12 synthetic Uzbek clips and 8 synthetic RU/EN clips,
  on CPU and on the GTX 1650. Result: Uzbek WER 1.24 → 0.21–0.26 with NavAI, no repetition, lower latency
  and memory; NavAI cannot handle Russian/English. Recommendation: NavAI for Uzbek only (not implemented).
- Added `docs/STT_EVALUATION.md`, `docs/STT_EVALUATION_REPRODUCE.md`, the `stt-eval/` scripts, dataset lists,
  raw run outputs, per-sample and summary CSVs, checksum manifest and pinned evaluation requirements.
- `docs/STT.md`, `docs/API_REFERENCE.md`: evaluation summary and the proposed routing, clearly marked as not implemented
  (backups `*.before_eval.bak`).
- `README.md`: "Hardware and expected performance" section — measured results on the reference PC and
  estimates for an Ubuntu server (i7-13700, 64 GB RAM, RTX 4060 8 GB). Backup `README.md.before_hardware.bak`.

## 2026-10-14 — STT through `server.py` (iPhone / HTTPS tunnel)

- `server.py`: new `POST /api/transcribe` (forwards audio, `Content-Type` and `?language=` to
  `127.0.0.1:8769`) and `GET /api/stt/health`. Existing routes unchanged. Backup: `server.py.before_stt_proxy.bak`.
- `local_voice_chat.html`: STT requests go to the page's own origin (`/api/transcribe`); `audio/mp4`
  (iPhone Safari) added to accepted recorder types; header shows STT status. Backup: `local_voice_chat.html.before_stt_proxy.bak`.

## 2026-10-14 — Speech-to-text

- Added `stt_server.py` (port 8769): Faster-Whisper `small`, CPU, int8, background loading, raw or
  multipart upload, language mapped to `uz`/`ru`/`en`, Uzbek-specific decoding options, VAD filter,
  queue limit, memory check. Added `start_stt.ps1`, `.venv-stt\`, `stt-models\` (not in git), `docs/STT.md`,
  `docs/requirements/stt-venv.freeze.txt`.
- `local_voice_chat.html`: microphone button (record → transcribe → insert into the message box for
  review); the detected language is sent with the next chat request; typed messages now send
  `language: "auto"`. **Kokoro mode no longer falls back to Piper** — the real Kokoro error is shown.
  Previous version: `local_voice_chat.html.before_stt.bak`.
- `server.py`: `run_chat` honours an explicit `language` of `uz`/`ru`/`en` again, otherwise detects
  from the text (one line). Previous version: `server.py.before_stt.bak`.
- Measured: Russian/English WER 0.00 on synthetic test speech; Uzbek WER 0.56–1.00; STT ≈ 2.6 GB commit;
  chat + STT + Kokoro do not fit together on the reference machine. Not yet tested with a real microphone.

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
