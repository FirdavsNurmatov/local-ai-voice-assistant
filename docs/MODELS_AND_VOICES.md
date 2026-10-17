# Models and voices

- **Last verified:** 2026-10-13
- **Status:** file names, sizes and SHA256 `VERIFIED`; upstream provenance as marked per row
- **Related:** [LICENSING.md](LICENSING.md), [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md), [MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md)

None of these files belong in version control. They must be obtained separately (≈ 4.3 GB active models, plus RUAccent data inside the Kokoro venv).

## Voice selection per language

| Language | Voice | Engine / port | Loaded when | Status |
|---|---|---|---|---|
| Uzbek (female, default) | single-speaker fine-tuned VITS | ONNX, 8766 | service start | working (tested 2026-10-13); owner-approved sample `stt-tts-uz\outputs\finetuned_test.wav` (same model and settings as the service) |
| Uzbek (male, optional) | voice cloned from `test_erkak.wav` | Uzbek_TTS (F5-style), 8770, CUDA | service start | working (tested 2026-10-17); owner-approved sample `Uzbek_TTS-test\test_uzbek_tts.wav` |
| English | `af_heart` | Kokoro-82M, 8768 | Kokoro start, if ≥ 2200 MB commit free | working (tested 2026-10-13) |
| Russian | `masha` | Kokoro-RU, 8768 | Kokoro start, if ≥ 4000 MB commit free **after** English loaded | worked when loaded; normally not loaded on the reference machine |
| Russian (fallback) | `irina` | Piper, 8767 | per request | working (tested 2026-10-13) |
| English (fallback) | `lessac` | Piper, 8767 | per request | working (tested 2026-10-13) |

**Never assume `masha` is available.** Check `ready.ru` in `GET :8768/api/health`.

## Chat model — Ollama

| Item | Value | Status |
|---|---|---|
| Model tag used | `gemma3:4b` (`CHAT_MODEL` in `server.py`; until 2026-10-17 `qwen3:1.7b`, see [LLM_COMPARISON.md](LLM_COMPARISON.md)) | `VERIFIED` in code and present in Ollama |
| Size reported by Ollama | 1.27 GB on disk, 1.36 GB loaded | `VERIFIED` |
| Other tags installed, unused by code | `qwen3:4b`, `qwen3-uz:latest`, `qwen3-fast:latest` | `VERIFIED` present; how the two custom tags were built is `NOT VERIFIED` (no Modelfile in this directory) |
| Ollama version | 0.40.3 | `VERIFIED` |

Stored by Ollama outside this directory. Obtain with `ollama pull gemma3:4b`.

## Translation model — MADLAD-400 3B (CTranslate2 INT8)

| Item | Value | Status |
|---|---|---|
| Folder | `madlad400-3b-ct2-int8\` (2 839 MB) | `VERIFIED` |
| Files | `model.bin` (2 950 208 290 bytes), `shared_vocabulary.json`, `spiece.model`, `tokenizer.json`, `tokenizer_config.json`, `config.json`, `special_tokens_map.json`, `added_tokens.json` | `VERIFIED` |
| Upstream | Downloaded from Hugging Face (the folder contains `.cache\huggingface\download\*.metadata`; recorded commit `fd0b55729c074372eb84b52b9309a00dc65c40c4`). **The repository id is not recorded locally.** | repo id `NOT VERIFIED` |
| Base model | Google MADLAD-400 3B MT, converted to CTranslate2 with INT8 quantization (inferred from folder name and `server.py` strings) | `NOT VERIFIED` |
| SHA256 of `model.bin` | not computed in this audit | — |

To pin provenance, find the Hugging Face repository whose commit `fd0b5572…` matches and record it here.

## Uzbek TTS — VITS ONNX

| Item | Value | Status |
|---|---|---|
| Model | `stt-tts-uz\models\vits_uzbek_finetuned.onnx`, 114 052 323 bytes | `VERIFIED` |
| SHA256 | `75fc730755c107cfdc64618bdd2276efb5eb4a359a4eefcf17e8422b3c3b9401` | `VERIFIED` |
| Config | `stt-tts-uz\models\uz_tts_base.json` (22 050 Hz, `uzbek_cleaners`, `add_blank`, single speaker) | `VERIFIED` |
| Text front end | `stt-tts-uz\text\` (`cleaners.py`, `symbols.py`, `__init__.py`) from `github.com/3936010/STT-TTS-Uz` @ `a2d726f`, with a local patch ([patches/](patches/README.md)) | `VERIFIED` |
| Model origin | The upstream README points to a Google Drive folder for "pre-trained ONNX models"; `models\` is untracked in that repo. Whether this exact file comes from that folder, and who fine-tuned it on what data, is not recorded. | `NOT VERIFIED` |
| Output | WAV 22 050 Hz mono 16-bit | `HISTORICAL TEST RESULT` (header parsed 2026-10-13) |

Do not modify this model, its config, or the service.

## Uzbek TTS — male voice (Uzbek_TTS, F5-style)

| Item | Value | Status |
|---|---|---|
| Code | `Uzbek_TTS-test\` = clone of `github.com/Saidakmal02/Uzbek_TTS` @ `37b7400` (Conditional Flow Matching + DiT, F5-TTS architecture: dim 1024, depth 22) with local changes ([patches/](patches/README.md)) | `VERIFIED` |
| Checkpoint | `Uzbek_TTS-test\ckpts\UZ.safetensors`, 1.3 GB, SHA256 `27e7dc127b78453f539cfe5c5b23d4b542c5537ac179f3aa2c877d8cece2ca12` (checked at service start) | `VERIFIED` |
| Vocoder | `charactr/vocos-mel-24khz` from the Hugging Face cache (the service runs with `HF_HUB_OFFLINE=1`) | `VERIFIED` |
| Voice | cloned from the reference recording `test_data\test_erkak.wav` (SHA256 `900b6337…`) with its transcript "Jizzax kollejlarida infraqizil aniqlagichli turniketlar o'rnatilmoqda." Who is speaking in it is not recorded. | `NOT VERIFIED` origin |
| Settings | exactly those of `test_generate.py` (owner-approved sample): `nfe_step=8`, `speed=1.0`, `cfg_strength=2`, Euler, fp16 on CUDA | `VERIFIED` |
| Output | WAV 24 000 Hz mono 16-bit (service) | `VERIFIED` 2026-10-17 |
| Speed / memory | GTX 1650: ≈ 1.8 s per flow step, 8 steps → ≈ 15 s per sentence; 0.68 GB VRAM loaded, 1.94 GB peak | `VERIFIED` 2026-10-17 |
| Environment | `Uzbek_TTS-test\.venv` (Python 3.12.10, torch 2.14.1+cu126, torchaudio 2.11.0, vocos 0.1.0) | `VERIFIED` |

## Piper voices

| Voice | File | Size | SHA256 | Config |
|---|---|---|---|---|
| Russian `irina` (medium) | `ru_RU-irina-medium.onnx` | 63 201 294 | `8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa` | `ru_RU-irina-medium.onnx.json` |
| English `lessac` (medium) | `en_US-lessac-medium.onnx` | 63 201 294 | `5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f` | `en_US-lessac-medium.onnx.json` |

Both configs: 22 050 Hz, quality `medium`, 1 speaker, espeak voices `ru` / `en-us`, `piper_version 1.0.0` (`VERIFIED`).
Upstream is presumably the `rhasspy/piper-voices` collection on Hugging Face; the download source and revision are not recorded (`NOT VERIFIED`).

## Kokoro English — Kokoro-82M + `af_heart`

| Item | Value |
|---|---|
| Upstream | <https://huggingface.co/hexgrad/Kokoro-82M> @ commit `f3ff3571791e39611d31c381e3a41a3af07b4987` |
| Weights | `kokoro-models\kokoro-82m\kokoro-v1_0.pth`, 327 212 226 bytes, SHA256 `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4` |
| Voicepack | `kokoro-models\kokoro-82m\voices\af_heart.pt`, 523 425 bytes, SHA256 `0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff` |
| Config | `kokoro-models\kokoro-82m\config.json` |
| G2P | `misaki` English (`KPipeline(lang_code="a")`, American English) with espeak-ng fallback; needs spaCy `en_core_web_sm` |

Status: downloaded 2026-10-13 from the pinned commit; SHA256 compared with the Hugging Face LFS object ids at download time (`HISTORICAL TEST RESULT`). The voicepack hash is re-checked by the server at every start (`SOURCE-CODE CONFIRMED`).

## Kokoro Russian — Kokoro-RU + `masha`

| Item | Value |
|---|---|
| Upstream | <https://huggingface.co/zaakirio/kokoro-ru> @ commit `d649c57b239b18c4c384378127cbf01dba039bc1` |
| Weights | `kokoro-models\kokoro-ru\kokoro-ru-v2-base.pth`, 327 220 619 bytes, SHA256 `3bbee5bc05cfa182afc365b9116eaed8355f939c3c0af8aa0e43fdc45343ca15` (shared by `sveta` and `masha`) |
| Voicepack | `kokoro-models\kokoro-ru\voices\masha.pt`, 523 831 bytes, SHA256 `464d64ae793647c3b3f9d1f08ce5b11c641a61799f0bca65f111e6aad5d0a362` |
| Not downloaded | `sveta`, `dima` voicepacks, the `dima` checkpoint, ONNX exports |
| Config / vocab | `config.json`, `kokoro-config.json` |
| G2P script | `ru_g2p.py` (unmodified; SHA256 `d45057711b453a6349dac9d56b24272feaba42fbbd9ce43304dc9d82404777b4`) |
| espeak data | `espeak-data\` — 364 files; an espeak-ng data build whose Russian rules honour combining-acute stress marks. File sizes compared with upstream at download; `ru_dict` and `phondata` SHA256-checked. |
| Upstream model card | saved as `kokoro-models\kokoro-ru\README.md` |

### Russian G2P chain (`SOURCE-CODE CONFIRMED`; outputs `HISTORICAL TEST RESULT` 2026-10-13)

1. **RUAccent** (`ruaccent` 1.5.8.3, `omograph_model_size="turbo3.1"`, `use_dictionary=True`, `tiny_mode=False`) adds stress, restores `ё`, resolves homographs. Its models (≈ 693 MB) live in `.venv-kokoro\Lib\site-packages\ruaccent\` and were downloaded from Hugging Face on first load.
2. `+vowel` stress marks become combining acute accents; orthoepic respelling (`-ого → -ово`, `что`-type clusters, `чн → шн` exceptions…).
3. **espeak-ng** (via `misaki`/`phonemizer-fork`/`espeakng-loader`) with the repository's `espeak-data` produces IPA.
4. Normalization into Kokoro's vocabulary, positional vowel reduction, long `щ`.

Examples recorded on 2026-10-13:

| Input | After RUAccent | IPA |
|---|---|---|
| Здравствуйте! Меня зовут Маша. Чем я могу вам помочь? | Здра́вствуйте! Меня́ зову́т Ма́ша. Че́м я могу́ ва́м помо́чь? | `zdrˈɑstvujtʲi! mʲinʲˈɑ zɐvˈut mˈɑʃə. ʧˈem ˈja mɐɡˈu vˈɑm pɐmˈoʧ?` |
| Ёлка, еще, все хорошо. | Ёлка, ещё́, всё хорошо́. | `jˈolkə, jɪɕːˈo, fsʲˈo xərɐʃˈo.` |
| Замок стоит на горе. На двери висит замок. | За́мок стои́т на горе́. На двери́ виси́т замо́к. | `zˈɑmək … zɐmˈok.` |
| У меня 25 рублей и 3 яблока. | У меня́ 25 рубле́й и 3 я́блока. | `u mʲinʲˈɑ dvˈɑʦɐtʲpʲˈɑtʲ rublʲˈej ɪ trʲˈi ˈjabləkə.` |

Pronunciation was checked at the phoneme level only; no listening test or ASR round-trip was done (`NOT VERIFIED` perceptually).
Upstream states homograph accuracy of 93.8 % and lists known timbre/fricative artifacts (see the saved model card).

### Windows-specific UTF-8 workaround

`ru_g2p.py` reads `kokoro-config.json` with `Path.read_text()` and no encoding. On a Windows locale
such as cp1251 this raises `UnicodeDecodeError` (observed 2026-10-13). The upstream file is left
untouched; instead `kokoro_tts_server.py` re-launches itself with `python -X utf8` when
`sys.flags.utf8_mode` is off.

## Legacy / unused models present on disk

| Path | What | Used by services |
|---|---|---|
| `nllb-int8\` (600 MB) | NLLB-200 distilled 600M, CTranslate2 INT8 (per legacy scripts) | no |
| `Uzbek_TTS-test\ckpts\UZ.safetensors` | used since 2026-10-17 by the male voice service (see below) | yes, 8770 |

## Integrity re-check commands

```powershell
Set-Location C:\local-ai-translator
Get-FileHash -Algorithm SHA256 `
  kokoro-models\kokoro-82m\kokoro-v1_0.pth, kokoro-models\kokoro-82m\voices\af_heart.pt,
  kokoro-models\kokoro-ru\kokoro-ru-v2-base.pth, kokoro-models\kokoro-ru\voices\masha.pt,
  ru_RU-irina-medium.onnx, en_US-lessac-medium.onnx, stt-tts-uz\models\vits_uzbek_finetuned.onnx |
  ForEach-Object { '{0}  {1}' -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) }
```

Compare with the tables above.
