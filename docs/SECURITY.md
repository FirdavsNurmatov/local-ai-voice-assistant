# Security, privacy and publication readiness

- **Last verified:** 2026-10-13 · **Status:** exposure facts `SOURCE-CODE CONFIRMED`; repository scan `VERIFIED` (read-only, 2026-10-13)
- **Related:** [LICENSING.md](LICENSING.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md), [../CONTRIBUTING.md](../CONTRIBUTING.md)

## 1. Network exposure

| Service | Bind | Reachable from | Auth | TLS |
|---|---|---|---|---|
| `server.py` 8765 | `0.0.0.0` | **any host that can reach this machine** (LAN; subject to Windows Firewall rules, which were not inspected) | none | none |
| Uzbek TTS 8766 | `127.0.0.1` | local machine only — but exposed indirectly through `POST :8765/api/tts` | none | none |
| Piper 8767 | `127.0.0.1` | local machine; any web page open in a local browser (CORS `*`) | none | none |
| Kokoro 8768 | `127.0.0.1` | local machine; any web page open in a local browser (CORS `*`) | none | none |
| Ollama 11434 | `127.0.0.1` (default; no `OLLAMA_HOST` override found) | local machine | none | none |

Implications:

- Anyone on the same network can use the chat (CPU/memory load, prompt content) and the Uzbek TTS proxy. `server.py` prints a warning at start: use only on a trusted LAN, never port-forward.
- Because Piper and Kokoro allow any origin, a malicious website visited in a browser on this machine could make them synthesize speech (CPU load). It cannot read files or reach the other services' data through them.
- Request size and text length are bounded in every service; Kokoro additionally bounds its queue. There is no rate limiting.
- No service executes user input as code. Piper passes text via a temp **file** and a fixed argument list (no shell), so there is no command-injection path through `text`.
- Error responses include Python exception type and message; Piper's include up to 3000 characters of the CLI's stderr (may reveal local paths).

## 2. Privacy

| Data | Where it goes | Persisted? |
|---|---|---|
| User message, translations, answer | `server.py` memory → Ollama on localhost | not by this project; Ollama's own logging/history behaviour was not audited (`NOT VERIFIED`) |
| Text to speak | the selected local TTS service | no (Piper: temp files deleted per request) |
| Text in "browser voice" mode (removed 2026-10-17) | the browser's speech engine — may be a cloud service depending on browser/voice | no longer possible: the page offers only local voices |
| Console output | service windows: request lines, character counts; **full text on Uzbek TTS synthesis errors** | only if the operator redirects output to a file |

"Local" here means: no code in this repository sends request data to an external host
(`SOURCE-CODE CONFIRMED`; the only URLs are `127.0.0.1`/relative). It does **not** mean air-gapped:
setup needs downloads, Ollama is a third-party application, and the page is served over plain HTTP.

## 3. Secret scan (2026-10-13)

Scope: all files outside virtual environments, model binaries and nested `.git` folders. Patterns:
API keys, tokens (`hf_…`, `sk-…`, `ghp_…`), passwords, `Authorization`/`Bearer`, `.env`/key/credential files.

| Finding | Result |
|---|---|
| `.env`, `*.pem`, `*.key`, credentials files (outside venvs) | **none** |
| Hard-coded API keys / tokens / passwords in project sources, HTML, scripts, docs | **none** |
| Pattern hits | only false positives: tokenizer special-token names in `tts-test-code\train (26).py`; a `.gitignore` rule in `Uzbek_TTS-test\` |
| `logs\` | one non-empty file (`kokoro_tts.out.log`): request lines and character counts, no user text, no secrets |
| Git remotes of nested repos | plain HTTPS URLs without embedded credentials |

Not scanned: binary model files, the contents of virtual environments, and git history of the nested repositories.

## 4. Publication risks (before pushing to GitHub)

| Risk | Where | Recommendation |
|---|---|---|
| Large binaries (≈ 15 GB total) | `madlad400-3b-ct2-int8\`, `nllb-int8\`, `kokoro-models\`, `*.onnx`, `Uzbek_TTS-test\`, venvs | excluded by the provided `.gitignore`; never add with `git add -f` |
| Nested git repositories | `stt-tts-uz\`, `tts-test-code\`, `Uzbek_TTS-test\` | excluded; they belong to other authors. `git add` on them would create broken gitlinks. Record them as external dependencies instead (done in [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)) |
| Third-party code needed at runtime | `stt-tts-uz\text\` (with a local patch) | not redistributed; patch kept in [patches/](patches/README.md). Upstream has no license file — see [LICENSING.md](LICENSING.md) |
| Model licenses | Kokoro-RU (OpenRAIL), Piper voices, Uzbek model (unknown) | do not upload weights; link to sources |
| Project license | root | resolved: MIT `LICENSE` present; third-party terms still apply ([LICENSING.md](LICENSING.md)) |
| Machine-specific paths | `C:\local-ai-translator` in `start_tts.ps1`, legacy scripts, and docs; `pyvenv.cfg` contains the Windows user name (inside ignored venvs) | harmless but worth generalizing; docs use `<user>` where the profile path appears |
| Personal data in docs | none: no names, e-mail addresses or user profile paths were written into `docs/` | re-check before publishing |
| Backups (`*.bak`) | 3 files, source snapshots only, no secrets | excluded by `.gitignore`; history belongs in git once the repo exists |
| WAV test outputs | root and `kokoro-test-output\` | excluded; synthetic test sentences only |
| Legacy experiment scripts | `chat*.py`, `test_*.py`, `benchmark_translation.py`, `compare_nllb.py`, `benchmarks\` | **not** ignored — owner should decide whether to publish, move to `legacy/`, or drop |
| Interface language | UI and error messages are Uzbek; docs are English | note in README (done) |

## 5. What should and should not be version-controlled

**Track:** the four service scripts, `local_voice_chat.html`, the two `start_*.ps1`, `README.md`,
`CHANGELOG.md`, `CONTRIBUTING.md`, `.gitignore`, `docs\` (including `requirements\` and `patches\`),
`KOKORO_TTS.md`, optionally `README.txt`, `benchmarks\` and the legacy scripts.

**Download/obtain separately (never commit):** Python environments, Ollama and its models, MADLAD,
Piper voices, the Uzbek model, Kokoro weights/voicepacks/`espeak-data`/`ru_g2p.py`, RUAccent models,
the `stt-tts-uz` source tree.

## 6. Pre-commit checklist

The repository was first published on 2026-10-13 (public, <https://github.com/FirdavsNurmatov/local-ai-voice-assistant>)
after a `git add --dry-run .` review: 60 text files, the largest 19 KB, no binaries. Repeat before every commit:

```powershell
Set-Location C:\local-ai-translator
git status --short             # review: only sources, scripts and docs should be listed
git add --dry-run .            # confirm nothing large or nested is picked up
git check-ignore -v madlad400-3b-ct2-int8\model.bin .venv-kokoro stt-tts-uz kokoro-models logs
```

Because the repository is public, everything in the sections above (open bind address, no
authentication, permissive CORS) is public knowledge: do not expose a running instance to an untrusted network.

## 7. Hardening ideas (`PROPOSED`)

Bind `server.py` to `127.0.0.1` unless LAN access is needed; restrict CORS on 8767/8768 to
`http://localhost:8765` / `http://127.0.0.1:8765`; route Kokoro/Piper through a same-origin proxy
like the Uzbek TTS (also fixes remote-client playback); add a shared secret if exposed beyond one machine.
