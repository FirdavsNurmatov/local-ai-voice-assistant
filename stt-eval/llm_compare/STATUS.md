# LLM pipeline comparison — finished 2026-10-17

Results: [RESULTS.md](RESULTS.md) (tables) and `summary.json`; write-up and decision: [docs/LLM_COMPARISON.md](../../docs/LLM_COMPARISON.md).
All runs were made on the 8 GB reference PC (i7-9700K, GTX 1650 4 GB). MADLAD runs on the CPU; Ollama splits each
model between CPU and GPU by itself (gemma3:4b: 54 % / 46 % CPU/GPU, checked after the runs). With a 4B model and
MADLAD loaded, free commit dropped to ~1.2 GB, so the 4B latencies include paging.

## Contents
- `questions_uz.json` (25 questions, `stt_text` = the same question after TTS → NavAI STT, `answer_keywords`,
  `answer_keywords_en` for the model's English answer), `questions_ru.json`, `questions_en.json` (20 each).
- `runs/<model>_<pipeline>[_ru|_en].json` — one file per model × pipeline × language (`llm_compare.py`).
  Model short names: `qwen1.7b` = qwen3:1.7b, `qwen4bi` = qwen3:4b-instruct (Qwen3-4B-Instruct-2507),
  `gemma4b` = gemma3:4b, `qwen4bthink` = qwen3:4b (Qwen3-4B-Thinking-2507, thinking on; stopped after 17 Uzbek
  questions — 77 s median per answer). `qwen1.7b_madlad_dual_v1` = first dual prompt (model repeated the question).
- `runs/_invalid/` — first 4B runs with the `qwen3:4b` tag, which is the Thinking model and ignores `think:false`.
- `commands/<model>_<mode>.json` — robot command → action label (`command_compare.py`). The free-text
  "restate the command" check stored in `runs/*.json` (`restated`, `understood`) is **not used**: with the
  original Uzbek text the models echoed it or asked for the question.
- `audio/` (not in git) — TTS audio of the Uzbek questions used to make `stt_text`.

## Reproduce
The runs used `server.py` as of the commit that added this folder (request flags `dual_input` /
`direct_input`, `CHAT_MODEL`). The current `server.py` keeps only the winning pipeline.
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File stt-eval\scripts\llm_compare_all.ps1                   # uz + ru (+ thinking)
powershell -NoProfile -ExecutionPolicy Bypass -File stt-eval\scripts\llm_compare_all.ps1 -Languages en -NoThinking
powershell -NoProfile -ExecutionPolicy Bypass -File stt-eval\scripts\command_compare_all.ps1
.\.venv-stt-eval\Scripts\python.exe stt-eval\scripts\llm_compare_report.py
```
