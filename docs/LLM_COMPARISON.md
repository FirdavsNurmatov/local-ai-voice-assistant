# Chat model and pipeline comparison (2026-10-17)

**Decision:** the chat uses **`gemma3:4b`** with the **hybrid** pipeline — the model reads the user's Uzbek or
Russian text itself, answers in English, and MADLAD translates the answer into the user's language. English
goes to the model and back unchanged. `server.py` contains only this pipeline (no switches); the evaluation
version with request flags is in git history (commit "Integrate NavAI Uzbek STT and add the LLM pipeline comparison").

Why: the problem to solve was MADLAD mistranslating misspelled or misrecognised Uzbek *before* the model saw it.
Hybrid removes that step. With gemma3:4b it gave the most correct Uzbek answers, and by the widest margin on
speech-recognition text (19/25 vs 10/25 for the previous qwen3:1.7b + MADLAD design).

Raw data, scripts and full tables: [`stt-eval/llm_compare/`](../stt-eval/llm_compare/STATUS.md)
([RESULTS.md](../stt-eval/llm_compare/RESULTS.md)).

## What was compared

| Pipeline | Input to the model | Model answers in | Output |
|---|---|---|---|
| madlad (previous design) | MADLAD uz/ru → en translation | English | MADLAD en → uz/ru |
| dual | original text **and** the MADLAD translation | English | MADLAD en → uz/ru |
| **hybrid (chosen)** | original text | English | MADLAD en → uz/ru |
| direct | original text | the user's language | no MADLAD |

Models (Ollama): `qwen3:1.7b` (previous), `qwen3:4b-instruct` (Qwen3-4B-Instruct-2507), `gemma3:4b`
(Gemma 3 4B, Q4_K_M), and `qwen3:4b` (Qwen3-4B-**Thinking**-2507, thinking on). Note: the `qwen3:4b` tag is the
Thinking model and ignores `think:false`; its first results were discarded (`runs/_invalid/`).

Test sets:
- **Uzbek:** 25 general-knowledge questions, each as clean text and as the text NavAI STT produced from TTS audio of
  the question (real recognition errors, e.g. `bu yosh qaysi tomondan chiqadi` for *Quyosh…*).
- **Russian:** 20 questions; **English:** 20 questions (speed baseline).
- **Robot commands:** 12 Uzbek commands (clean) + 11 STT transcripts; the model must output one action label.

Scoring: an answer is correct when it contains an expected keyword (spelling variants included, e.g.
`yetti`/`etti`, `toshkent`/`tashkent`). Latency is the end-to-end text→text time of one request, first request
of a run excluded.

## Results

### Uzbek questions (50 = 25 clean + 25 STT text)

| Model | Pipeline | Clean | STT text | Median s | p95 s |
|---|---|---|---|---|---|
| **gemma3:4b** | **hybrid** | **20/25** | **19/25** | 6.7 | 12.4 |
| gemma3:4b | dual | 20/25 | 16/25 | 4.3 | 7.6 |
| gemma3:4b | madlad | 19/25 | 16/25 | 8.2 | 14.1 |
| qwen3:4b-instruct | madlad | 19/25 | 14/25 | 7.6 | 16.5 |
| gemma3:4b | direct | 15/25 | 13/25 | 4.3 | 6.3 |
| qwen3:1.7b | madlad (previous) | 17/25 | 10/25 | 2.7 | 4.5 |
| qwen3:4b-instruct | direct | 12/25 | 11/25 | 2.3 | 6.9 |
| qwen3:4b-instruct | dual | 10/25 | 10/25 | 3.2 | 7.7 |
| qwen3:1.7b | dual | 7/25 | 10/25 | 2.7 | 4.0 |
| qwen3:1.7b | direct | 9/25 | 7/25 | 0.3 | 0.5 |
| qwen3:1.7b | hybrid | 10/25 | 6/25 | 1.4 | 3.7 |
| qwen3:4b-instruct | hybrid | 8/25 | 6/25 | 5.6 | 12.2 |
| qwen3:4b Thinking | direct | 7/9 | 4/8 | **77** | 152 |

- Hybrid only works with a model that understands Uzbek: it is the best pipeline for gemma3:4b and the worst for
  both Qwen models.
- **MADLAD's output translation loses answers too.** For gemma3:4b hybrid the model's English answer was right in
  42/50 cases; 6 of those became wrong in Uzbek (e.g. *Spring.* → *Bas, chiq!*; a correct *60 minutes* became an
  unrelated religious sentence). Short or multi-sentence English answers are the risky ones.
- The Thinking model was stopped after 17 questions (owner's decision): 77 s median per answer, and 3 of 17
  answers were empty because reasoning used up the 2048-token budget. Not usable for a voice chat.

### Russian questions (20)

| Model | Pipeline | Correct | Median s |
|---|---|---|---|
| gemma3:4b | direct | 20/20 | 2.6 |
| qwen3:4b-instruct | direct | 19/20 | 1.2 |
| gemma3:4b | dual / **hybrid** / madlad | 19/20 each | 4.0 / **6.3** / 7.6 |
| qwen3:1.7b | madlad (previous) | 17/20 | 2.0 |
| qwen3:1.7b | dual | 3/20 | 2.4 |

For Russian, gemma3:4b direct was one question better and faster than hybrid. The owner chose one pipeline for all
languages rather than a per-language switch, so Russian also uses hybrid.

### English questions (20, no MADLAD)

| Model | Correct | Median s | Generation speed |
|---|---|---|---|
| qwen3:4b-instruct | 20/20 | 1.3 | 21 tok/s |
| gemma3:4b | 20/20 | 3.2 | 13 tok/s |
| qwen3:1.7b | 18/20 | 0.2 | 87 tok/s |

### Robot commands (action label; 12 clean + 11 STT)

| Model | Input | Clean | STT |
|---|---|---|---|
| qwen3:4b-instruct | original (hybrid/direct) | 12/12 | 5/11 |
| gemma3:4b | MADLAD translation | 11/12 | 5/11 |
| gemma3:4b | original (**chosen pipeline**) | 8/12 | 4/11 |
| qwen3:1.7b | MADLAD translation (previous) | 9/12 | 3/11 |

Commands are short and the STT transcripts of the synthetic command audio are poor (see `docs/STT.md`), so no
pipeline is reliable enough to drive a robot from free speech; a fixed command grammar is still needed.
The free-text "restate the command" check stored in `runs/*.json` was not usable (models echoed the Uzbek or asked
for the question) and is ignored.

## Cost of the change (reference PC, 8 GB RAM, GTX 1650)

| | qwen3:1.7b | gemma3:4b |
|---|---|---|
| Ollama model size loaded | 1.37 GB | 3.25 GB (≈ 54 % CPU / 46 % GPU on the GTX 1650) |
| Uzbek median latency (text → text) | 2.7 s (madlad) | 6.7 s (hybrid) |
| English median latency | 0.2 s | 3.2 s |

With MADLAD (≈ 9.9 GB commit) and a 4B model loaded, free commit fell to ~1.2 GB, so the 4B timings include
paging; on the Ubuntu server (64 GB, RTX 4060) both the paging and most of the generation time should disappear.

## Limits of this evaluation

- Small sets (25 + 25 Uzbek, 20 Russian, 20 English, 23 commands); a difference of 1–3 answers is within noise.
- The STT versions come from TTS audio (one synthetic voice), not from real users.
- Keyword scoring checks the fact, not fluency or grammar of the Uzbek answer.
- Answers are sampled at temperature 0.4; one run per configuration.

## Reproduce

See [`stt-eval/llm_compare/STATUS.md`](../stt-eval/llm_compare/STATUS.md). The runs need the evaluation version
of `server.py` (request flags `dual_input` / `direct_input`, `CHAT_MODEL`) from the commit named above.
