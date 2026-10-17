# NavAI integration — status 2026-10-17

Code integrated, tested and committed (2026-10-17). Details and numbers: [docs/STT.md](../../docs/STT.md#uzbek-routing-navai--integrated-2026-10-16).

## Result folders
- `baseline/` — exact pre-integration code (`stt_server.py.before_navai.bak`), separate test process on port 8779.
  Part 1 was run on 2026-10-14, part 2 on 2026-10-16 (same code, same model); `peak_baseline*.json` = process peaks.
- `navai/` — new code with NavAI, separate test process on port 8779; same requests.
- `production/` — new code started as the real service (`python stt_server.py`, port 8769); 5 of the sets.
- `memory_probe.json` — base model / both models / unload / reload, one process, sequential loading.
- `swap_test*.json`, `fallback_test*.json` — swap policy and NavAI-unavailable checks (`*2` = after the fixes).

Compare: `.venv-stt-eval\Scripts\python.exe stt-eval\scripts\integration_score.py stt-eval\integration\navai stt-eval\integration\baseline`

## Open items
1. ~~iPhone Safari through the HTTPS tunnel~~ — tested by the owner on 2026-10-16, microphone input works (manual test, no recorded numbers).
2. Male Uzbek voices (no open data found; USC 9.5 GB not downloaded without consent).
3. STT next to chat + Ollama on the 8 GB PC — not enough commit (measured). The owner accepted the risk and runs them together (system-managed pagefile grew to ~23.5 GB, `STT_SKIP_MEMCHECK=1`); the Ubuntu server is the long-term target.
4. Robot commands: transcripts are not reliable enough to act on directly.
