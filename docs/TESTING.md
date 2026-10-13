# Testing

- **Last verified:** 2026-10-13
- **Status:** procedures are `PROPOSED`/manual; results in §4 are `HISTORICAL TEST RESULT` from 2026-10-13. **No test was run during the documentation audit** except read-only checks listed in §5.
- **Related:** [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md), [API_REFERENCE.md](API_REFERENCE.md), [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md)

## 1. What exists

- **No automated test suite, no test runner, no CI.**
- Root files named `test_*.py` are one-off experiment scripts from the translation prototyping phase (NLLB/MADLAD). They load multi-GB models, hard-code paths, and assert nothing. Do not treat them as tests and do not run them next to the live services.
- `kokoro-test-output\*.wav`, `test_en.wav`, `test_ru.wav`, `piper_api_test.wav` are saved outputs of earlier manual tests.
- The scripts used for the 2026-10-13 Kokoro tests were temporary and are not in the repository.

## 2. Testing each component independently

Prerequisite for every command: the service in question is running ([WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md)).
Define the helper once per PowerShell session:

```powershell
function Send-Json($Url, $Object, $OutFile) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Object | ConvertTo-Json -Compress))
    if ($OutFile) { Invoke-WebRequest $Url -Method Post -Body $bytes -ContentType 'application/json' -UseBasicParsing -OutFile $OutFile }
    else          { Invoke-RestMethod  $Url -Method Post -Body $bytes -ContentType 'application/json' }
}
function Test-Wav($Path) {   # a 200 response is not enough: check the audio itself
    $b = [IO.File]::ReadAllBytes((Resolve-Path $Path))
    if ($b.Length -lt 44 -or [Text.Encoding]::ASCII.GetString($b,0,4) -ne 'RIFF') { return "$Path : NOT A WAV" }
    $rate = [BitConverter]::ToInt32($b,24); $ch = [BitConverter]::ToInt16($b,22); $bits = [BitConverter]::ToInt16($b,34)
    $peak = 0; for ($i = 44; $i -lt $b.Length - 1; $i += 200) { $v = [math]::Abs([int][BitConverter]::ToInt16($b,$i)); if ($v -gt $peak) { $peak = $v } }
    '{0} : {1} Hz, {2} ch, {3} bit, ~{4:N2} s, peak {5} {6}' -f $Path, $rate, $ch, $bits, (($b.Length-44)/($rate*$ch*$bits/8)), $peak, $(if ($peak -lt 300) {'<-- SILENT?'})
}
```

(`Test-Wav` assumes the canonical 44-byte header, which all three local engines produce, and samples every 100th frame.)

| Component | Test | Pass criteria |
|---|---|---|
| Ollama | `Invoke-RestMethod http://127.0.0.1:11434/api/tags` | list contains `qwen3:1.7b` |
| Uzbek TTS | `Send-Json http://127.0.0.1:8766/api/tts @{text='Assalomu alaykum!'} uz.wav; Test-Wav uz.wav` | 22050 Hz, 1 ch, 16 bit, not silent |
| Uzbek TTS via proxy | same with port 8765 | same |
| Piper | `Send-Json http://127.0.0.1:8767/api/tts @{text='Hello! This is a voice test.'; language='en'} p.wav; Test-Wav p.wav` | 22050 Hz, not silent |
| Kokoro EN | `Send-Json http://127.0.0.1:8768/api/tts @{text='Hello! How can I help you?'; language='en'} k.wav; Test-Wav k.wav` | 24000 Hz, 1 ch, 16 bit, not silent |
| Kokoro RU | as above with Russian text and `language='ru'` | `200` only if `ready.ru` is true; otherwise `503` is the **expected** result |
| Kokoro voice identity | `(Invoke-WebRequest … -UseBasicParsing).Headers['X-TTS-Voice']` | `af_heart` / `masha` |
| Chat (EN, no translation) | `Send-Json http://127.0.0.1:8765/api/chat @{text='Hello, how are you?'}` | `ok=true`, `language=en`, non-empty `answer` |
| Chat (RU) | `Send-Json http://127.0.0.1:8765/api/chat @{text='Привет, как дела?'}` | `language=ru`, Cyrillic `answer`, non-zero translation timings |
| Chat (UZ) | `Send-Json http://127.0.0.1:8765/api/chat @{text='Salom, bugun qalaysan?'}` | `language=uz`, Latin-script `answer` |

Error-path checks for Kokoro (expected status in brackets): empty text [400], `language='uz'` [400],
2001 characters [413], text `'@@@ ###'` with `language='ru'` [422, Russian loaded only].

## 3. End-to-end smoke test

Run after all services are up. It does not need much extra memory.

```powershell
Set-Location C:\local-ai-translator
# (define Send-Json and Test-Wav from §2 first)
$out = Join-Path $env:TEMP 'lat-smoke'; New-Item -ItemType Directory -Force $out | Out-Null
foreach ($port in 8765,8766,8767,8768) {
    try { $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 5; "{0} health ok" -f $port } catch { "{0} DOWN" -f $port } }
$k = Invoke-RestMethod http://127.0.0.1:8768/api/health; "kokoro ready: en=$($k.ready.en) ru=$($k.ready.ru)"

$r = Send-Json http://127.0.0.1:8765/api/chat @{ text = 'Hello, how are you?' }
"chat: lang=$($r.language) total=$($r.timings.total)s answer=$($r.answer)"

Send-Json http://127.0.0.1:8765/api/tts @{ text = 'Assalomu alaykum! Xush kelibsiz.' } "$out\uz.wav";           Test-Wav "$out\uz.wav"
Send-Json http://127.0.0.1:8768/api/tts @{ text = $r.answer; language = 'en' } "$out\en.wav";                  Test-Wav "$out\en.wav"
Send-Json http://127.0.0.1:8767/api/tts @{ text = 'Здравствуйте! Это тест голоса.'; language = 'ru' } "$out\ru_piper.wav"; Test-Wav "$out\ru_piper.wav"
if ($k.ready.ru) { Send-Json http://127.0.0.1:8768/api/tts @{ text = 'Здравствуйте! Меня зовут Маша.'; language = 'ru' } "$out\ru_masha.wav"; Test-Wav "$out\ru_masha.wav" }
else { 'Kokoro RU not loaded - skipped (expected on a memory-constrained machine)' }
```

Then do the manual frontend check from [WINDOWS_RUNBOOK.md §6](WINDOWS_RUNBOOK.md#6-frontend-check): the
HTTP tests cannot prove that the browser actually plays sound. Finally, **listen** to the WAV files —
no automated check here measures intelligibility or naturalness.

This script was written for the documentation and has **not been executed** (`NOT VERIFIED`).

## 4. Recorded results — 2026-10-13 (`HISTORICAL TEST RESULT`)

Environment: reference machine, CPU. Tests driven by temporary Python scripts over HTTP and by the in-app browser.

**A. Kokoro, English + Russian loaded (before the memory guard existed)**

| Test | Result |
|---|---|
| `/api/health` | `ok:true`, both ready, `load_seconds` 19.09, `memory_mb` 4204 |
| 4 required sentences (2 RU `masha`, 2 EN `af_heart`), twice | all `200 audio/wav`, 24 kHz mono 16-bit, RMS 1171–1627, 38–51 % of samples above the silence threshold; durations/timings in [MEMORY_AND_PERFORMANCE.md §8](MEMORY_AND_PERFORMANCE.md#8-performance-historical-test-result-2026-10-13-cpu-not-rerun) |
| Response headers | `X-TTS-Voice: masha` for `ru`, `af_heart` for `en` |
| Determinism | same text → identical duration |
| Error cases | empty/missing text 400; `uz`/`xx`/missing language 400; 2001 chars 413; bad JSON 400; JSON array 400; symbols-only Russian 422; non-numeric speed 400; unknown GET/POST path 404 |
| Long text | RU 736 chars → 55.0 s audio in 22.5 s; EN 1920 chars → 110.1 s audio in 56.1 s |
| 6 parallel mixed requests | 5 × `200` with the same durations as serial runs; 1 × `503` (queue limit); server healthy afterwards |
| Russian G2P | stress, `ё` restoration, homograph `замок`, `дорого`, numbers — correct at phoneme level (examples in [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md)) |
| **Side effect** | services on 8765/8766/8767 found dead afterwards — see the incident in [MEMORY_AND_PERFORMANCE.md §5](MEMORY_AND_PERFORMANCE.md#5-incident-of-2026-10-13-why-the-guard-exists) |

**B. All four services, Kokoro with guard (English only loaded)**

| Test | Result |
|---|---|
| Kokoro `/api/health` | `ready.en:true`, `ready.ru:false`, `errors.ru` = MemoryError (1653 MB free, 4000 needed) |
| Kokoro during load | `/api/health` `loading:true`; `/api/tts` → 503 |
| CORS preflight to 8768 | `204`, `Access-Control-Allow-Origin: *` |
| Kokoro RU request | `503` |
| Kokoro EN | `200`, 2.92 s audio in 1.14 s |
| Uzbek TTS direct (8766) and via proxy (8765) | `200`, 22 050 Hz, 3.41 s / 3.83 s audio, 0.59 s / 0.51 s |
| Piper EN / RU | `200`, 22 050 Hz, 2.02 s / 2.65 s audio, 5.35 s / 3.42 s |
| Chat `POST /api/chat` (English) | `200`, answer "I'm doing well, thank you.", 7.28 s |
| Page served | `200`, contains the `kokoro` option |
| Frontend "Test ovozi", EN | `Kokoro (Heart) ovozi ijro etilmoqda…` → `Tayyor.`; audio element played to the end (2.25 s) |
| Frontend "Test ovozi", RU | Kokoro error shown, Piper fallback played to the end (2.55 s) |
| Frontend "Test ovozi", UZ | Uzbek ONNX played to the end (3.95 s) |

Not covered by any test so far: chat in Russian or Uzbek through the full pipeline in this session;
`masha` played from the browser; other browsers; a remote LAN client; long-running stability;
perceptual voice quality; Piper/Uzbek error paths; behaviour when Ollama is down.

## 5. Checks actually run during the documentation audit (2026-10-13)

Read-only: directory inventory; `pip freeze` of four environments; `pyvenv.cfg`; SHA256 of Piper and
Uzbek models and `ru_g2p.py`; Ollama `/api/version`, `/api/tags`, `/api/ps`; listening ports
(only 11434 was open); memory and pagefile status; secret scan; nested-repository status;
Markdown link check; endpoint/port/path consistency checks against source. No service was started or stopped.

## 6. Proposed automated tests (`PROPOSED`)

See [ROADMAP.md](ROADMAP.md): unit tests for `detect_language` and `uzbek_cyrillic_to_latin` (pure
functions, but currently importing `server.py` loads MADLAD), an HTTP contract test per service, and a WAV validity check.
