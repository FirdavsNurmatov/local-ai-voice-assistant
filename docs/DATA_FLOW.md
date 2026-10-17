# Data flow: from typed text to played audio

- **Last verified:** 2026-10-13 · **Status:** `SOURCE-CODE CONFIRMED`; example values `HISTORICAL TEST RESULT` (2026-10-13)
- **Related source:** `local_voice_chat.html`, `server.py`
- **Related:** [ARCHITECTURE.md](ARCHITECTURE.md), [API_REFERENCE.md](API_REFERENCE.md)

## Stage 0 — page load

1. Browser requests `GET /` from `server.py`; the file `local_voice_chat.html` is read from disk on every request (edits take effect on reload, no restart needed).
2. The page calls `GET /api/health` once and shows `MADLAD-400-3B INT8 + gemma3:4b + Uzbek TTS ✓` or `· TTS ulanmagan`. It does **not** probe Ollama, Piper or Kokoro.

## Stage 1 — user input

- The user types text and presses Enter. The page sends `POST /api/chat` with `{"text": …, "language": <selector>}`.
- The selector ("Suhbat tili": `uz`, `ru`, `en`, `auto`) is transmitted but the backend ignores it. It only affects the "Test ovozi" button.
- While waiting, the send button is disabled (`busy` flag): one request at a time per page.

## Stage 2 — language detection (`detect_language`)

| Input property | Result |
|---|---|
| contains any Cyrillic character | `ru` |
| otherwise, contains a word from `UZ_WORDS` or `oʻ` / `gʻ` | `uz` |
| otherwise | `en` |

Consequences: Uzbek Cyrillic → `ru`; Uzbek Latin without a listed keyword → `en`; any other
Latin-script language → `en`. This single decision controls both translation directions **and**
which voice speaks, so a wrong detection propagates through every later stage.

## Stage 3 — input translation (removed 2026-10-17)

There is no input translation any more: MADLAD mistranslated misspelled or misrecognised Uzbek before the
model saw it ([LLM_COMPARISON.md](LLM_COMPARISON.md)). Until 2026-10-17 MADLAD translated non-English input
with `<2en> {text}`.

## Stage 4 — chat generation

`POST http://127.0.0.1:11434/api/chat` with model `gemma3:4b`, a fixed English system prompt
("Answer in English in 1-3 concise sentences…"; for Uzbek/Russian plus "the user may write in Uzbek or
Russian, possibly with speech-recognition errors; understand the message in that language, but always answer
in English"), the user's original text, `stream: false`, `keep_alive: "10m"`, `num_ctx: 2048`,
`num_predict: 100`, `temperature: 0.4`. No conversation history is sent. Timeout 180 s.

## Stage 5 — output translation

Skipped for `en`. Otherwise MADLAD translates the English answer with `<2ru>` or `<2uz>`.
For `uz` the result is passed through `uzbek_cyrillic_to_latin` (MADLAD may answer in Cyrillic script).

## Stage 6 — response to the browser

```json
{
  "ok": true, "language": "uz", "input": "bir haftada nesha kun bor",
  "answer_english": "Okay, I understand you're asking about the number of days in a week. There are seven days in a week. Would you like to know something else?",
  "answer": "Ha, siz haftada qancha kun borligi haqida soʻrayotganingizni tushundim. Haftada etti kun bor. Yana biror narsani bilishingiz kerakmi?",
  "llm": {"model": "gemma3:4b", "prompt_tokens": …, "output_tokens": …},
  "timings": {"llm": 3.65, "output_translation": 3.99, "total": 7.65}
}
```

(Real response recorded 2026-10-17 on the reference PC; token counts omitted here.) The page renders `answer`, a timing line, and a "▶ Qayta eshitish" (replay) button.

## Stage 7 — speech synthesis

The page calls `speak(answer, language)` without awaiting it. Routing is described in
[ARCHITECTURE.md §3](ARCHITECTURE.md#3-tts-language-routing-and-fallback). Per engine:

| Engine | Request from page | Text processing | Audio returned |
|---|---|---|---|
| Uzbek ONNX | `POST /api/tts {text}` → proxied to 8766 | drop unknown symbols → `uzbek_cleaners` → symbol ids with blanks | WAV, 22 050 Hz, mono, 16-bit PCM |
| Kokoro EN | `POST :8768/api/tts {text, language:"en", speed}` | misaki English G2P (espeak fallback), chunked by `KPipeline` | WAV, 24 000 Hz, mono, 16-bit PCM |
| Kokoro RU | `POST :8768/api/tts {text, language:"ru", speed}` | sentence split → RUAccent stress → respelling → espeak-ng → vowel reduction → ≤ 510 phonemes per chunk, 0.12 s gap between sentences | WAV, 24 000 Hz, mono, 16-bit PCM |
| Piper | `POST :8767/api/tts {text, language}` | Piper's own espeak-ng phonemization (inside the CLI) | WAV, 22 050 Hz (model config; mono 16-bit `NOT VERIFIED` by header in this audit) |

Sample-rate/format facts for Uzbek and Kokoro were verified by parsing the WAV headers on 2026-10-13.

## Stage 8 — playback

The WAV bytes become a `Blob` → `URL.createObjectURL` → `new Audio(url).play()`. On `ended` the URL
is revoked. "■ To‘xtatish" stops the HTML audio. Starting a new `speak()` stops whatever is playing.
UI sliders: **volume** applies to Kokoro and Piper audio (not Uzbek ONNX); **rate** applies to Kokoro
(`speed`) only. (The browser voice and its pitch slider were removed on 2026-10-17.)

## What is stored

Nothing is persisted by the application: no database, no chat history, no audio files (Piper uses
a temp directory deleted after each request). Console output of the services contains request
lines and, for TTS, character counts; the Uzbek TTS server prints the **full text** of a request
when synthesis fails (`[TTS ERROR] Matn: …`). If console output is redirected to files, treat
those files as potentially containing user text.
