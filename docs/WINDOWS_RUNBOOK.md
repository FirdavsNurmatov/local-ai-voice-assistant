# Windows runbook (operator manual)

- **Last verified:** 2026-10-14 (STT start-up, port 8769 and the memory combinations were exercised that day)
- **Status:** file paths and commands `VERIFIED` against the directory; start-up commands were used successfully earlier on 2026-10-13 (`HISTORICAL TEST RESULT`); services were not started during the documentation audit
- **Related:** [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [TESTING.md](TESTING.md)

All commands are for **Windows PowerShell 5.1**. Run them from `C:\local-ai-translator` unless stated.

## 1. Prerequisites

- The four Python environments and all model files exist (see [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)).
- Ollama is installed and `qwen3:1.7b` is pulled.
- Free commit memory: see §3 before starting anything.

Quick file check (prints `True` for everything that is present):

```powershell
Set-Location C:\local-ai-translator
'.venv\Scripts\python.exe','.venv-piper\Scripts\python.exe','.venv-kokoro\Scripts\python.exe',
'stt-tts-uz\.venv-tts\Scripts\python.exe','madlad400-3b-ct2-int8\model.bin',
'stt-tts-uz\models\vits_uzbek_finetuned.onnx','stt-tts-uz\models\uz_tts_base.json',
'ru_RU-irina-medium.onnx','ru_RU-irina-medium.onnx.json','en_US-lessac-medium.onnx','en_US-lessac-medium.onnx.json',
'kokoro-models\kokoro-82m\kokoro-v1_0.pth','kokoro-models\kokoro-82m\voices\af_heart.pt',
'kokoro-models\kokoro-ru\kokoro-ru-v2-base.pth','kokoro-models\kokoro-ru\voices\masha.pt',
'kokoro-models\kokoro-ru\ru_g2p.py','kokoro-models\kokoro-ru\espeak-data\ru_dict' |
  ForEach-Object { '{0,-5} {1}' -f (Test-Path $_), $_ }
```

## 2. Is something already running? (avoid duplicates)

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 8765,8766,8767,8768,8769,11434 } |
  Select-Object LocalAddress, LocalPort, OwningProcess | Sort-Object LocalPort
```

A row for a port means that service is already up — **do not start a second copy**. A second copy
fails with `OSError: [WinError 10048]`. For `server.py` and `tts_onnx_server.py` the failure comes
only **after** the model has been loaded a second time (the port is bound last), which wastes
several GB of commit while it loads; the Kokoro server binds first and fails immediately.

Which program owns a port:

```powershell
$p = (Get-NetTCPConnection -LocalPort 8765 -State Listen).OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId=$p" | Select-Object ProcessId, ParentProcessId, CommandLine
```

## 3. Check memory before starting

```powershell
$o = Get-CimInstance Win32_OperatingSystem
'{0:N1} GB RAM free of {1:N1};  {2:N1} GB commit free of {3:N1}' -f `
  ($o.FreePhysicalMemory/1MB), ($o.TotalVisibleMemorySize/1MB), ($o.FreeVirtualMemory/1MB), ($o.TotalVirtualMemorySize/1MB)
```

"Commit free" is the number that matters. Approximate needs (historical, see
[MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md)): `server.py` ≈ 10 GB, Kokoro English ≈ 2 GB,
Kokoro Russian ≈ 3.5 GB more, STT ≈ 2.6 GB, Uzbek TTS ≈ 0.7 GB, Ollama model ≈ 1.4 GB.

## 4. Start-up

Open **one PowerShell window per service** and keep it open; closing the window stops the service.
Recommended order (reasons below):

**Window 0 — Ollama** (usually already running in the tray):

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models.name    # must include qwen3:1.7b
```

If the first command fails, start the Ollama application from the Start menu (or run `ollama serve` in its own window).

**Window 1 — Uzbek TTS (8766).** Wait for `TTS modeli tayyor`:

```powershell
Set-Location C:\local-ai-translator
.\stt-tts-uz\.venv-tts\Scripts\python.exe .\tts_onnx_server.py
```

Equivalent: `.\start_tts.ps1` (same command plus a check that the venv exists; it hard-codes `C:\local-ai-translator`).

**Window 2 — Piper TTS (8767).** Starts instantly:

```powershell
Set-Location C:\local-ai-translator
.\.venv-piper\Scripts\python.exe .\piper_tts_server.py
```

**Window 3 — Chat backend (8765).** Wait for `MADLAD tayyor.` and `Chat server: http://localhost:8765`:

```powershell
Set-Location C:\local-ai-translator
.\.venv\Scripts\python.exe .\server.py
```

**Window 4 — Kokoro TTS (8768).** Wait for the line starting `[Kokoro] ready=`:

```powershell
Set-Location C:\local-ai-translator
.\.venv-kokoro\Scripts\python.exe .\kokoro_tts_server.py
```

**Window 5 — STT / voice input (8769).** Optional; wait for `[STT] model tayyor`:

```powershell
Set-Location C:\local-ai-translator
.\.venv-stt\Scripts\python.exe .\stt_server.py
```

Equivalent: `.\start_stt.ps1`. Needs ≈ 2.6 GB of free commit. **On the reference machine chat + STT +
Kokoro do not fit together** (measured 2026-10-14): with chat and STT loaded, Kokoro refused both
voices; with chat and Kokoro (English) loaded there is no room for STT. Choose per session:

| Goal | Start |
|---|---|
| Voice input + chat, Uzbek answers spoken | 8766, 8765, 8769 (Kokoro will show a memory error for ru/en answers) |
| Typed chat with English Kokoro voice | 8766, 8765, 8768 |
| Try STT with both Kokoro voices, no chat | 8766, 8769, 8768 |

Details: [STT.md](STT.md#memory).

About the Kokoro start: `.\start_kokoro_tts.ps1` is equivalent to the Window 4 command. The script only does `Set-Location` to its own folder and runs
the same interpreter with `-X utf8`. Neither form is "preferred" functionally: without `-X utf8`
the server re-launches itself in UTF-8 mode (one extra process). The script is location-independent
and avoids the extra process.

### Why this order

- **Dependencies:** none of the services refuses to start without the others. Order matters only for memory and for what the page reports at load.
- **Kokoro last, on purpose:** Kokoro is the only service that checks free commit and backs off. Starting it last means it adapts to what is left instead of the unguarded services crashing later.
- **Starting Kokoro last does not guarantee Russian loads.** It guarantees that Kokoro will not take memory the others need. Whether `masha` loads depends on `free_commit_mb` at that moment (needs ≥ 4000 MB after English has loaded). On the reference machine it usually does not.
- If Russian `masha` matters more than everything else, see the options in [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md#6-options-for-getting-russian-masha-to-load).

### Optional Kokoro switches (set in the window before starting)

```powershell
$env:KOKORO_LANGS = 'en'      # or 'ru' or 'en,ru' (default)
Remove-Item Env:KOKORO_LANGS  # back to default
```

`KOKORO_SKIP_MEMCHECK=1` disables the memory guard. **Do not use it while other services are running.**

## 5. Health checks

```powershell
foreach ($port in 8765, 8766, 8767, 8768, 8769) {
    try   { '{0}  {1}' -f $port, (Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 5 | ConvertTo-Json -Compress -Depth 4) }
    catch { '{0}  DOWN  {1}' -f $port, $_.Exception.Message }
}
```

How to read the result:

| Port | Healthy looks like | Caveat |
|---|---|---|
| 8765 | `"ok":true,"local_tts":true` | says nothing about Ollama, Piper or Kokoro |
| 8766 | `"ok":true` | — |
| 8767 | `"ok":true` | static; does not prove the models exist |
| 8768 | `"loading":false` and `"ready":{"ru":…,"en":true}` | `ok:false` with `ready.en:true` is the normal state on a memory-constrained machine; read `errors` |
| 8769 | `"ready":true,"model":"small","compute_type":"int8"` | `ready:false` with `loading:false` → read `error` |

Kokoro readiness in one line:

```powershell
$h = Invoke-RestMethod http://127.0.0.1:8768/api/health
'loading={0} en={1} ru={2} free_commit_mb={3}  {4}' -f $h.loading, $h.ready.en, $h.ready.ru, $h.free_commit_mb, ($h.errors | ConvertTo-Json -Compress)
```

## 6. Frontend check

Open <http://localhost:8765>. The header should read `MADLAD-400-3B INT8 + qwen3:1.7b + Uzbek TTS ✓`.
Pick a language under "Suhbat tili" and press **Test ovozi**; watch the status line under the input box:

| Language | Expected status line |
|---|---|
| O‘zbekcha | `Mahalliy Uzbek TTS ovozi ijro etilmoqda…` then `Tayyor.` |
| Inglizcha | `Kokoro (Heart) ovozi ijro etilmoqda…` then `Tayyor.` |
| Ruscha, `masha` loaded | `Kokoro (Masha) ovozi ijro etilmoqda…` |
| Ruscha, `masha` not loaded | `Kokoro (Masha) TTS xatosi: ru modeli tayyor emas: MemoryError…` and nothing plays (no Piper fallback since 2026-10-14) |

**Voice input check** (needs 8769 and a working microphone): press **🎤 Gapirish**, allow the
microphone, say a sentence, press **⏹ To‘xtatish**. Expected: `Nutq matnga aylantirilmoqda…`, then
`Transkript tayyor · til: ru, ishonch 94% …` and the text appears in the message box **without being
sent**. Edit if needed, press **Yuborish**. `STT xatosi: mikrofonga ruxsat berilmadi…` means the
browser blocked the microphone; `STT serveriga ulanib bo‘lmadi (8769)` means the STT server is not running.
The microphone works only when the page is opened as `http://localhost:8765` or `http://127.0.0.1:8765`.

Use a browser **on the same machine**; from another device Kokoro and Piper are unreachable (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).

## 7. End-to-end smoke test

See [TESTING.md §3](TESTING.md#3-end-to-end-smoke-test) for a copy-paste script that exercises chat and every TTS engine and validates the WAV files.

## 8. Logs

Services print to their console window; nothing is written to disk by default. To keep a log, start a service with redirection:

```powershell
.\.venv-kokoro\Scripts\python.exe .\kokoro_tts_server.py *> logs\kokoro_tts.log
```

(With `*>` the window shows nothing; use `Get-Content logs\kokoro_tts.log -Wait -Tail 20` in another window.)
The existing `logs\*.log` files come from the 2026-10-13 session; only `kokoro_tts.out.log` has content.
Log prefixes: `[HTTP]` chat backend, `[TTS HTTP]`/`TTS:` Uzbek, `[Piper]`/`[Piper HTTP]`, `[Kokoro]`/`[Kokoro HTTP]`.

## 9. Shutdown

Preferred: press `Ctrl+C` in the service's window (or close the window).

If the window is gone, stop **only** the process that owns the port — check the command line first:

```powershell
$port = 8768
$p = (Get-NetTCPConnection -LocalPort $port -State Listen).OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId=$p" | Select-Object ProcessId, CommandLine   # confirm it is the right script
Stop-Process -Id $p
```

Do **not** use `Stop-Process -Name python` or `taskkill /IM python.exe`: that kills every service and
any unrelated Python program. Stopping the port owner also ends its venv-launcher parent.

Ollama is stopped from its tray icon; it is independent of this project.

## 10. Recovery from an unexpected exit

1. Find out what is still up (§2) and how much commit is free (§3).
2. Look at the dead service's window for the last lines (a Python traceback, `MemoryError`, or nothing at all — a silent exit with several services dying together points to commit exhaustion; see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#service-crashes-after-another-model-loads)).
3. If commit is nearly exhausted, stop the Kokoro server first (it is the largest optional consumer), then restart the missing services in the order of §4.
4. Re-run the health checks (§5) and the smoke test.
5. Reload the browser page (it probes health only at load).

Nothing needs repair after a crash: the services keep no state on disk.

## 11. Determining the configured chat model

```powershell
Select-String -Path .\server.py -Pattern '^QWEN_MODEL|^OLLAMA_URL'
(Invoke-RestMethod http://127.0.0.1:8765/api/health).model          # what the running backend uses
(Invoke-RestMethod http://127.0.0.1:11434/api/tags).models.name     # what Ollama has
```

On 2026-10-13: code `qwen3:1.7b` (`VERIFIED`); Ollama had `qwen3:1.7b`, `qwen3:4b`, `qwen3-uz:latest`, `qwen3-fast:latest` (`VERIFIED`). Only `qwen3:1.7b` is used by the code.
