# Current best setup (decision record, 2026-10-17)

This is the configuration the project runs with after all evaluations so far, with the numbers behind
each choice. Every number below is **measured** on the reference PC (Windows 11, i7-9700K, 7.9 GB RAM,
GTX 1650 4 GB) unless it says *estimate*. Raw data is in git under `stt-eval/` (see [Where the data is](#where-the-data-is)).

## The combination

```
microphone ──► STT :8769 ──────────────► chat :8765 ─────────────────────────────► TTS
               uz: NavAI whisper-small     gemma3:4b reads the original text,        uz: female VITS ONNX :8766 (default)
                   uzbek (CT2 int8)        answers in English;                           male Uzbek F5-style :8770 (GPU, optional)
               ru/en: Faster-Whisper       MADLAD-400 3B translates the answer        ru: Kokoro masha / male dima :8768
                   small (CT2 int8)        into uz/ru (English as is)                 en: Kokoro af_heart / male am_michael :8768
                                                                                      (Piper irina/lessac, male dmitri/ryan :8767,
                                                                                       only in its own mode)
```

| Stage | Choice | Key settings | Service / file |
|---|---|---|---|
| Speech-to-text, Uzbek | `navai-uz/whisper-small-uzbek`, CTranslate2 int8, CPU | `?language=uz` (or auto with p(ru), p(en) < 0.2); beam 5, VAD, `without_timestamps=True`, `no_repeat_ngram_size=4`, no prompt; SHA256-checked; memory policy `auto` | `stt_server.py`, port 8769, `.venv-stt` |
| Speech-to-text, Russian / English | Faster-Whisper `small`, int8, CPU | unchanged production settings; also does language detection in auto mode | same |
| Chat model | **`gemma3:4b`** (Ollama, Q4_K_M) | `temperature 0.4`, `num_predict 100`, `num_ctx 2048`, no history; loaded when `server.py` starts and never unloaded (`keep_alive -1`) | Ollama :11434 |
| Chat pipeline | **hybrid**: no input translation; the model reads the user's Uzbek/Russian text, answers in English; MADLAD translates the answer | system prompt: answer in English in 1–3 sentences; for uz/ru "the user may write in Uzbek or Russian, possibly with speech-recognition errors; understand the message in that language, but always answer in English" | `server.py`, port 8765, `.venv` |
| Output translation | MADLAD-400 3B, CTranslate2 int8, CPU | greedy, ≤ 128 tokens; Uzbek Cyrillic → Latin | in `server.py` |
| TTS Uzbek, default | **female**: fine-tuned VITS, ONNX, CPU | `noise_scale 0.667`, `noise_scale_w 0.8`, `length_scale 1.0` (owner-approved sample `stt-tts-uz\outputs\finetuned_test.wav`) | `tts_onnx_server.py`, port 8766 |
| TTS Uzbek, optional | **male**: Uzbek_TTS (F5-style flow matching), CUDA | reference `test_erkak.wav`, `nfe_step 8`, `speed 1.0`, `cfg_strength 2` (owner-approved sample `Uzbek_TTS-test\test_uzbek_tts.wav`) | `uz_male_tts_server.py`, port 8770 |
| TTS Russian / English | Kokoro: `masha` / male `dima` (RU), `af_heart` / male `am_michael` (EN) | default page mode "Kokoro"; Piper (`irina`/`lessac`, male `dmitri`/`ryan`) only in "Piper" mode; no browser voices | `kokoro_tts_server.py` :8768, `piper_tts_server.py` :8767 |
| Proxies in `server.py` | `/api/transcribe` (STT), `/api/tts` (Uzbek), `/api/tts/kokoro`, `/api/tts/piper` — every request from the page goes to 8765, so a phone through the HTTPS tunnel gets all voices | — | `server.py` |
| Page | `local_voice_chat.html` | microphone language selector (Avto/O‘zbekcha/Русский/English), "Ovoz" (Ayol/Erkak, all languages), "Ruscha / inglizcha ovoz" (Kokoro/Piper) | served by `server.py` |

## Why — the numbers

### Speech-to-text: NavAI for Uzbek, `small` for Russian/English

| Test | Before (`small` for everything) | Now |
|---|---|---|
| 120 real Uzbek recordings (FLEURS test, benchmark) | WER 1.239, 12/120 repetition loops, median 5.9 s | NavAI WER **0.207**, 0 loops, median 3.1 s |
| 40 **new** FLEURS Uzbek recordings (integration test) | WER 1.164, CER 0.435, median 6.3 s | WER **0.223**, CER 0.093, median 3.1 s |
| 12 synthetic robot commands | WER 3.70, 4 loops | WER 0.91, 0 loops (still unusable for driving a robot) |
| Russian/English (28 requests, formats, noise) | WER 0.007 | **identical text 28/28** — NavAI is never used for ru/en (it cannot transcribe them, WER ≈ 1.0) |
| iPhone Safari through the HTTPS tunnel | — | works (owner's manual test, 2026-10-16) |

Sources: [STT_EVALUATION.md](STT_EVALUATION.md), [STT.md § Uzbek routing](STT.md#uzbek-routing-navai--integrated-2026-10-16).

### Chat: gemma3:4b + hybrid

Problem being solved: MADLAD mistranslated misspelled or misrecognised Uzbek **before** the model saw it.
3 models × 4 pipelines were compared ([LLM_COMPARISON.md](LLM_COMPARISON.md)):

| Uzbek questions (25 clean + 25 STT text) | Clean | STT text | Median s |
|---|---|---|---|
| **gemma3:4b hybrid (chosen)** | **20/25** | **19/25** | 6.7 |
| gemma3:4b dual (original + translation) | 20/25 | 16/25 | 4.3 |
| gemma3:4b madlad | 19/25 | 16/25 | 8.2 |
| qwen3:4b-instruct madlad | 19/25 | 14/25 | 7.6 |
| qwen3:1.7b madlad (**previous setup**) | 17/25 | 10/25 | 2.7 |
| Qwen3-4B Thinking (17 questions) | 7/9 | 4/8 | 77 |

| Other sets | Chosen setup | Previous setup | Best seen |
|---|---|---|---|
| Russian, 20 questions | 19/20, 6.3 s (gemma hybrid) | 17/20, 2.0 s | 20/20, 2.6 s (gemma direct) |
| English, 20 questions | 20/20, 3.2 s | 18/20, 0.2 s | 20/20, 1.3 s (qwen3:4b-instruct) |
| Robot commands → action label (12 clean + 11 STT) | 8/12 + 4/11 | 9/12 + 3/11 | 12/12 + 5/11 (qwen3:4b-instruct reading the original) |

One pipeline for all languages was the owner's decision (Russian direct was one question better). MADLAD's output
translation still loses some correct answers (6 of 42 correct English answers became wrong in Uzbek).

### TTS: two Uzbek voices, Kokoro for Russian/English

Same 4 Uzbek sentences (40–105 characters), one warm-up excluded (`stt-eval/tts_uz/`):

| Voice | Median generation | Real-time factor (generation ÷ audio) | 105-char sentence | Memory |
|---|---|---|---|---|
| Female, VITS ONNX, CPU | **1.0 s** | 0.30 | 1.8 s for 6.4 s audio | 0.4–0.7 GB commit |
| Male, Uzbek_TTS, GTX 1650 | 18.2 s | 3.96 | 29.4 s for 7.5 s audio | 0.68 GB VRAM loaded, **1.94 GB** peak |
| Male, Uzbek_TTS, CPU (i7-9700K) | 28.3 s | 6.11 | 41.9 s | — (not used) |

The male voice stays on the GPU (the CPU is 1.5× slower and is shared with MADLAD, Ollama and STT). It is optional and
off by default because of its speed on this PC.

Russian/English, 3 sentences per voice, one warm-up excluded (`stt-eval/tts_ruen/results.json`, 2026-10-17):

| Engine | Language | Female voice, median | Male voice, median |
|---|---|---|---|
| Kokoro | Russian | `masha` 1.52 s | `dima` 1.41 s |
| Kokoro | English | `af_heart` 0.99 s | `am_michael` 1.11 s |
| Piper | Russian | `irina` 3.37 s | `dmitri` 3.39 s |
| Piper | English | `lessac` 3.24 s | `ryan` 3.23 s |

Male voices cost the same as female ones (Kokoro: same model, another 0.5 MB voicepack; Piper: another 63 MB
voice file, one process per request). Kokoro stays the default (≈ 2–3× faster than Piper).

## End-to-end, measured (reference PC, 2026-10-17)

Spoken Uzbek questions (TTS recordings of `questions_uz.json`) sent through `server.py` exactly like the page does:
`/api/transcribe?language=uz` → `/api/chat` → `/api/tts` (`stt-eval/scripts/e2e_voice_test.py`, `stt-eval/e2e/`).
Running at the same time: 8765, 8766, 8769, 8770 and Ollama (free commit fell to 1.2 GB).

| Voice | Questions | Correct | STT | Chat | TTS | **Total, median** | Total, mean |
|---|---|---|---|---|---|---|---|
| Female | 6 | 4/6 | 2.4 s | 6.4 s | 0.9 s | **9.9 s** | 12.3 s |
| Male | 3 | 3/3 | 2.7 s | 8.1 s | 29.1 s | **39.6 s** | 40.2 s |

- The **first** question after start took 25.8 s (Ollama loading gemma3:4b: LLM 15.6 s); later ones 7–13 s.
  **Fixed the same day:** `server.py` now preloads gemma3:4b at start (≈ 12 s, in the background) and keeps it
  loaded; the first question after a cold start then took 3.0 s (chat part), like any other question.
  Quality and normal latency unchanged (Uzbek 39/50, Russian 19/20, English 20/20; `stt-eval/chat_eval/keep_alive_*`).
  Cost: gemma3:4b stays in memory (≈ 3.3 GB, 1.6 GB of it VRAM) even when nobody asks anything.
- Times are until the answer audio is ready (the page then plays it).
- The two wrong answers show the two main weaknesses: STT heard *Quyosh* as *bu yosh* and the model answered the
  misheard question; and for "cho‘l kemasi" gemma answered correctly (*camel*) but MADLAD turned the English answer
  into an unrelated Uzbek sentence.

### Estimate per stage (before the end-to-end run)

Sum of the stage medians above for a short spoken Uzbek question:

| Path | STT | Chat (LLM + MADLAD out) | TTS | Spoken question → answer audio |
|---|---|---|---|---|
| Uzbek, female voice | ≈ 3 s | ≈ 6.7 s | ≈ 1–2 s | **≈ 11–12 s** |
| Uzbek, male voice | ≈ 3 s | ≈ 6.7 s | ≈ 15–30 s | ≈ 25–40 s |
| Russian, Kokoro `masha` | ≈ 3.5–5 s | ≈ 6.3 s | ≈ 2 s | ≈ 12–13 s |
| English, Kokoro `af_heart` | ≈ 3.5–5 s | ≈ 3.2 s | ≈ 1 s | ≈ 8–9 s |

On the Ubuntu server (i7-13700, 64 GB, RTX 4060) *estimate*: Uzbek with the female voice ≈ 3–5 s; the male voice
≈ 1–3 s per sentence on the RTX 4060 (tensor cores; not measured).

## Memory on the 8 GB reference PC

| Process | Commit / VRAM |
|---|---|
| `server.py` (MADLAD) | ≈ 9.9 GB commit |
| Ollama `gemma3:4b` | 3.25 GB (≈ 54 % CPU / 46 % GPU, 1.6 GB VRAM) |
| STT (`small` + NavAI) | 2.6–2.7 GB, 5.05 GB with both models |
| Uzbek female TTS | 0.4–0.7 GB |
| Uzbek male TTS | 0.68–1.94 GB VRAM + its CUDA runtime |
| Kokoro EN + RU | ≈ 5.5 GB |

The full stack exceeds the 8 GB PC's comfortable budget (free commit fell to ≈ 1.2 GB with MADLAD + a 4B model; the
system-managed pagefile grew to ≈ 23.5 GB). The owner accepted this risk. The Ubuntu server is the long-term target.

## Start the full setup

```powershell
Set-Location C:\local-ai-translator
.\stt-tts-uz\.venv-tts\Scripts\python.exe .\tts_onnx_server.py              # 8766 Uzbek female voice
.\.venv\Scripts\python.exe .\server.py                                       # 8765 chat (gemma3:4b must be pulled)
.\.venv-stt\Scripts\python.exe .\stt_server.py                               # 8769 STT (NavAI for Uzbek)
.\.venv-kokoro\Scripts\python.exe .\kokoro_tts_server.py                     # 8768 Russian/English voices
.\Uzbek_TTS-test\.venv\Scripts\python.exe -X utf8 .\uz_male_tts_server.py    # 8770 optional Uzbek male voice (GPU)
```

Then open <http://localhost:8765>. Details: [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md).

## What was tried and not chosen

| Option | Result | Why not |
|---|---|---|
| Faster-Whisper `small` for Uzbek | WER 1.24 on real speech | NavAI is 6× more accurate |
| NavAI for Russian/English | WER ≈ 1.0 | cannot transcribe them |
| qwen3:1.7b (previous chat model) | Uzbek STT-text 10/25 | weakest on misrecognised Uzbek |
| qwen3:4b-instruct | best on English speed and commands, Uzbek STT-text 14/25 (madlad) | weaker Uzbek understanding; hybrid only 6/25 |
| Qwen3-4B Thinking | 77 s median per answer, 3/17 empty | far too slow for voice |
| dual input (original + translation) | gemma 16/25 STT text; qwen3:1.7b worse than before | below hybrid |
| direct (model answers in Uzbek itself) | gemma 13/25 STT text | the 4B models write Uzbek worse than MADLAD translates |
| Browser voices | — | removed on the owner's request: only local voices |
| Shorter answers (prompt: no restating, no follow-up questions) | Uzbek median 6.7 → 4.7 s, but correct 39/50 → **28/50**; MADLAD lost 11 answers instead of 6 | MADLAD mistranslates very short English answers (*Spring.* → *Bas, chiq!*) |
| Male voice on the CPU | 28.3 s median | slower than the GTX 1650 |

## Known limits of this setup

- **MADLAD output translation can replace a correct answer with an unrelated sentence** (seen in the end-to-end
  run and in 6 of 42 correct answers in the comparison). It is the largest remaining quality problem.
- **STT mistakes are not caught**: a misheard word changes the question and the model answers the wrong question;
  the page shows the transcript, but nothing asks for confirmation.
- The model sometimes explains or restates the question ("That translates to …") instead of answering.
- On the 8 GB PC the full stack does not fit: with chat + STT + both Uzbek voices running, only ≈ 1.2 GB commit is
  left, so Kokoro (Russian/English voices) cannot be started at the same time.
- No conversation history: every question is answered on its own.
- `server.py` listens on all interfaces without authentication.
- Robot commands are not reliable from free speech (STT and LLM both); a fixed command grammar or confirmation step is needed.
- Test sets are small (25 + 25 Uzbek, 20 Russian, 20 English); differences of 1–3 answers are within noise.
- STT tests use FLEURS (female, read speech) and synthetic audio; no male or spontaneous Uzbek speech yet.
- MADLAD can turn short correct English answers into wrong Uzbek (e.g. *Spring.* → *Bas, chiq!*).
- The male voice clones an unknown speaker's recording; licence of the Uzbek_TTS checkpoint is not verified ([LICENSING.md](LICENSING.md)).
- Piper's English male voice `ryan` was trained on a CC BY-NC-SA 4.0 dataset (non-commercial); Kokoro `am_michael` is Apache-2.0.

## Where the data is

| What | Path |
|---|---|
| STT benchmark (120 FLEURS + synthetic) | `stt-eval/runs/`, `stt-eval/results/`, [STT_EVALUATION.md](STT_EVALUATION.md) |
| STT integration tests (before/after, memory, swap, fallback) | `stt-eval/integration/` |
| Dual-input experiment | `stt-eval/dual_input/experiment.json` |
| LLM × pipeline comparison | `stt-eval/llm_compare/` (`RESULTS.md`, `summary.json`, `runs/`, `commands/`) |
| Uzbek TTS speed (female / male GPU / male CPU) | `stt-eval/tts_uz/*.json` (`stt-eval/scripts/tts_uz_benchmark.py`) |
| Chat speed-up test (keep_alive/preload; shorter-answer prompt) | `stt-eval/chat_eval/` (`stt-eval/scripts/chat_eval.py`) |
| End-to-end voice test (audio → STT → chat → TTS) | `stt-eval/e2e/results.json`, `results_male.json` (`stt-eval/scripts/e2e_voice_test.py`) |
| Russian/English TTS speed, female vs male (Kokoro, Piper) | `stt-eval/tts_ruen/results.json` (`stt-eval/scripts/tts_ruen_benchmark.py`) |
