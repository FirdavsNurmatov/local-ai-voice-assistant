# Known issues and limitations

- **Last verified:** 2026-10-13
- **Status:** each item is tagged. `CODE` = follows from the current source (`SOURCE-CODE CONFIRMED`); `OBSERVED` = seen on 2026-10-13 (`HISTORICAL TEST RESULT`); `UNVERIFIED` = suspected only.
- **Related:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [ROADMAP.md](ROADMAP.md)

## Memory

| # | Issue | Tag |
|---|---|---|
| K1 | The complete system does not fit the 8 GB reference machine; Russian `masha` normally does not load while `server.py` runs. | OBSERVED |
| K2 | Only the Kokoro server checks memory. `server.py`, the Uzbek TTS and Ollama load unconditionally and can be the ones that fail. | CODE |
| K3 | Kokoro's memory check runs once at start; no retry, no unloading, no re-check before inference. | CODE |
| K4 | `server.py` commits ≈ 9.9 GB for a 2.8 GB model; reason unknown. | OBSERVED / cause UNVERIFIED |
| K5 | A duplicate start of `server.py` or the Uzbek TTS loads the whole model before failing on the busy port. | CODE |
| K6 | The 2026-10-13 crash of three services is attributed to commit exhaustion without proof. | UNVERIFIED |

## Language detection and translation

| # | Issue | Tag |
|---|---|---|
| K7 | *Changed 2026-10-14:* the backend now honours `language` = `uz`/`ru`/`en`, but the page sends it only for transcribed speech; for typed text it sends `auto`, so the "Suhbat tili" selector still does not control typed chat. | CODE |
| K8 | Any Cyrillic text is treated as Russian — including Uzbek, Kazakh, Tajik, Ukrainian… | CODE |
| K9 | Uzbek (Latin) is recognized only via ≈ 45 keywords or `oʻ`/`gʻ`; otherwise the text is treated as English and sent to the LLM untranslated. | CODE |
| K10 | Translation output is capped at 128 tokens and decoded greedily; long inputs/answers are truncated without warning. | CODE |
| K11 | Uzbek answers are transliterated by a character map with two hard-coded word fixes; mixed-script or Russian words inside an Uzbek answer are transliterated too. | CODE |
| K12 | No conversation memory: every message is answered in isolation. | CODE |
| K13 | LLM answers are limited to 100 tokens and "1–3 sentences" by the prompt. | CODE |

## TTS

| # | Issue | Tag |
|---|---|---|
| K14 | Kokoro and Piper URLs are hard-coded to `127.0.0.1` in the page: from another device these voices fail (the page itself and Uzbek TTS still work over the LAN). | CODE |
| K15 | The friendly message "server ishlamayapti (8768)" appears only when the browser's error text is exactly `Failed to fetch` (Chromium). Firefox reports `NetworkError when attempting to fetch resource.`, shown verbatim. Cosmetic. | CODE |
| K16 | No streaming: time to first audio equals full synthesis time (≈ 56 s for a 1 920-character English text). | OBSERVED |
| K17 | Piper reloads its model on every request (3–5 s for one sentence). | CODE + OBSERVED |
| K18 | Piper returns `422` for every kind of error, including server-side faults and timeouts. | CODE |
| K19 | The Uzbek TTS has no lock around inference and no queue limit; concurrent requests run in parallel on one ONNX session. Not stress-tested. | CODE / effect UNVERIFIED |
| K20 | The Uzbek TTS silently removes characters outside its symbol table (digits, other scripts) — numbers are not read out. Exact symbol set not documented here. | CODE / extent UNVERIFIED |
| K21 | Uzbek TTS failure has no fallback voice; the page only shows an error. | CODE |
| K22 | The volume slider does not affect Uzbek ONNX audio; rate affects only Kokoro and the browser voice; pitch only the browser voice. | CODE |
| K23 | Russian homograph resolution is imperfect (upstream: 93.8 %); upstream also documents a darker timbre and fricative artifacts. | upstream claim, UNVERIFIED locally |
| K24 | Voice quality/naturalness has never been measured (no listening test, no ASR round-trip). | — |
| K25 | *Superseded 2026-10-14:* Kokoro mode never falls back to Piper any more (see K51). K15 no longer applies: both browsers' network-error texts are now mapped to "server ishlamayapti (8768)". | CODE (by design) |
| K26 | `ru_g2p.py` fails on non-UTF-8 Windows locales unless Python runs in UTF-8 mode (worked around in the server). | OBSERVED |
| K27 | `tts_onnx_server.py` contains a stray `from email.mime import text` (harmless, shadowed on the next import). | CODE |

## Speech-to-text (added 2026-10-14, details in [STT.md](STT.md))

| # | Issue | Tag |
|---|---|---|
| K43 | Uzbek recognition with Whisper `small` is not usable: WER 0.56–1.00 on five synthetic clips; "Rahmat." was not recognised. Russian and English: WER 0.00 on the same kind of clips. | OBSERVED |
| K44 | Whisper `small` does not identify Uzbek (labels it `hy`/`az`/`en`); the service assigns `uz` by exclusion, so any non-Russian/English or unclear speech becomes `uz`. | OBSERVED + CODE |
| K45 | STT commits ≈ 2.6 GB (RSS ≈ 0.4 GB). Chat + STT + Kokoro cannot be loaded together on the reference machine. | OBSERVED |
| K46 | `stt_server.py`'s load guard (`REQUIRED_FREE_MB = 1200`) is lower than the measured need (≈ 2.6 GB). | CODE vs OBSERVED |
| K47 | STT was tested only with TTS-generated speech and a simulated microphone stream; no human recording, no real microphone. | VERIFIED (absence) |
| K48 | ≈ 3.5 s minimum latency per utterance (language detection ≈ 1.7 s + decoding), even for one word. | OBSERVED |
| K49 | `faster-whisper 1.2.1` breaks with PyAV ≥ 17; `.venv-stt` pins `av 16.1.0`. Two pip leftover folders (`~v`, `~v.libs`) remain in its `site-packages`. | OBSERVED |
| K50 | STT, like Kokoro/Piper, is called at `127.0.0.1` from the page; microphone capture additionally requires a `localhost`/HTTPS origin. | CODE |
| K51 | Since 2026-10-14 Kokoro mode has no fallback voice: when a Kokoro voice is not loaded (the usual case for Russian, and for English too when STT is running), answers in that language are shown but not spoken. | CODE + OBSERVED |

## Health, operations, security

| # | Issue | Tag |
|---|---|---|
| K28 | `GET :8765/api/health` always says `ok:true` and never checks Ollama, Piper or Kokoro. | CODE |
| K29 | Piper's health endpoint is static (does not check models or the venv). | CODE |
| K30 | Kokoro's `ok` is `false` whenever any enabled language is missing, even though English works; clients must read `ready`. | CODE |
| K31 | The page probes health only once, at load. | CODE |
| K32 | `server.py` listens on all interfaces without authentication; Piper/Kokoro allow any CORS origin. | CODE |
| K33 | Malformed JSON to `server.py` returns `500` instead of `400`. | CODE |
| K34 | No log files, no supervisor, no auto-restart; closing a window stops a service. | CODE |
| K35 | `start_tts.ps1` hard-codes `C:\local-ai-translator`. | CODE |

## Project hygiene

| # | Issue | Tag |
|---|---|---|
| K36 | No automated tests, no CI. | VERIFIED |
| K37 | *Resolved 2026-10-13:* the root is now a git repository (history before that date exists only as local `.bak` files). | VERIFIED |
| K38 | *Resolved 2026-10-13:* MIT `LICENSE` for the project's own code. | VERIFIED |
| K39 | Runtime depends on a third-party repository without a license (`stt-tts-uz`) carrying an uncommitted local patch. | VERIFIED |
| K40 | Provenance of the MADLAD conversion, the Uzbek model and the Piper voice downloads is not recorded. | VERIFIED (absence) |
| K41 | ≈ 7.7 GB of unused legacy material sits in the working directory (`Uzbek_TTS-test\`, `nllb-int8\`). | VERIFIED |
| K42 | `README.txt` and the in-page help text partly describe older behaviour (e.g. "STT hali qo‘shilmagan" is still true; the header subtitle still says "brauzer yoki mahalliy Uzbek ONNX TTS"). | VERIFIED |
