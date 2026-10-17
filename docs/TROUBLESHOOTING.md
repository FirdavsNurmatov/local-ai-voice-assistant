# Troubleshooting

- **Last verified:** 2026-10-13
- **Status:** causes marked **Confirmed** were observed on 2026-10-13 or follow directly from source code; causes marked **Possible** are plausible but unobserved
- **Related:** [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md), [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md), [API_REFERENCE.md](API_REFERENCE.md)

First, always: which stage failed? Text answer missing → stages 1–3 (`server.py`, MADLAD, Ollama).
Text answer present but no sound → stage 4 (TTS / browser). See [DATA_FLOW.md](DATA_FLOW.md).

Standard diagnostics used below:

```powershell
# D1 ports            D2 memory                         D3 all health endpoints
Get-NetTCPConnection -State Listen -EA SilentlyContinue | ? { $_.LocalPort -in 8765,8766,8767,8768,11434 } | select LocalPort,OwningProcess
$o = Get-CimInstance Win32_OperatingSystem; '{0:N1} GB commit free of {1:N1}' -f ($o.FreeVirtualMemory/1MB), ($o.TotalVirtualMemorySize/1MB)
8765,8766,8767,8768 | % { try { "$_ " + (irm "http://127.0.0.1:$_/api/health" -TimeoutSec 5 | ConvertTo-Json -Compress -Depth 4) } catch { "$_ DOWN" } }
```

Contents: [Port in use](#port-already-in-use) · [Health unavailable while loading](#health-endpoint-unavailable-during-model-loading) ·
[Kokoro 503](#kokoro-http-503) · [English works, Masha does not](#kokoro-english-works-but-russian-masha-is-unavailable) ·
[Piper NetworkError](#piper-fallback-networkerror) · [Commit memory](#insufficient-windows-commit-memory) ·
[Ollama](#ollama-unavailable) · [MADLAD](#madlad-translation-failure) · [G2P encoding](#g2p-encoding-failure-on-windows) ·
[Silent/malformed audio](#audio-file-exists-but-is-silent-or-malformed) · [Cannot play](#frontend-receives-audio-but-cannot-play-it) ·
[Wrong language](#language-detection-chooses-the-wrong-language) · [Crash after model load](#service-crashes-after-another-model-loads) ·
[Environment mismatch](#dependency-or-python-environment-mismatch)

---

## Port already in use

1. **Symptom:** a service exits at start with `OSError: [WinError 10048] Only one usage of each socket address…`.
2. **Causes:** *Confirmed (by design):* another copy of the same service is running. *Possible:* an unrelated program uses the port.
3. **Diagnostics:** D1, then `Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | select CommandLine`.
4. **Interpretation:** command line shows the same script → duplicate; anything else → foreign program.
5. **Fix:** keep the existing instance, or stop it by PID and start again.
6. **Recovery:** health check (D3).
7. **Do not:** change the port number in one file only (ports are hard-coded in the HTML and `server.py` too); kill all `python.exe`. Note `server.py` and `tts_onnx_server.py` load their model *before* failing on the port — a duplicate start costs memory first.

## Health endpoint unavailable during model loading

1. **Symptom:** connection refused / timeout on `/api/health` shortly after start.
2. **Causes:** *Confirmed:* `server.py` (8765) and `tts_onnx_server.py` (8766) open their port only after the model is loaded. Kokoro (8768) answers immediately with `"loading": true`.
3. **Diagnostics:** look at the service window: `MADLAD INT8 modeli yuklanmoqda...` / `Fine-tuned Uzbek ONNX TTS modeli yuklanmoqda...` means still loading. D1 shows no row yet.
4. **Interpretation:** no listener + window still alive = loading. No listener + window back at the prompt = it exited (read the traceback).
5. **Fix:** wait (MADLAD takes tens of seconds; under memory pressure much longer).
6. **Recovery:** none needed.
7. **Do not:** start a second copy "because it didn't respond".

## Kokoro HTTP 503

1. **Symptom:** `POST :8768/api/tts` → `503` with `{"ok":false,"error":…}`; the page shows `Kokoro TTS xatosi: …` and falls back to Piper.
2. **Causes (all Confirmed in code; first three observed):** (a) still loading — `…model hali yuklanmoqda`; (b) not enough commit at start — `MemoryError: xotira yetarli emas…`; (c) queue full — `Server band…`; (d) language disabled — `KOKORO_LANGS orqali o'chirilgan`; (e) missing file or voicepack hash mismatch — `FileNotFoundError` / `SHA256 mos kelmadi`.
3. **Diagnostics:** `irm http://127.0.0.1:8768/api/health | ConvertTo-Json -Depth 4`.
4. **Interpretation:** read `loading`, `ready`, `errors`, `free_commit_mb`. The `error` text of the 503 is the same as `errors.<lang>`.
5. **Fix:** (a) wait ≈ 10–20 s; (b) see next entry; (c) retry — at most 5 requests are accepted at once; (d) unset the variable and restart; (e) restore the file ([MODELS_AND_VOICES.md](MODELS_AND_VOICES.md)).
6. **Recovery:** restart only the Kokoro server; the load decision is made once at start.
7. **Do not:** set `KOKORO_SKIP_MEMCHECK=1` to silence (b).

## Kokoro English works but Russian Masha is unavailable

1. **Symptom:** health shows `"ready":{"ru":false,"en":true}`, `ok:false`; Russian is spoken by the Piper voice.
2. **Causes:** *Confirmed:* free commit after English loaded was below 4000 MB (1653 MB on 2026-10-13 with all services up). This is the expected state on the 8 GB reference machine.
3. **Diagnostics:** `errors.ru` in health; D2.
4. **Interpretation:** the number in the error is the free commit at the moment of the check.
5. **Fix:** free or add commit — options in [MEMORY_AND_PERFORMANCE.md §6](MEMORY_AND_PERFORMANCE.md#6-options-for-getting-russian-masha-to-load) — then restart the Kokoro server.
6. **Recovery:** nothing is broken; Piper covers Russian meanwhile.
7. **Do not:** lower `REQUIRED_FREE_MB`, or skip the check, while `server.py` is running — that is how the other services crashed.

## Piper fallback NetworkError

1. **Symptom:** status line `…Piper ham ishlamadi: NetworkError when attempting to fetch resource.` (Firefox) or `…Failed to fetch` (Chromium), or `Piper TTS xatosi: …` in `piper` mode.
2. **Causes:** since 2026-10-17 the page calls `/api/tts/piper` on `server.py`, which forwards to `127.0.0.1:8767`: (a) Piper server not running → the notice says `server ishlamayapti (8767)`; (b) `Failed to fetch` means the page lost `server.py` (8765) itself. (Before 2026-10-17 the page called 8767 directly, which failed from other devices.)
3. **Diagnostics:** D1 for 8767; `irm http://127.0.0.1:8767/api/health` on the server machine; check the address bar — is it `localhost`/`127.0.0.1` or an IP?
4. **Interpretation:** health fails → (a). Health OK but the page URL is not local → (b)/(c).
5. **Fix:** start `piper_tts_server.py`; use a browser on the server machine.
6. **Recovery:** press "▶ Qayta eshitish" on the message.
7. **Do not:** rebind Piper/Kokoro to `0.0.0.0` as a quick fix — they have no authentication ([SECURITY.md](SECURITY.md)). Note: a `NetworkError` means *no HTTP response*; an HTTP error from Piper would show its own message (`422 …`).

## Insufficient Windows commit memory

1. **Symptom:** any of: Kokoro refuses a language; a service exits without a traceback; `MemoryError`; `bad allocation`; Windows "low on memory" warnings; everything becomes very slow.
2. **Causes:** *Confirmed measurement:* `server.py` commits ≈ 9.9 GB and full Kokoro ≈ 5.5 GB against an 18.4 GB limit. *Probable, not proven:* this killed three services on 2026-10-13.
3. **Diagnostics:** D2; per process: `Get-Process python | select Id,@{n='RSS_MB';e={[int]($_.WorkingSet64/1MB)}},@{n='Commit_MB';e={[int]($_.PrivateMemorySize64/1MB)}}`.
4. **Interpretation:** look at **Commit**, not RSS — an idle model can show a tiny RSS. Free commit under ≈ 1 GB is dangerous.
5. **Fix:** stop the Kokoro server first; close other heavy applications; longer term, enlarge the pagefile or add RAM (owner decision).
6. **Recovery:** [MEMORY_AND_PERFORMANCE.md §7](MEMORY_AND_PERFORMANCE.md#7-safe-recovery-when-memory-runs-out).
7. **Do not:** judge by "free RAM" alone; start duplicate services; change pagefile settings casually or without a restart plan.

## Ollama unavailable

1. **Symptom:** chat bubble `Xatolik: Ollama bilan ulanish xatosi: …` (HTTP 502), while the page header still looks healthy.
2. **Causes (from code):** (a) Ollama not running → connection refused; (b) model `gemma3:4b` not pulled → Ollama returns 404, surfaced as the same 502; (c) generation exceeded 180 s → timeout; *Possible:* (d) Ollama itself out of memory.
3. **Diagnostics:** `irm http://127.0.0.1:11434/api/version`; `(irm http://127.0.0.1:11434/api/tags).models.name`; read the text after `xatosi:`.
4. **Interpretation:** version call fails → (a); model absent from tags → (b); `Read timed out` → (c).
5. **Fix:** start the Ollama app; `ollama pull gemma3:4b`; for timeouts check memory (the first request after 10 idle minutes reloads the model).
6. **Recovery:** resend the message; no restart of `server.py` needed.
7. **Do not:** trust `GET :8765/api/health` for this — it never contacts Ollama.

## MADLAD translation failure

1. **Symptom:** (a) `server.py` dies at start; (b) chat returns `500` with an exception name; (c) translation is wrong, cut off, or in the wrong script.
2. **Causes:** (a) *Possible:* missing/corrupt `madlad400-3b-ct2-int8\`, or not enough commit to load ≈ 10 GB. (b) any exception in `translate`/`run_chat` (also malformed request JSON → `JSONDecodeError`). (c) *Confirmed by code:* output capped at 128 tokens, greedy decoding, source language not specified; Uzbek output is transliterated by a simple character map.
3. **Diagnostics:** the `server.py` window (traceback); compare `english_input` / `answer_english` / `answer` in the JSON response to see which direction went wrong.
4. **Interpretation:** `english_input` wrong → input translation or language detection; `answer_english` fine but `answer` bad → output translation.
5. **Fix:** (a) restore files / free memory; (c) shorter inputs; these are model-quality limits, not bugs to patch casually.
6. **Recovery:** restart `server.py` if it exited (check memory first).
7. **Do not:** run the root `test_madlad*.py` scripts next to the live server — each loads another full copy of the model.

## G2P encoding failure on Windows

1. **Symptom:** `UnicodeDecodeError: 'charmap' codec can't decode byte 0x98 …` from `ru_g2p.py` (`read_text`) when Russian loads; `errors.ru` contains it.
2. **Causes:** *Confirmed (2026-10-13):* `ru_g2p.py` reads a UTF-8 JSON file with the locale encoding (cp1251 on this machine).
3. **Diagnostics:** `& .\.venv-kokoro\Scripts\python.exe -c "import sys,locale; print(sys.flags.utf8_mode, locale.getpreferredencoding(False))"`.
4. **Interpretation:** `0 cp1251` (or another non-UTF-8 code page) reproduces the problem when `ru_g2p` is used directly.
5. **Fix:** the server already handles this by re-launching itself with `-X utf8`. For ad-hoc scripts add `-X utf8` or set `$env:PYTHONUTF8='1'`.
6. **Recovery:** restart the Kokoro server.
7. **Do not:** edit `ru_g2p.py` (kept identical to upstream), or set `PYTHONUTF8=0` in the environment of the server.

## Audio file exists but is silent or malformed

1. **Symptom:** a WAV is returned/saved but nothing is audible, or players reject it.
2. **Causes:** *Confirmed by code:* (a) the "file" is actually a JSON error saved with `-OutFile` (non-200); (b) Uzbek TTS silently drops characters it does not know — text in another script yields near-empty audio or `422`; (c) Kokoro raises `500` for all-silent output and `422` when nothing is pronounceable. *Possible:* (d) text in the wrong language for the selected voice; (e) volume slider at 0.
3. **Diagnostics:** `Test-Wav file.wav` from [TESTING.md §2](TESTING.md#2-testing-each-component-independently); `Get-Content file.wav -TotalCount 1` to spot JSON; check `X-TTS-Voice` / status code.
4. **Interpretation:** not `RIFF` → error body; correct header with tiny peak → silent synthesis.
5. **Fix:** send text in the engine's language and script; check the HTTP status before saving.
6. **Recovery:** none.
7. **Do not:** treat HTTP 200 as proof of good audio; "fix" the Uzbek symbol filter without retraining knowledge.

## Frontend receives audio but cannot play it

1. **Symptom:** status line `Kokoro audio ijro etilmadi: …`, `Audio ijro etilmadi.`, `Piper audio ijro etilmadi.` or a `play()` error; network tab shows `200`.
2. **Causes:** *Confirmed (2026-10-13):* a browser pauses/blocks playback for muted or background tabs (`The play() request was interrupted…`). *Possible:* autoplay policy when the reply arrives without a recent click; output device problems; a new `speak()` interrupting the previous one.
3. **Diagnostics:** click "▶ Qayta eshitish" (a direct user gesture); try "Test ovozi"; check the tab is in the foreground and not muted; browser console.
4. **Interpretation:** works on click but not automatically → autoplay policy.
5. **Fix:** allow autoplay/sound for `localhost:8765` in the browser's site settings; keep the tab active.
6. **Recovery:** replay button.
7. **Do not:** conclude the TTS server is broken — in this case it answered correctly. (By design, a playback error does **not** trigger the Piper fallback.)

## Language detection chooses the wrong language

1. **Symptom:** Uzbek text answered in English or Russian; wrong voice; `language` in the response is not what was typed.
2. **Causes:** *Confirmed by code:* keyword heuristic — any Cyrillic → `ru`; Uzbek only if one of ≈ 45 words or `oʻ`/`gʻ` appears; everything else → `en`; the page's language selector is ignored by the backend.
3. **Diagnostics:** inspect `language` in the `/api/chat` response (shown in the status line as `til: …`).
4. **Interpretation:** see the rules in [DATA_FLOW.md](DATA_FLOW.md#stage-2--language-detection-detect_language).
5. **Fix (user side):** include a common Uzbek word (`salom`, `rahmat`, `qanday`, …), write Uzbek in Latin script.
6. **Recovery:** resend.
7. **Do not:** expect the "Suhbat tili" selector to force a language — it currently only affects the test-voice button. A real fix is a code change ([ROADMAP.md](ROADMAP.md)).

## Service crashes after another model loads

1. **Symptom:** a previously healthy service is gone (connection refused) soon after another service started or loaded a model; often several die together; possibly no traceback.
2. **Causes:** *Probable (observed once, 2026-10-13, not proven):* system commit exhausted — see [the incident](MEMORY_AND_PERFORMANCE.md#5-incident-of-2026-10-13-why-the-guard-exists). *Possible:* the window was closed; an unrelated crash.
3. **Diagnostics:** D1, D2; the last lines of each service window; Event Viewer → Windows Logs → Application/System around that time (may show nothing).
4. **Interpretation:** several services gone + low free commit = memory. One service gone with a traceback = that service's own error.
5. **Fix:** reduce what is loaded (Kokoro first), then restart.
6. **Recovery:** [WINDOWS_RUNBOOK.md §10](WINDOWS_RUNBOOK.md#10-recovery-from-an-unexpected-exit).
7. **Do not:** restart everything at once without checking memory; disable the Kokoro guard.

## Dependency or Python environment mismatch

1. **Symptom:** `ModuleNotFoundError`, `ImportError`, DLL load errors, or odd API errors right at start.
2. **Causes:** *Confirmed by design:* each service must run with **its own** interpreter; the environments hold incompatible versions (e.g. `transformers` 4.57 vs 5.19). Typical mistakes: using `python` from PATH, an activated wrong venv, `pip install` into the wrong venv, moving the project folder (venvs record absolute paths).
3. **Diagnostics:** `& <venv>\Scripts\python.exe -c "import sys; print(sys.executable, sys.version)"`; compare `& <venv>\Scripts\python.exe -m pip freeze --all` with [requirements/](requirements/README.md).
4. **Interpretation:** any version difference from the snapshot is a lead.
5. **Fix:** start with the exact commands from the runbook; reinstall the single deviating package at the snapshot version.
6. **Recovery:** if an environment is beyond repair, rebuild it in a **new** folder ([DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)) and switch only when it works.
7. **Do not:** `pip install --upgrade` inside a working environment; share one environment between services; delete an environment before its replacement is proven.
