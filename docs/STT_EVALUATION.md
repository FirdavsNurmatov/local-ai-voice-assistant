# Uzbek STT evaluation: Faster-Whisper `small` vs NavAI `whisper-small-uzbek`

- **Run:** 2026-10-14, reference PC (Windows 11, i7-9700K, 7.9 GB RAM, GTX 1650 4 GB)
- **Status:** all numbers below were measured in this evaluation (`VERIFIED` at that time) unless marked otherwise
- **Data:** per-clip results [`stt-eval/results/per_sample_results.csv`](../stt-eval/results/per_sample_results.csv), summary [`stt-eval/results/summary.csv`](../stt-eval/results/summary.csv), raw run files `stt-eval/runs/*.json`
- **Reproduce:** [STT_EVALUATION_REPRODUCE.md](STT_EVALUATION_REPRODUCE.md) · **Production service:** [STT.md](STT.md)
- **Production was not changed:** `stt_server.py`, `.venv-stt` and the production model are untouched; no service was running during the benchmark except Ollama.

## 1. Verdict

| Question | Answer (evidence below) |
|---|---|
| Does NavAI improve recognition of **real human** Uzbek speech? | **Yes, decisively.** On 120 FLEURS test recordings the word error rate falls from **1.239** (production) to **0.255** with NavAI under identical neutral settings, and to **0.207** with the timestamp fix. NavAI is better on **120 of 120** clips. |
| Does it cause repetition / hallucination? | No. 0 repetitions in 704 NavAI transcriptions (all datasets and settings); the production setup produced 12 on 120 FLEURS clips (e.g. `2-2-2-2…`, `ṢĪm ṢĪm…`) and returned its own prompt text instead of a transcript 4 times (2 FLEURS, 2 synthetic). |
| Resource cost? | **Equal or lower**: model load 0.7–1.0 s vs 1.9 s, peak RSS 0.6 GB vs 1.1 GB, peak commit 2.9 GB vs 3.4 GB on CPU; median latency 3.1–3.3 s vs 5.9 s. |
| Can it replace the current model completely? | **No.** NavAI cannot transcribe Russian or English (WER ≈ 1.0, it answers in Uzbek-Latin transliteration) and its language detector labels everything as Uzbek. |
| Settings | NavAI must **not** use the production Uzbek workarounds (prompt, disabled thresholds): they double its error rate. It should decode **without timestamp tokens** (post-hoc finding, see §6.3). |
| **Recommendation** | **B — use NavAI for Uzbek only, keep the current model for Russian/English and for language detection.** Not implemented; plan in §9. One more validation on fresh audio (held-out FLEURS clips and real iPhone recordings) is required before switching. |

## 2. Systems compared

| | Production baseline | Candidate |
|---|---|---|
| Model | `Systran/faster-whisper-small` @ `536b0662` (OpenAI Whisper small, CTranslate2 fp16 weights) | `navai-uz/whisper-small-uzbek` @ `4b432caf` (Whisper small fine-tuned on 753 h of Uzbek; Apache-2.0) |
| Format used | CTranslate2, loaded with `compute_type=int8` | converted locally: `ct2-transformers-converter --quantization int8` → 248 MB `model.bin` |
| Runtime | faster-whisper 1.2.1, ctranslate2 4.8.3, PyAV 16.1.0 — identical for both (`.venv-stt-eval`, same versions as production `.venv-stt`) | same |
| Threads / device | CPU, 4 threads (as production); GPU runs: GTX 1650, `int8_float16` | same |

Conversion notes: the NavAI repository has no `tokenizer.json`; it was generated with `transformers.AutoTokenizer(...).save_pretrained()`.
The converted model differs from the production model's config only in `suppress_ids` (NavAI's `generation_config` has an empty `suppress_tokens` list).
Checksums of every model and dataset file: [`stt-eval/manifest_sha256.csv`](../stt-eval/manifest_sha256.csv).

### 2.1 Conversion check against the original implementation

20 FLEURS clips (every 6th of the sample) decoded by the **original weights in Transformers/PyTorch fp32**
(the model card's own usage: greedy, shipped `generation_config` with `no_repeat_ngram_size=4`, no VAD)
and by the converted CT2 int8 model with matching settings (greedy, no VAD, `no_repeat_ngram_size=4`):

| Implementation | micro-WER | CER | Exact | First word correct | Median latency | Peak RSS |
|---|---|---|---|---|---|---|
| Transformers / PyTorch fp32 (reference) | 0.236 | 0.082 | 5/20 | 15/20 | 14.8 s | 2.05 GB |
| CT2 int8, faster-whisper default (timestamps on) | 0.272 | 0.101 | 4/20 | **8/20** | 3.0 s | 0.55 GB |
| CT2 int8, `without_timestamps=True` | 0.256 | 0.088 | 5/20 | **15/20** | 2.7 s | 0.55 GB |

Finding: the large first-word loss of the converted model is **not** a conversion error. faster-whisper
asks the model for timestamp tokens by default, while NavAI's `generation_config` sets
`return_timestamps: false`; with timestamps disabled the converted model matches the reference's
first-word accuracy. The remaining gap (0.256 vs 0.236 on 20 clips, about 4 words) is attributable to
int8 quantisation and small decoding differences; it was not investigated further.

## 3. Datasets

Human and synthetic speech are **never** pooled.

| Dataset | Type | Clips | Selection | Use |
|---|---|---|---|---|
| **A. FLEURS `uz_uz` test** | real human read speech (Google FLEURS, CC-BY-4.0) | **120** (24.4 min) | one random speaker per sentence; sentences split into duration terciles; 40 random per tercile; seed `20261014` (`prepare_fleurs.py`) | primary comparison |
| A-parity | subset of A | 20 | every 6th clip of A | conversion check §2.1 |
| **B. Synthetic Uzbek** | project's Uzbek VITS TTS | 12 | hand-written: 6 natural requests, 1 one-word, 4 repetition-prone (counting, "ha, ha", "yo'q, yo'q, yo'q", stutter), 1 long | diagnostics only |
| **C. RU/EN regression** | Kokoro TTS (`masha`, `af_heart`) | 4 + 4 | required sentence, short, long, required + pink noise | regression only |
| D. iPhone recordings | — | **0** | none were available | **not evaluated** |

FLEURS checks (all passed): archive SHA256 `1c9e47b3…057a` equals the Hugging Face LFS id; 862
recordings, 345 sentences; every selected file is 16 kHz, mono, 32-bit float WAV with exactly the
number of samples listed in `test.tsv`. Short 4.6–9.6 s, medium 9.7–13.2 s, long 13.3–26.7 s.
20 of 120 references contain digits.

**Known limitation:** every recording in the FLEURS Uzbek test split is labelled `FEMALE` (862/862) —
male voices are not represented. FLEURS is read encyclopedic speech with many proper names; it is
harder than short spoken commands. NavAI states that FLEURS **test** was excluded from its training
(its `train` split was used); this could not be verified independently. No other legally usable
real Uzbek recordings were added.

## 4. Configurations

All runs: same audio files, decoded by PyAV to 16 kHz; `task="transcribe"`; `condition_on_previous_text=False`;
4 CPU threads; one configuration per process, run one after another (never two models loaded at once).

| Config | Model | Decoding | Purpose |
|---|---|---|---|
| `small_prod` | production | **exact production code** `stt_server.transcribe()`: `beam_size=5`, Silero VAD, Uzbek `initial_prompt`, `no_speech_threshold=None`, `log_prob_threshold=None`, `temperature=(0.0, 0.4)` | baseline as deployed (with Uzbek selected) |
| `navai_prod` | NavAI | same production code and options | identical-settings comparison |
| `small_neutral` | production | `beam_size=5`, VAD, **no prompt**, default thresholds/temperatures, `no_repeat_ngram_size=4` | neutral comparison |
| `navai_neutral` | NavAI | same neutral options | neutral comparison |
| `*_nots` | both | neutral + `without_timestamps=True` | **post-hoc** (chosen after seeing errors; reported separately) |
| `*_auto` | both | production pipeline with automatic language detection | diagnostic |
| `hf_navai`, `navai_card` | NavAI | greedy, no VAD (model-card usage) | conversion check |

`no_repeat_ngram_size`, `repetition_penalty` and `hallucination_silence_threshold` are accepted by
the installed faster-whisper 1.2.1 (checked with `inspect.signature`); only `no_repeat_ngram_size=4`
(the value NavAI was trained and scored with) was used. No parameter was tuned on the test set except
the post-hoc `without_timestamps`, whose reason is documented in §2.1.

**Reproducibility note:** the production Uzbek settings allow a temperature-0.4 retry, which samples
randomly; `small_prod` results can differ slightly between runs (seen on the synthetic set: forced-uz
WER 0.989 vs the auto run's 1.782 on identical audio and language).

## 5. Metrics and normalisation

One function (`stt-eval/scripts/common.py: normalize`) is applied to every reference and hypothesis:
Unicode NFKC → lower case → every apostrophe variant (`' ` ´ ‘ ’ ʻ ʼ ʽ ′ ‛`) folded to `ʻ` → hyphens
and dashes to spaces → all other punctuation removed → whitespace collapsed.
**Not** normalised (they stay errors): digits vs number words, Cyrillic vs Latin script, spelling.
Raw texts are kept unchanged in the CSV next to the normalised copies.

| Metric | Definition |
|---|---|
| micro-WER | (substitutions + deletions + insertions) summed over all clips / reference words summed over all clips |
| macro-WER | mean of per-clip WER (each clip weighs the same, short clips count more than in micro-WER) |
| CER | character edit distance between normalised texts (words joined by one space), summed / reference characters |
| Exact match | normalised hypothesis identical to normalised reference |
| Repetition | a 1–4-character unit repeated ≥ 6 times, an n-gram (n ≤ 3) repeated 3× in a row that the reference does not contain, or output > 1.5 × reference length + 3 words |
| Wrong language | returned language ≠ dataset language (auto mode only) |
| Latency | wall-clock per clip: decoding the file + (detection) + transcription; median and p95 (linear interpolation) |
| RTF | total latency / total audio duration |
| Memory | peak RSS during inference (50 ms sampler); peak commit = Windows peak pagefile usage of the process (load + inference) |
| GPU | `nvidia-smi` sampled every 0.25 s: peak used minus used before loading; max utilisation |

WER above 1.0 means the output had more wrong words than the reference had words (insertions).

## 6. Results

### 6.1 Real human speech (FLEURS, 120 clips, language forced to Uzbek, CPU)

| Config | micro-WER | macro-WER | CER | Exact | Repetition | Median / p95 latency | RTF | Load | Peak RSS | Peak commit |
|---|---|---|---|---|---|---|---|---|---|---|
| `small_prod` (production) | 1.239 | 1.228 | 0.435 | 0/120 | 12 | 5.90 / 22.05 s | 0.651 | 1.95 s | 1074 MB | 3359 MB |
| `navai_prod` | 0.496 | 0.495 | 0.351 | 2/120 | 0 | 5.03 / 7.30 s | 0.425 | 2.78 s | 1025 MB | 3309 MB |
| `small_neutral` | 1.103 | 1.097 | 0.398 | 0/120 | 3 | 3.69 / 21.58 s | 0.567 | 1.91 s | 1054 MB | 3339 MB |
| **`navai_neutral`** | **0.255** | **0.241** | **0.101** | **12/120** | **0** | **3.27 / 5.04 s** | **0.283** | 1.01 s | 613 MB | 2896 MB |

Post-hoc (§2.1), reported separately because it was chosen after inspecting test-set errors:

| Config | micro-WER | macro-WER | CER | Exact | Repetition | Median / p95 | Peak RSS | Peak commit |
|---|---|---|---|---|---|---|---|---|
| `small_neutral_nots` | 1.089 | 1.082 | 0.381 | 0/120 | 1 | 3.36 / 21.14 s | 1076 MB | 3360 MB |
| `navai_neutral_nots` | **0.207** | **0.193** | **0.067** | **21/120** | 0 | 3.13 / 4.53 s | 609 MB | 2896 MB |

Breakdown (micro-WER):

| Config | short (4.6–9.6 s) | medium | long (13–27 s) | refs with digits (20) | first word correct | clips losing ≥ 30 % of words |
|---|---|---|---|---|---|---|
| `small_prod` | 1.298 | 1.356 | 1.124 | 1.204 | 13/120 | 3 |
| `navai_prod` | 0.427 | 0.468 | 0.553 | 0.569 | 6/120 | **35** |
| `navai_neutral` | 0.287 | 0.257 | 0.235 | 0.366 | 46/120 | 1 |
| `navai_neutral_nots` | 0.238 | 0.209 | 0.190 | 0.338 | 99/120 | 0 |

Per clip, `navai_neutral` and `navai_neutral_nots` each have a lower WER than `small_prod` on all 120 clips.

For reference, NavAI's model card reports 16.96 % WER on the full FLEURS test set with its own
normaliser (which spells out numbers and folds Cyrillic) and greedy decoding. 20.7 % here on a
120-clip sample with a stricter normaliser is consistent with that claim but does not verify it.

### 6.2 GPU (GTX 1650, `int8_float16`, FLEURS 120, neutral settings)

The GPU was confirmed in use (utilisation up to 90–93 %, VRAM rising during the run). CUDA libraries
came from pip wheels in the evaluation environment (`nvidia-cublas-cu12 12.9.2.10`, `nvidia-cudnn-cu12 9.27.0.42`).

| Config | micro-WER | CER | Median / p95 | RTF | VRAM (above idle) | GPU util. max | Peak RSS | Peak commit |
|---|---|---|---|---|---|---|---|---|
| `small_neutral` | 1.071 | 0.395 | 1.10 / 4.41 s | 0.133 | +716 MB | 90 % | 616 MB | 1910 MB |
| `navai_neutral` | 0.243 | 0.094 | **0.90 / 1.38 s** | **0.077** | **+474 MB** | 93 % | 602 MB | **1714 MB** |

GPU decoding is 3.6× faster for NavAI and needs ≈ 1.2 GB less commit than CPU; accuracy is the same
within noise (fp16 activations vs int8). Production does not use the GPU today.

### 6.3 Automatic language detection (diagnostic, FLEURS 120)

| Config | Returned language | Whisper's raw best guess on Uzbek speech | micro-WER |
|---|---|---|---|
| `small_prod` auto | `uz` 120/120 | `hy` 37, `fa` 30, `az` 25, `ka` 10, `ps` 5, `kk` 3 — **never `uz`** | 1.289 |
| `navai_prod` auto | `uz` 120/120 | `uz` 120 | 0.485 |

The production rule ("Russian or English if their probability ≥ 0.5, otherwise Uzbek") is what makes
auto mode work for Uzbek: the production model never recognises Uzbek by itself. NavAI's detector
says `uz` for everything — including Russian and English speech (§6.5) — so it cannot be used for detection.

### 6.4 Synthetic Uzbek (12 TTS clips) — diagnostics only

| Config | micro-WER | CER | Repetition | Median / p95 |
|---|---|---|---|---|
| `small_prod` | 0.989 | 0.683 | 1 | 4.19 / 17.01 s |
| `small_neutral` | 1.632 | 0.918 | 1 | 2.33 / 10.08 s |
| `navai_neutral` | 0.379 | 0.209 | 0 | 2.17 / 2.73 s |
| `navai_neutral_nots` (post-hoc) | 0.299 | 0.133 | 0 | 2.12 / 2.72 s |
| `navai_prod` | 0.782 | 0.634 | 0 | 3.73 / 4.52 s |

The one-word clip "Rahmat." (0.6 s) produced no text with **any** model. The production setup
returned its own prompt for two clips ("…gapiryapman, menga yordam bering."). The synthetic voice is
a single TTS speaker; these numbers say nothing about real users.

### 6.5 Russian / English regression (Kokoro TTS clips, 4 + 4)

| Config | RU micro-WER | EN micro-WER | Language returned (auto) |
|---|---|---|---|
| `small_prod`, auto | 0.022 | 0.000 | correct 8/8 |
| `small_prod`, forced | 0.022 | 0.000 | — |
| `navai_prod`, auto | 1.022 | 0.983 | `uz` for 4/4 RU and 3/4 EN (1 EN clip: no text) |
| `navai_prod`, forced ru/en | 1.000 | 1.017 | — |

Example: Russian "Привет! Расскажи мне короткую интересную историю." → NavAI forced to Russian:
`privyet raskarjev nikorotku interesnu estoryo`; English "Hello! Please explain how artificial
intelligence works." → `ob ʻalloʻ pleiz eksplayin ham artefessional intellenjans rizq`. Fine-tuning
removed NavAI's Russian and English ability. These clips are synthetic; human RU/EN regression
(e.g. FLEURS `ru_ru`/`en_us` test) is **planned, not performed**.

### 6.6 Resources summary (CPU, per process, model + runtime)

| | Production `small` | NavAI |
|---|---|---|
| Model file | 484 MB (fp16, quantised at load) | 248 MB (int8) |
| Load time | 1.3–2.0 s | 0.7–1.0 s (2.8 s once, first run after a reboot) |
| Peak RSS during inference | 1.0–1.1 GB on FLEURS, 0.6 GB on short clips | 0.55–0.61 GB (1.0 GB through the production pipeline) |
| Peak commit (Windows) | 2.9–3.4 GB | 2.8–2.9 GB (3.3 GB through the production pipeline) |
| GPU (GTX 1650) | +716 MB VRAM, 1.9 GB commit | +474 MB VRAM, 1.7 GB commit |

Most of the commit comes from the CTranslate2 runtime itself (see [STT.md](STT.md#memory)), so a
process that holds **both** models is expected to need noticeably less than the sum (≈ 2.9 + 2.9 GB);
this was **not measured**.

## 7. Error analysis

Error mix on FLEURS (word operations against 2 240 normalised reference words, CPU, forced `uz`):

| Config | Substitutions | Deletions | Insertions | Dominant problem |
|---|---|---|---|---|
| `small_prod` | 2 042 | 44 | 690 | almost every word garbled phonetically (Turkic/Arabic-style spellings), repetition loops, prompt leakage |
| `small_neutral` | 1 983 | 77 | 410 | same without prompt leakage |
| `navai_prod` | 446 | **604** | 61 | the production prompt makes NavAI start mid-sentence and stop early |
| `navai_neutral` | 399 | 116 | 55 | missing/garbled **first word** (timestamp mode), proper names |
| `navai_neutral_nots` | 385 | 38 | 41 | proper names, suffixes, numerals, acronyms |

Representative examples (all real outputs from this run; "Robot impact" = whether a robot command with this error would be misunderstood):

| # | Reference | Production (`small_prod`) | NavAI (`navai_neutral`) | NavAI post-hoc (`_nots`) | Category | Robot impact |
|---|---|---|---|---|---|---|
| 1 | Arxipelag va ko'llarda sizga yaxta shart bo'lmaydi. | Archipilak wakullardas izgay axta shard bon majde. | archipelag **vakillarda** sizga yaxta shart boʻlmaydi | arxipelag va **gollarda** sizga yaxta shart boʻlmaydi | prod: substitution (phonetic); NavAI: substitution (word boundary) | prod: unusable; NavAI: meaning mostly kept |
| 2 | Metroda odatiy e'lonlar faqat katalan tilida aytiladi, … ispan, ingliz, fransuz, arab va yapon tillarida e'lon qilinadi. | `Metro 2-2-2-2-2-2-2-2-…` | … katalon tili … koʻplab **tushuntirish va minglisi bilan asos avgʻarb qayerda** eʻlon qilinadi | similar | prod: **repetition hallucination**; NavAI: proper names / uncommon words | prod: command lost; NavAI: list of languages lost |
| 3 | Biz USOCning sportchilarimiz va klublarimiz … fikriga qoʻshilamiz. | `ṢĪm ṢĪm ṢĪm ṢĪm …` | *(first words missing)* sportchilar va klublarimiz … | biz **uscʻning** sportchilarimiz … | prod: repetition; NavAI: deletion at start / acronym | prod: lost; NavAI: subject lost in `navai_neutral`, kept in `_nots` |
| 4 | "Bu vidolashuv bo'lmaydi. Bu bitta bobning yopilishi hamda yangisining ochilishidir". | **Bugun o'zbek tilida gapiryapman, menga yordam bering.** | … hamda **yangi zilning** ochilishidir | same | prod: **prompt leakage** (insertion of the initial prompt, nothing transcribed); NavAI: split word | prod: wrong command invented; NavAI: minor |
| 5 | Echkilar ilk bor 10 ming yilcha avval Eronning Zagros tog'larida … | Echkiler ilik bar onmin yelika ahval, iranin zakrystahlar … | **lar** ilk bor **oʻn** ming … **zagreb** … | **echkilar** ilk bor oʻn ming … zagreb … | NavAI: first-word deletion (fixed by `_nots`), numeral form, proper name | NavAI: "10" vs "o'n" harmless; subject loss would matter |
| 6 | Moldova poytaxti Kishinyov. … | Maldava poi tahta kxinyof, … | **a** poytaxti kishinyov … | **moldova** poytaxti kishinyov … | NavAI: first-word deletion (timestamp mode) | the key noun was lost; fixed post-hoc |
| 7 | Olti nafar garovga olinganlar, … | **6** nafar garovga alingenlar, … | **i** olti nafar … | olti nafar … | prod: number form + garble; NavAI: spurious leading fragment | minor |
| 8 | Yakshanba oqshomida AQSH prezidenti … bayonotida AQSH qo'shinlari … | Yakishan ba okshao me da aksh presidenta Donald Trump … | yakshanba **oqshomidan** … **bayonotidan aqish** qoʻshinlari … | same | NavAI: suffix substitution (-ida → -idan), acronym | meaning kept |
| 9 | AQSH Gimnastika qo'mitasi Qo'shma Shtatlar Olimpiya Qo'mitasining … | Aksh gibnastika kumita asa. Koshmashdatlar … | … **qo�ra shtatlar** olimpiya **qo�** izning … **qoʙ** quvvatlaydi … | same | NavAI: **broken characters** (U+FFFD / wrong Cyrillic byte) — byte-level token decoding; also seen once in production outputs | words corrupted |
| 10 | Biroq bu faqatgina tajribalar emas … (26.7 s) | Burak bu fakat kina tajiribalar imaz. … | **ir** boʻlib ham xizmat qiluvchi … *(21 of 33 words missing)* | biroq bu faqatgina tajribalar emas … (WER 0.09) | NavAI: large deletion — **segmentation** of the first window in timestamp mode | first half of the request lost; fixed post-hoc |
| 11 | O'tgan hafta METI Apple kompaniyasi "jiddiy emas" … 34 ta qo'shimcha holat … | Utken hafta mieti apel kampanyat jiddi, … | *(first words missing)* apple kompaniyasi … **bort oʻtdi toʻrtta** … | oʻtgan hafta **media** apple … **oʻttiz toʻrt** … | NavAI: acronym, numerals as words | "34" kept as words in `_nots` |
| 12 | Salom, menga bugungi kun uchun qisqa reja tuzib ber. *(synthetic)* | **Menge bugun gapiryapman, menga yordam bering.** | salom menga bugungi kun uchun qisqa **yarasha** tuzib ber | same | prod: prompt leakage; NavAI: one substitution | prod: wrong request; NavAI: "reja" (plan) lost — would affect a command |
| 13 | Привет! Расскажи мне короткую интересную историю. *(synthetic RU)* | Привет. Расскажи мне короткую интересную историю. | `privyet raskarjev nikorotku interesnu estoryo` (forced `ru`) | — | NavAI: **wrong language / script** | NavAI unusable for Russian |

Category counts (FLEURS, from the per-clip CSV): production repetition 12/120, prompt text returned
instead of speech 2/120 (FLEURS) and 2/12 (synthetic); `navai_neutral` first word wrong 74/120, `navai_neutral_nots` first word wrong 21/120;
U+FFFD characters in 1 NavAI and 2 production FLEURS outputs (CPU); Cyrillic output for Latin references: 0.

## 8. Does the improvement justify the cost?

Yes. On real human Uzbek speech NavAI reduces errors by about **80 %** (WER 1.24 → 0.21–0.26), never
produced repetition, is faster, and needs the same or less memory than the current model. On the
GPU it would answer in under a second for typical sentences. The cost is that it **adds** a model
(Russian/English still need the current one), and its accuracy on proper names, acronyms and very
short utterances is still imperfect (WER ≈ 0.2 on read encyclopedic speech; "Rahmat." not recognised).

## 9. Recommendation and proposed production change (not implemented)

**Recommendation B:** adopt NavAI for Uzbek only; keep the current model for Russian, English and
language detection.

Routing inside `stt_server.py` (proposal):

| Request | Detection | Transcription model | Decoding |
|---|---|---|---|
| `?language=uz` | none | **NavAI** | `beam_size=5`, VAD on, `without_timestamps=True`, `no_repeat_ngram_size=4`, **no prompt**, default thresholds/temperatures |
| `?language=ru` / `en` | none | current `small` | unchanged production settings |
| auto (default) | current `small` `detect_language` + existing rule (ru/en if p ≥ 0.5, else uz) | NavAI if the rule says `uz`, otherwise `small` | as above |

Fallback: if NavAI fails to load, log it in `/api/health` (`models.uz.error`) and use the current
model for Uzbek, so behaviour degrades to today's instead of failing.

Steps:

1. **Validate first** on data not used in this evaluation: 100 other FLEURS `test` recordings (or the `validation` split) and at least 10 real iPhone recordings per language through the HTTPS tunnel. Accept if NavAI `_nots` WER on that set is within ±0.05 of 0.207 and no repetition appears.
2. Run human-speech RU/EN regression (FLEURS `ru_ru`, `en_us`, ≥ 50 clips each) for the unchanged `small` path.
3. Copy `stt-models/navai-whisper-small-uzbek-ct2-int8/` (no new Python packages are needed — same faster-whisper/ctranslate2/PyAV).
4. Change `stt_server.py` (backup first): load both models in the background; route as above; remove the Uzbek-specific prompt/threshold overrides for the NavAI path; report both models in `/api/health`.
5. Measure the two-model process: load time, RSS, commit (estimated ≈ 4–5 GB commit on CPU, not measured). On the 8 GB reference PC this makes chat + STT tighter; consider moving STT to the GPU (≈ 1.2 GB VRAM for both models, measured separately) or the Ubuntu server.
6. Expose the language choice in the page (the backend already supports `?language=`), so a user who knows they speak Uzbek skips detection (−1.7 s) and its failure modes.
7. Re-run the smoke tests in [STT.md](STT.md) and this evaluation's synthetic/regression sets; update [API_REFERENCE.md](API_REFERENCE.md).

Alternatives considered: **A** (keep `small`, tune settings) — rejected: best `small` setting still
WER 1.09. **C** (NavAI only when Uzbek is explicitly selected) — workable but leaves auto mode at
WER 1.24 for Uzbek. **D** (reject) — not supported by the data.

## 10. Limitations

- Human test data: one corpus, read speech, **female speakers only**, 120 clips; no male voices, no spontaneous speech, no noise, no iPhone recordings.
- RU/EN regression used 8 synthetic clips only.
- `without_timestamps=True` was chosen after looking at test-set errors; its benefit must be confirmed on fresh data (step 1 above).
- Numbers are not normalised (digits vs words count as errors for both models).
- `small_prod` is not fully deterministic (temperature 0.4 retry).
- The first production run was lost in an unexpected reboot (Kernel-Power 41, no bugcheck) and re-run from scratch; one diagnostic run (`navai_prod` auto, FLEURS) was resumed after 8 clips, so its load/memory figures cover only the resumed process.
- Latency was measured on the reference PC with only Ollama running (no model loaded in it); CPU runs used 4 threads.
- The NavAI training-data claims (FLEURS test excluded) are the model author's statement.

## 11. Files

Created for this evaluation (nothing in production was modified):

- `stt-eval/scripts/` — `common.py`, `prepare_fleurs.py`, `make_datasets.py`, `run_config.py`, `run_all.ps1`, `score.py`, `manifest.py`
- `stt-eval/datasets/*.csv` — exact clip lists with raw references and per-clip SHA256
- `stt-eval/runs/*.json` — raw outputs and options of every run
- `stt-eval/results/per_sample_results.csv`, `stt-eval/results/summary.csv`
- `stt-eval/manifest_sha256.csv`, `stt-eval/requirements-eval.txt`
- `docs/STT_EVALUATION.md`, `docs/STT_EVALUATION_REPRODUCE.md`
- Not in git (large / downloadable): `.venv-stt-eval/`, `stt-models/navai-*`, `stt-eval/fleurs/` (archive and extracted audio), synthetic WAVs.

FLEURS transcripts in the CSV files are © Google, CC-BY-4.0 (Conneau et al., 2022, arXiv:2205.12446).
