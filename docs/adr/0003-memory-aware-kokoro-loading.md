# ADR 0003 — Memory-aware, per-language model loading in the Kokoro server

- **Status:** Accepted (implemented 2026-10-13)
- **Evidence level:** behaviour `SOURCE-CODE CONFIRMED`; motivation from measurements and an incident on 2026-10-13 (`HISTORICAL TEST RESULT`; root cause of the incident unproven)
- **Related source:** `kokoro_tts_server.py` — `REQUIRED_FREE_MB`, `free_commit_mb()`, `load_models()`, `ENABLED`, `SKIP_MEMCHECK`
- **Related:** [../MEMORY_AND_PERFORMANCE.md](../MEMORY_AND_PERFORMANCE.md), [../DECISIONS.md](../DECISIONS.md) (D10)

## Context

Loading both Kokoro languages commits ≈ 5.5 GB (the Russian front end, RUAccent, being the largest
part). On the reference machine `server.py` already commits ≈ 9.9 GB of an 18.4 GB limit. When the
first, unguarded Kokoro server loaded everything, the three other services stopped; the most
likely cause is exhausted system commit. The requirement was: do not break the working services,
load models at start-up (not per request), and do not silently substitute a different model.

## Decision

1. **Check before loading.** Before each language, read the commit available to the process (`GlobalMemoryStatusEx().ullAvailPageFile`). Load only if it is at least `REQUIRED_FREE_MB[lang]` — 2200 MB for English, 4000 MB for Russian.
2. **Languages are independent.** A language that cannot load is marked not ready with an explanatory error; the other still serves.
3. **Fixed order English → Russian** (also required so that English espeak initialises before the Russian espeak data path is set).
4. **Report, do not hide.** `/api/health` exposes `ready`, `errors`, `free_commit_mb`, `memory_mb`; `/api/tts` for an unavailable language returns `503` with the same message, which the page shows before falling back to Piper.
5. **Bind first, load in the background**, so a port clash fails before memory is spent and health is observable during loading.
6. **Escape hatches:** `KOKORO_LANGS` to choose languages; `KOKORO_SKIP_MEMCHECK=1` to bypass the check knowingly.
7. Serialize inference with a lock and cap the queue (1 running + 4 waiting) to bound per-request memory.

## Consequences

Positive

- The Kokoro server can no longer be the cause of commit exhaustion at start-up.
- Partial availability (English only) instead of all-or-nothing.
- The reason Russian is missing is visible to the operator and the user.

Negative

- On the reference machine Russian `masha` is normally unavailable.
- The check is a one-time snapshot: other processes can consume memory afterwards; nothing is re-checked or unloaded; a later improvement in free memory needs a manual restart.
- Thresholds are estimates from one machine and one version set; larger inputs or other library versions may need more.
- Only this service is guarded; the others still load unconditionally.
- The check is Windows-specific; elsewhere it is skipped.

## Alternatives considered

- **Lazy loading per request / unloading idle models** — rejected: the requirement was to load at start-up and keep latency predictable.
- **Smaller homograph model or dictionary-less RUAccent** — would reduce memory but alters the upstream G2P quality; deferred to the roadmap as a measured experiment.
- **ONNX / quantized Kokoro exports** — lower memory, but a different model artifact than specified; needs an explicit owner decision.
- **Enlarging the pagefile automatically** — rejected: system configuration is the owner's decision.

## Open questions

- Should Russian be retried automatically when `free_commit_mb` later exceeds the threshold?
- Should thresholds be environment-configurable?
- Should a shared launcher apply the same guard to `server.py` and the Uzbek TTS?
