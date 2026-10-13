# Memory and performance

- **Last verified:** 2026-10-13
- **Status:** machine facts `VERIFIED`; thresholds `SOURCE-CODE CONFIRMED`; all process measurements and timings are `HISTORICAL TEST RESULT` from 2026-10-13 and were **not rerun** for this document
- **Related source:** `kokoro_tts_server.py` (`REQUIRED_FREE_MB`, `free_commit_mb`, `load_models`)
- **Related:** [adr/0003-memory-aware-kokoro-loading.md](adr/0003-memory-aware-kokoro-loading.md), [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

> **The one thing to remember:** on the 8 GB reference machine the full system does not fit.
> The limit that is hit is not RAM but the Windows **commit limit**, and when it is hit, *other*
> processes die — not necessarily the one that asked for the memory.

## 1. Concepts

| Term | What it is | Where to read it |
|---|---|---|
| **Physical RAM** | Installed memory. 7.9 GB usable here. | `Win32_OperatingSystem.TotalVisibleMemorySize` |
| **Working set / RSS** | The part of a process's memory currently in RAM. Shrinks when Windows pages idle memory out; a process holding a 3 GB model can show a few MB of RSS when idle. | Task Manager "Memory", `Get-Process … WorkingSet64`, Kokoro `memory_mb` |
| **Committed (private) memory** | Memory a process has been *promised* (RAM or pagefile must be able to back it), whether or not it is touched. Always ≥ what is really used; often much larger than RSS. | `Get-Process … PrivateMemorySize64`, Task Manager "Commit size" |
| **System commit limit** | RAM + current pagefile size. The sum of all commits can never exceed it. | `TotalVirtualMemorySize` (18.4 GB here) |
| **Free commit** | Commit limit − total committed. When this reaches zero, allocations fail everywhere. | `FreeVirtualMemory`, Kokoro `free_commit_mb` |
| **Pagefile** | Disk file that extends the commit limit and holds paged-out memory. | `Win32_PageFileUsage` |
| **Disk size of a model** | Bytes on disk. Only loosely related to memory use: MADLAD is 2.8 GB on disk but its process committed ≈ 9.9 GB. | Explorer |
| **Start-up vs inference memory** | Loading creates temporary copies (peak); after loading some is released; each request then adds short-lived buffers. Guards must be sized for the **peak**. | measurements below |

Why insufficient commit hurts *other* services: when the limit is reached, the next allocation in
**any** process fails. Native libraries (ONNX Runtime, CTranslate2, PyTorch) often abort the process
on a failed allocation instead of raising a Python exception. A service that was idle and healthy can
therefore disappear because a different service loaded a model.

## 2. Reference machine (`VERIFIED` 2026-10-13)

| Fact | Value | Method |
|---|---|---|
| OS | Windows 11 Pro | `Win32_OperatingSystem.Caption` |
| CPU | Intel Core i7-9700K, 8 cores / 8 threads, no GPU use | `Win32_Processor`; all services use CPU providers (source) |
| Physical RAM | 7.9 GB | `TotalVisibleMemorySize` |
| Commit limit | 18.4 GB | `TotalVirtualMemorySize` |
| Pagefile | `C:\pagefile.sys`, 10 752 MB allocated, **system-managed** | `Win32_PageFileUsage`, `AutomaticManagedPagefile = True` |
| Free commit, project services stopped, Ollama with `qwen3:1.7b` loaded | 8.8 GB | `FreeVirtualMemory` at audit time |

Because the pagefile is system-managed, Windows may grow it, so the commit limit is not strictly
fixed; whether and how far it grows on this machine was not tested (`NOT VERIFIED`).

## 3. Measurements

All rows: date 2026-10-13, same machine, **not rerun**. "Private" = `PrivateMemorySize64` / psutil
`private`; "RSS" = working set / psutil `rss`.

| # | What | Value | Method / source | Status |
|---|---|---|---|---|
| M1 | `server.py` (MADLAD) process | Private ≈ 9 902 MB; RSS 344–807 MB | `Get-Process` on the port owner, twice | HISTORICAL |
| M2 | `tts_onnx_server.py` process | Private 416–664 MB; RSS 145–270 MB | `Get-Process` | HISTORICAL |
| M3 | `piper_tts_server.py` process (idle) | Private ≈ 13 MB | `Get-Process` | HISTORICAL |
| M4 | Ollama `qwen3:1.7b` loaded | 1.36 GB | `GET /api/ps` `size` | VERIFIED (audit) |
| M5 | Kokoro, English only, running server | RSS 1 385 MB (`memory_mb`); later RSS 1 352 MB / Private 1 846 MB | `/api/health`, `Get-Process` | HISTORICAL |
| M6 | Kokoro English component steps (one process) | Private: `import torch` 423 → `import kokoro` 593 → `KModel` 1 637 → `KPipeline` 1 739 → after 2 inferences 1 506 MB | psutil probe script | HISTORICAL |
| M7 | Kokoro-RU `KModel` alone | Private 593 → 1 636 MB | psutil probe script | HISTORICAL |
| M8 | Kokoro English + Russian, one process (script) | RSS: imports 380 → +English 1 382 → +RuG2P 3 600 → +Russian model 4 167 MB | psutil | HISTORICAL |
| M9 | Kokoro English + Russian, running server | RSS 4 204 MB after load; 2 973 MB after a test run; Private ≈ 5 530 MB | `/api/health`, `Get-Process` | HISTORICAL |
| M10 | RuG2P (RUAccent + espeak) alone | RSS +≈ 2.2 GB (from M8); a separate probe passed 2 600 MB private and was aborted by its own safety cap, so the true private figure is **> 2.06 GB, exact value unknown** | psutil | HISTORICAL |
| M11 | Free commit with 8765+8766+8767 running, Kokoro stopped | ≈ 3.3 GB | `FreeVirtualMemory` | HISTORICAL |
| M12 | Free commit with those three + Kokoro English | 1 653–1 654 MB | Kokoro log and `/api/health` | HISTORICAL (recorded in `logs\kokoro_tts.out.log`) |
| M13 | Russian refused with HTTP 503 at "≈ 1 270 MB free commit" | 1 270 MB | reported by the project owner; **no local record** (the recorded value is M12) | NOT VERIFIED |
| M14 | Kokoro load time | English + Russian 18.9–19.1 s; English only 9.6 s | `/api/health` `load_seconds` | HISTORICAL |

Summary figures used elsewhere in the docs (rounded from the table): English-only ≈ 1.4 GB RSS / ≈ 1.8 GB
commit; English + Russian ≈ 4.2 GB RSS / ≈ 5.5 GB commit; RUAccent/G2P ≈ 2.2 GB; MADLAD ≈ 9.9 GB commit.

Unexplained: why a 2.8 GB INT8 model commits ≈ 9.9 GB (M1). Not investigated (`NOT VERIFIED`).

## 4. The Kokoro memory guard (`SOURCE-CODE CONFIRMED`)

In `kokoro_tts_server.py`:

```python
REQUIRED_FREE_MB = {"en": 2200, "ru": 4000}
```

- Before loading each language, `free_commit_mb()` calls `GlobalMemoryStatusEx` and reads
  `ullAvailPageFile` (commit available to the process). On non-Windows systems it returns `None` and the check is skipped.
- If free commit is below the threshold, the language is **not loaded**; `errors[lang]` gets
  `MemoryError: xotira yetarli emas: bo'sh commit <N> MB, kerak <threshold> MB (…)`, and
  `POST /api/tts` for that language answers `503`.
- Languages load in the order English → Russian, so the Russian check sees memory *after* English is loaded.
- The check happens **once, at start-up**. It is not repeated later, there is no retry, and nothing
  is unloaded if memory becomes tight afterwards. To retry Russian, restart the Kokoro server.
- `KOKORO_SKIP_MEMCHECK=1` bypasses the check; `KOKORO_LANGS` restricts which languages are attempted.

The thresholds are the measured peaks plus a margin (English peak ≈ 1.74 GB private → 2200;
Russian adds ≈ 3.5 GB of commit on top of English → 4000). They are engineering estimates from
one machine, not guarantees.

Consequence: for both Kokoro voices, free commit must be roughly **≥ 6.2 GB before the Kokoro
server starts** (2200 for English is only a gate; English then consumes ≈ 1.8 GB, and ≥ 4000 must remain).

## 5. Incident of 2026-10-13 (why the guard exists)

1. Three services were running (8765, 8766, 8767) plus Ollama. Free RAM was ≈ 0.9 GB.
2. A first version of the Kokoro server (no guard) loaded English + Russian (≈ 5.5 GB commit) and served a test suite successfully.
3. During/after that test the processes on 8765, 8766 and 8767 were found dead (connection refused). No Python traceback or Windows error event was found for them.
4. With `server.py` alone committing ≈ 9.9 GB against an 18.4 GB limit, commit exhaustion is the **most likely** cause. This was **not proven** (their console windows were not inspected). Status: probable cause, `NOT VERIFIED`.
5. The services were restarted with their normal commands; the guard and `KOKORO_LANGS` were then added. With the guard, Kokoro loaded English only and the other three services stayed up through the remaining tests.

## 6. Options for getting Russian `masha` to load

None of these has been applied; they are operator/owner decisions (`PROPOSED`).

| Option | Effect | Cost / risk |
|---|---|---|
| Increase the pagefile (fixed size, e.g. +6–8 GB) | Raises the commit limit so everything can be committed | Heavier paging → latency spikes; a system setting, change deliberately |
| Add RAM (16 GB+) | Removes the constraint properly | Hardware |
| Run Kokoro with `KOKORO_LANGS=ru` and let English fall back to Piper | Saves ≈ 1.8 GB | English voice quality changes; still needs ≥ 4000 MB free |
| Do not run `server.py` while testing voices | Frees ≈ 10 GB | No chat |
| Reduce RUAccent memory (smaller homograph model, etc.) | Could save hundreds of MB | Changes stress accuracy; see [ROADMAP.md](ROADMAP.md) |

## 7. Safe recovery when memory runs out

1. Do not start anything new. Check free commit ([WINDOWS_RUNBOOK.md §3](WINDOWS_RUNBOOK.md#3-check-memory-before-starting)).
2. Stop the Kokoro server (largest optional consumer) by port ([§9](WINDOWS_RUNBOOK.md#9-shutdown)).
3. Restart whichever of 8766, 8767, 8765 died, in that order.
4. Start Kokoro last; read `/api/health` to see what loaded.
5. Never set `KOKORO_SKIP_MEMCHECK=1` to "make Russian work" on a machine in this state.

## 8. Performance (`HISTORICAL TEST RESULT`, 2026-10-13, CPU, not rerun)

Speech generation, measured client-side over HTTP on localhost:

| Engine | Input | Audio length | Generation time |
|---|---|---|---|
| Kokoro RU `masha` | "Здравствуйте! Меня зовут Маша. Чем я могу вам помочь?" | 6.79 s | 2.40 s first request after load, 2.18 s second |
| Kokoro RU `masha` | "Сегодня прекрасная погода, и я очень рада вас видеть!" | 4.50 s | 1.65–1.67 s |
| Kokoro EN `af_heart` | "Hello! I'm happy to see you today. How can I help you?" | 3.50 s | 1.19–1.21 s |
| Kokoro EN `af_heart` | "That's wonderful! Let me explain it to you." | 2.92 s | 0.94–1.14 s |
| Kokoro RU, long | 736 characters | 55.0 s | 22.5 s |
| Kokoro EN, long | 1 920 characters | 110.1 s | 56.1 s |
| Uzbek ONNX | "Assalomu alaykum! Xush kelibsiz. Sizga qanday yordam bera olaman?" | 3.4–3.8 s | 0.51–0.59 s |
| Piper EN `lessac` | "Hello! This is a voice test." | 2.02 s | 5.35 s |
| Piper RU `irina` | "Здравствуйте! Это тест голоса." | 2.65 s | 3.42 s |

Observations:

- Kokoro ran at roughly 0.32–0.37× real time for short sentences and ≈ 0.4–0.5× for long ones; there is no noticeable first-request penalty beyond ≈ 0.2 s.
- No engine streams: the whole WAV is generated before the first byte is returned, so **time to first audio = generation time**. A 2000-character English answer means almost a minute of silence.
- Piper is slow per request because it starts a new process and reloads the model each time.
- Requests to Kokoro are serialized; 6 simultaneous requests took 9.3 s wall-clock in total, the 6th was rejected with `503` (queue limit).

Chat pipeline (one sample, English, so no translation): `qwen` 7.28 s, total 7.28 s.
Translation timings from the older `benchmarks\comparison.csv` (date of run unknown): MADLAD ≈ 1.0–1.5 s
per short sentence versus NLLB ≈ 0.3–0.5 s.

Do not run memory-heavy benchmark combinations (full Kokoro next to MADLAD) on the reference machine.
