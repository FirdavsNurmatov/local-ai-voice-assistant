# ADR 0002 — Language-specific TTS routing with client-side fallback

- **Status:** Accepted (implemented 2026-10-13)
- **Evidence level:** `SOURCE-CODE CONFIRMED`; requirements from the recorded Kokoro integration brief of 2026-10-13
- **Related:** [../ARCHITECTURE.md](../ARCHITECTURE.md#3-tts-language-routing-and-fallback), [../DECISIONS.md](../DECISIONS.md) (D5–D8, D11, D12)

## Context

No single local engine covers the three languages well: the Uzbek voice is a dedicated VITS model;
Kokoro has no Uzbek voice; Piper voices were already installed for Russian and English. The project
owner asked for `masha` (Kokoro-RU) for Russian and `af_heart` (Kokoro-82M) for English, with the
Uzbek ONNX service untouched, Piper kept as a fallback, minimal frontend changes and no backend changes.

## Decision

Route by the language the backend reports for each answer, in the browser's `speak()` function:

| Language | Engine order |
|---|---|
| `uz` | Uzbek ONNX (via backend proxy) — no fallback |
| `ru` | Kokoro `masha` → Piper `irina` |
| `en` | Kokoro `af_heart` → Piper `lessac` |

- A "voice system" selector keeps the older modes (`local`, `browser`, `piper`) available; `kokoro` is the default.
- Fallback to Piper happens when Kokoro cannot be reached or answers non-200 (including `503` when a voice is not loaded). The user sees the reason.
- A *playback* error after audio was received does not trigger fallback (the engine worked; retrying another engine would not help).
- All TTS servers accept the same request shape `{text, language}` and return a WAV body, so the page code is identical per engine.

## Consequences

Positive

- Best available voice per language, degrading gracefully instead of going silent.
- The backend and the Uzbek service did not need to change.

Negative

- Routing logic lives in the page: other clients must re-implement it; the backend cannot report or log which voice spoke.
- Kokoro/Piper are addressed as `127.0.0.1` from the browser → they only work on the server machine, and both servers need permissive CORS.
- A conversation can switch voices between messages (Kokoro ↔ Piper) depending on load state.
- Uzbek has no second option.

## Alternatives considered

- Proxying Kokoro/Piper through `server.py` like the Uzbek TTS — rejected for now because `server.py` was not to be modified; recommended later ([../ROADMAP.md](../ROADMAP.md)).
- Automatic per-language routing with no selector — rejected to keep existing modes and Piper selectable.

## Open questions

- Should the page learn Kokoro's readiness up front (health probe) instead of discovering it by a failed request each time?
- Should the browser voice be a last-resort fallback?
