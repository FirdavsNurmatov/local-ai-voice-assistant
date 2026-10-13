# Contributing / working on this project safely

This applies equally to the project owner and to AI coding agents. Read
[docs/INDEX.md](docs/INDEX.md) first; the system has sharp edges that are not visible in the code.

> The project's own code is MIT-licensed ([LICENSE](LICENSE)); contributions are accepted under the
> same license. Third-party models and libraries keep their own terms ([docs/LICENSING.md](docs/LICENSING.md)).

## Ground rules

1. **Protect the working setup.** Take a backup (or, once the root is a git repository, a commit) before editing a service or the page.
2. **Check memory before loading any model** — including "quick" test scripts. Look at free *commit*, not free RAM ([docs/MEMORY_AND_PERFORMANCE.md](docs/MEMORY_AND_PERFORMANCE.md)). Loading a second copy of MADLAD or the full Kokoro stack next to the live services can crash them.
3. **One environment per service.** Never `pip install` or upgrade inside an existing environment as a side effect of another task. If versions change deliberately, regenerate the matching file in `docs/requirements/`.
4. **Do not stop or restart services you did not start**, and never kill by process name. Identify the process by port ([docs/WINDOWS_RUNBOOK.md](docs/WINDOWS_RUNBOOK.md#9-shutdown)).
5. **Do not substitute models, voices or model formats silently.** `masha` and `af_heart` are pinned by path and SHA256 on purpose. A different artifact is a decision to record in [docs/DECISIONS.md](docs/DECISIONS.md).
6. **Leave third-party files untouched:** `kokoro-models\kokoro-ru\ru_g2p.py`, `espeak-data\`, model configs, and the Uzbek model. Work around them in our own code and document the workaround.
7. **Never commit** environments, weights, voicepacks, WAV files, logs, `.bak` files or the nested third-party repositories. Check `git status` and `git add --dry-run .` before every commit.
8. **No secrets** in code, docs, logs or examples. The project currently needs none.

## Things that are easy to break

See the table "What must not be changed casually" in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#7-what-must-not-be-changed-casually).
In short: ports and JSON field names are a contract spread over several files; Kokoro's load order and
memory thresholds exist for reasons recorded in ADR 0003.

## Making a change

1. Find the relevant page in `docs/` and the related entry in [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) / [docs/ROADMAP.md](docs/ROADMAP.md).
2. Change one service at a time. The page is re-read on browser refresh; Python services need a restart (mind rule 2 when restarting `server.py`).
3. Test the component alone, then run the smoke test ([docs/TESTING.md](docs/TESTING.md)). A `200` is not proof — validate the WAV and listen to it.
4. Update the documentation in the same change:
   - endpoint or schema → `docs/API_REFERENCE.md`
   - constant, port, env var → `docs/CONFIGURATION.md` (and `README.md` tables if a port/voice changed)
   - model, voice, hash → `docs/MODELS_AND_VOICES.md`, `docs/LICENSING.md`
   - behaviour or flow → `docs/ARCHITECTURE.md`, `docs/DATA_FLOW.md`
   - new measurement → `docs/MEMORY_AND_PERFORMANCE.md` with date, method and status
   - fixed/new limitation → `docs/KNOWN_ISSUES.md`, `docs/ROADMAP.md`
   - a choice between alternatives → `docs/DECISIONS.md` (or a new file in `docs/adr/`)
   - always → `CHANGELOG.md`
5. Use the status vocabulary from [docs/INDEX.md](docs/INDEX.md) and set "Last verified" only for what you actually re-checked. Never upgrade a `HISTORICAL TEST RESULT` to `VERIFIED` without rerunning it.

## Style

- Services: Python standard library `http.server`, no framework, constants at the top of the file, user-facing messages in Uzbek (existing convention).
- Frontend: a single HTML file with inline CSS/JS, no build step, no external assets.
- Documentation: English, relative links, one canonical page per topic (link instead of copying).
