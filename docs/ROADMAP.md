# Roadmap

- **Last verified:** 2026-10-13
- **Related:** [KNOWN_ISSUES.md](KNOWN_ISSUES.md), [DECISIONS.md](DECISIONS.md), [TESTING.md](TESTING.md)

Nothing in sections 3–4 has been implemented. Item numbers `K…` refer to [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## 1. Implemented and verified (manual tests, 2026-10-13)

- Browser chat UI served by `server.py`; English chat round-trip through Ollama `qwen3:1.7b`.
- Uzbek ONNX TTS, directly and through the backend proxy; valid 22.05 kHz audio.
- Piper TTS for Russian and English; valid audio.
- Kokoro TTS: English `af_heart` and Russian `masha` produce valid 24 kHz audio; correct voice per language; error handling; queue limit; background loading; CORS.
- Russian G2P (stress, `ё`, homographs, numbers) at phoneme level.
- Memory guard: Russian refused with a clear error when commit is short; other services unaffected afterwards.
- Frontend routing: `en` → Kokoro, `ru` → Kokoro with Piper fallback, `uz` → ONNX; audio actually played in a browser.

## 2. Implemented but not fully verified

| Item | What is missing |
|---|---|
| Russian and Uzbek chat through the full pipeline | not re-tested in the latest session (worked in earlier use according to the project history; no recorded result) |
| `masha` played from the browser | only tested over HTTP; in the browser test Russian fell back to Piper |
| `KOKORO_LANGS=ru` / `en` single-language modes | code path exists, never run |
| Kokoro long-text chunking quality (sentence gaps, comma splits) | produced audio; not listened to |
| Behaviour under concurrent chat requests | MADLAD is locked; Ollama and Uzbek TTS concurrency untested |
| Other browsers, LAN clients | only one Chromium-based browser on the server machine |
| Rebuilding environments from `docs/requirements/` | never replayed |
| The smoke-test script in `TESTING.md` | written, not executed |
| Cause of the 2026-10-13 multi-service crash | attributed to commit exhaustion, unproven |

## 3. Known limitations

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md). The ones that shape the roadmap: memory ceiling (K1–K4),
heuristic language detection ignoring the selector (K7–K9), no streaming (K16), loopback-only
Kokoro/Piper from the page (K14), no automated tests (K36), unrecorded provenance (K40).

## 4. Proposed improvements (`PROPOSED`)

### Memory

- **Reduce RUAccent memory.** It is the largest part of the Russian stack (≈ 2.2 GB). Candidates to measure: smaller homograph model via the existing `omograph_model_size` parameter of `RuG2P`; ONNX Runtime session options (memory arena); whether the full dictionary is required. Each changes stress accuracy and must be evaluated against the upstream 15/16 orthoepy set first.
- Evaluate the ONNX/quantized exports published in the same `kokoro-ru` repository (138 MB q8) and an ONNX build of Kokoro-82M instead of two PyTorch models. This is a model-format change and needs an explicit decision.
- Find out why `server.py` commits ≈ 9.9 GB (K4); a fix there would free more than any TTS optimization.
- Memory-aware orchestration: a single launcher that starts services in order, checks commit before each, and reports what was skipped; optional re-check/late loading of Russian when memory becomes available (K2, K3).

### Language handling

- Honour the page's language selector when it is not `auto` (K7).
- Replace the keyword heuristic with a proper language identifier, or at least distinguish Uzbek Cyrillic from Russian (K8, K9).
- Raise or make configurable the 128-token translation cap; warn on truncation (K10).

### TTS latency and quality

- Sentence-level streaming or chunked playback so the first sentence plays while the rest is generated (K16).
- Keep a Piper voice loaded in-process instead of spawning the CLI per request (K17).
- Measure voice quality: ASR round-trip (WER) and a small listening test for `masha`, `af_heart`, the Uzbek voice (K24).
- Number/abbreviation normalization for Uzbek (K20).

### Robustness and operations

- ~~Same-origin proxy for Kokoro and Piper~~ — done 2026-10-17 (K14). Still open: tighten Kokoro/Piper CORS (K32).
- Truthful aggregate health endpoint (Ollama, all TTS engines) and periodic refresh in the page (K28–K31).
- Log files with rotation; a start/stop script set; optional Windows service wrappers (K34).
- Proper HTTP status codes in Piper and `server.py` (K18, K33).

### Engineering

- ~~Put the project root under git; choose a license (K37, K38).~~ Done 2026-10-13 (MIT, GitHub).
- Automated tests: pure-function unit tests (`detect_language`, `uzbek_cyrillic_to_latin` — requires moving them out of the module that loads MADLAD), HTTP contract tests per service, WAV validity checks, one end-to-end test (K36).
- Reproducible setup script that downloads pinned model revisions and verifies hashes; record the missing provenance (K40).
- Move legacy experiments to a `legacy/` folder or remove them from the working tree (K41).
- Speech-to-text input (the UI text already says it is not implemented).
