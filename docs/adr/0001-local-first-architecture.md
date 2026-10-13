# ADR 0001 — Local-first architecture with one process per model

- **Status:** Accepted (retroactively documented 2026-10-13; the decision itself predates this record)
- **Evidence level:** structure `SOURCE-CODE CONFIRMED`; motivation partly inferred (marked)
- **Related:** [../ARCHITECTURE.md](../ARCHITECTURE.md), [../DECISIONS.md](../DECISIONS.md) (D1, D2, D4)

## Context

The assistant must chat in Uzbek, Russian and English with spoken replies on a single consumer PC
(8 GB RAM, no GPU use). All prototypes in the directory, from the first (`chat.py`, 2026-10-11),
use local models: Ollama for the LLM and a local translation model. No cloud API key or external
endpoint appears anywhere in the code.

*Inferred, not recorded:* privacy, zero running cost and independence from connectivity were goals.

## Decision

1. Run every model on the local machine: Ollama (`qwen3:1.7b`) for chat, MADLAD-400 (CTranslate2 INT8) for translation, and separate local TTS engines.
2. Give each model runtime its **own process, own port and own Python virtual environment**, communicating over plain HTTP + JSON on localhost.
3. Use only the Python standard library `http.server` for the services — no web framework.
4. Keep a small LLM that is prompted in English and translate around it, instead of a larger multilingual LLM.

## Consequences

Positive

- Components can be added, replaced or restarted independently; dependency conflicts between stacks cannot occur.
- A failing TTS engine does not affect chat.
- No request data leaves the machine through this project's code.

Negative

- Memory: runtimes are duplicated and nothing coordinates total use; the sum exceeds the reference machine ([../MEMORY_AND_PERFORMANCE.md](../MEMORY_AND_PERFORMANCE.md)).
- Operations: four windows, manual start order, no supervisor, no shared health view.
- Translation adds latency and a failure stage, caps answer length, and can distort meaning.
- `http.server` is single-purpose and unauthenticated; fine for localhost, unsuitable for exposure.

## Alternatives (not evaluated in any recorded form)

A single multilingual LLM without translation; one combined Python process; a framework such as FastAPI; cloud APIs.

## Open questions

- Is MADLAD's quality advantage over NLLB worth ≈ 10 GB of commit on this hardware?
- Should there be an orchestrator/launcher that owns start order and memory budgeting?
