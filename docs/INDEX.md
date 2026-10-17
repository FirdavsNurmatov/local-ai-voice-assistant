# Documentation index

- **Last verified:** 2026-10-13
- **Scope:** `C:\local-ai-translator` as found on that date (reference machine: Windows 11 Pro, i7-9700K, 7.9 GB RAM, CPU only)

## How to read these documents

Every important statement carries one of these statuses:

| Status | Meaning |
|---|---|
| `VERIFIED` | Observed directly during the documentation audit on 2026-10-13 (command output, file contents, hashes). |
| `SOURCE-CODE CONFIRMED` | Read from the current source code; behaviour not re-executed during the audit. |
| `HISTORICAL TEST RESULT` | Measured or tested earlier (date given), **not rerun** during the audit. Do not treat as a guarantee. |
| `NOT VERIFIED` | Believed or reported, but no evidence was found locally. |
| `PROPOSED` | An idea or recommendation, not implemented. |

During the audit the four Python services were **not running** (the owner runs them manually) and
were deliberately not started. Therefore all runtime behaviour of the services is either
`SOURCE-CODE CONFIRMED` or `HISTORICAL TEST RESULT` from the integration session earlier the same day.

> **Update 2026-10-14.** Three behaviours changed after the original audit: (1) voice input was
> added ([STT.md](STT.md)); (2) `POST /api/chat` now honours `language` = `uz`/`ru`/`en`;
> (3) Kokoro mode no longer falls back to Piper — the real error is shown instead.
> [STT.md](STT.md), [ARCHITECTURE.md](ARCHITECTURE.md), [API_REFERENCE.md](API_REFERENCE.md),
> [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and the README reflect this.
> [DATA_FLOW.md](DATA_FLOW.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [DECISIONS.md](DECISIONS.md),
> [adr/0002](adr/0002-language-specific-tts-routing.md), [TESTING.md](TESTING.md) and
> [CONFIGURATION.md](CONFIGURATION.md) still describe the 2026-10-13 state on these three points.

## Start here

| If you want to… | Read |
|---|---|
| Understand what this is | [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) |
| See how the parts connect | [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_FLOW.md](DATA_FLOW.md) |
| Start, stop, check services | [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md) |
| Fix a problem | [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md) |
| Call an endpoint | [API_REFERENCE.md](API_REFERENCE.md) |
| Rebuild the setup on another machine | [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md), [DEPENDENCIES.md](DEPENDENCIES.md), [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md) |
| Understand the memory limits | [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md) |
| Change the code safely | [../CONTRIBUTING.md](../CONTRIBUTING.md), [CONFIGURATION.md](CONFIGURATION.md), [TESTING.md](TESTING.md) |
| Publish to GitHub | [SECURITY.md](SECURITY.md), [LICENSING.md](LICENSING.md) |
| Know why things are the way they are | [DECISIONS.md](DECISIONS.md), [adr/](adr/0001-local-first-architecture.md) |
| Plan next work | [ROADMAP.md](ROADMAP.md) |

## All documents

| Document | Content |
|---|---|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Purpose, inventory of every top-level file and folder, what is active vs. legacy |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System, component and sequence diagrams; port/process map; per-service design |
| [DATA_FLOW.md](DATA_FLOW.md) | Step-by-step path from typed text to played audio |
| [STT.md](STT.md) | Speech-to-text (Faster-Whisper `small`, port 8769): install, API, language handling, measured accuracy/speed/memory, limits. **Added 2026-10-14** |
| [STT_EVALUATION.md](STT_EVALUATION.md) | Uzbek STT model comparison (current `small` vs NavAI) on real human speech: method, results, error analysis, recommendation. **Added 2026-10-14** |
| [STT_EVALUATION_REPRODUCE.md](STT_EVALUATION_REPRODUCE.md) | Exact commands to reproduce that evaluation |
| [CURRENT_SETUP.md](CURRENT_SETUP.md) | **The current best configuration** (STT → chat → TTS), every choice with its numbers, what was rejected, how to start it. **Added 2026-10-17** |
| [LLM_COMPARISON.md](LLM_COMPARISON.md) | Chat model and pipeline comparison (qwen3:1.7b / qwen3:4b / gemma3:4b × madlad / dual / hybrid / direct) and why the chat now uses gemma3:4b with the hybrid pipeline. **Added 2026-10-17** |
| [API_REFERENCE.md](API_REFERENCE.md) | Every HTTP route of the five services with examples |
| [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) | Rebuilding environments and obtaining models |
| [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md) | Operator manual: start, stop, health, logs, recovery, smoke test |
| [CONFIGURATION.md](CONFIGURATION.md) | Every constant, environment variable and tunable, with file and line |
| [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md) | Model files, hashes, provenance, voice routing |
| [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md) | Memory concepts, measurements, the 2026-10-13 incident, benchmarks |
| [TESTING.md](TESTING.md) | Manual test procedures and recorded results |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based knowledge base |
| [SECURITY.md](SECURITY.md) | Exposure, privacy, publication-readiness audit |
| [DEPENDENCIES.md](DEPENDENCIES.md) | The four Python environments and external tools |
| [LICENSING.md](LICENSING.md) | License status of code, models and voices |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Confirmed defects and limitations |
| [ROADMAP.md](ROADMAP.md) | Verified / unverified / limitations / proposals |
| [DECISIONS.md](DECISIONS.md) | Decision log with evidence and open trade-offs |
| [adr/0001-local-first-architecture.md](adr/0001-local-first-architecture.md) | ADR: local-first architecture |
| [adr/0002-language-specific-tts-routing.md](adr/0002-language-specific-tts-routing.md) | ADR: language-specific TTS routing |
| [adr/0003-memory-aware-kokoro-loading.md](adr/0003-memory-aware-kokoro-loading.md) | ADR: memory-aware Kokoro loading |
| [requirements/](requirements/README.md) | `pip freeze` snapshot of each environment |
| [patches/](patches/README.md) | Local modification to the third-party Uzbek text cleaner |

Root files: [../README.md](../README.md), [../CHANGELOG.md](../CHANGELOG.md), [../CONTRIBUTING.md](../CONTRIBUTING.md).
The repository's own code is MIT-licensed ([../LICENSE](../LICENSE)); third-party terms are in [LICENSING.md](LICENSING.md).

Earlier notes kept for reference: [../KOKORO_TTS.md](../KOKORO_TTS.md) (Uzbek, Kokoro integration notes) and
`README.txt` (original install note, predates Piper and Kokoro). Where they disagree with `docs/`, `docs/` is current.
