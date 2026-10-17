# Licensing

- **Last verified:** 2026-10-13
- **Status:** package licenses `VERIFIED` from installed package metadata; model licenses as marked. **This is an inventory, not legal advice — no legal review has been done.**
- **Related:** [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md), [SECURITY.md](SECURITY.md)

## 1. This project's own code — MIT

The repository contains [`LICENSE`](../LICENSE): MIT License, "Copyright (c) 2026 Firdavs Nurmatov"
(`VERIFIED` 2026-10-13; the file was added by the owner in the repository's initial commit on GitHub).

The MIT license applies to the files in this repository only — the service scripts, the page, the
start scripts and the documentation. It does **not** relicense any model, voice, or third-party
library the system downloads or loads at runtime; each keeps its own terms (sections 2–3).

Points that still deserve attention (`PROPOSED`, not legal advice):

- GPL-licensed components are **used at arm's length**, not embedded: `piper-tts` (GPL-3.0-or-later) is run as a separate process; `phonemizer-fork` (GPLv3+) and espeak-ng (GPL-3.0) are imported/loaded inside the Kokoro server process; `Unidecode` (GPLv2+) is imported inside the Uzbek TTS process. Whether importing GPL libraries constrains the license of *your* server scripts when you distribute only the scripts (not the libraries) is a question for someone qualified. (MIT itself is GPL-compatible; the question matters mainly if the scripts and those libraries are ever shipped together as one product.)
- The repository does not contain model weights, so model licenses govern use, not the repo's license.
- `docs/patches/stt-tts-uz-text-cleaners.patch` contains a few context lines from a third-party file whose repository has no license; it is kept only as a reproducibility record.

## 2. Models and voices

| Asset | License | Source of the statement | Status |
|---|---|---|---|
| Kokoro-82M weights + `af_heart` voice | Apache-2.0 | Hugging Face model metadata, read 2026-10-13: <https://huggingface.co/hexgrad/Kokoro-82M> | `HISTORICAL` (read from the API during integration) |
| Kokoro-RU weights + `masha` voice | **OpenRAIL** (weights/voices); code Apache-2.0 | Model card, saved locally as `kokoro-models\kokoro-ru\README.md`; <https://huggingface.co/zaakirio/kokoro-ru> | `VERIFIED` in the saved card |
| `ru_g2p.py`, `espeak-data` (from Kokoro-RU) | code Apache-2.0 per the card; `espeak-data` is derived from espeak-ng (GPL-3.0) | model card; espeak-ng project | card `VERIFIED`; espeak-data terms `NOT VERIFIED` |
| RUAccent package and models | package: Apache Software License (classifier); model files: not checked | package metadata; <https://github.com/Den4ikAI/ruaccent> | package `VERIFIED`, models `NOT VERIFIED` |
| MADLAD-400 3B (and the CTranslate2 conversion) | believed Apache-2.0 (Google MADLAD-400) | not recorded locally; conversion repository unknown | `NOT VERIFIED` |
| `gemma3:4b` (Ollama), used since 2026-10-17 | Gemma Terms of Use (Google; not an OSI licence, use restrictions apply) | check `ollama show gemma3:4b --license` | `NOT VERIFIED` |
| `qwen3:1.7b` (Ollama), used until 2026-10-17 | believed Apache-2.0 (Qwen3) | check `ollama show qwen3:1.7b --license` | `NOT VERIFIED` |
| Piper voices `ru_RU-irina-medium`, `en_US-lessac-medium` | per-voice terms in the Piper voices collection (each voice has a `MODEL_CARD`) | <https://huggingface.co/rhasspy/piper-voices> | `NOT VERIFIED` — read both model cards before any redistribution or commercial use |
| Uzbek VITS model `vits_uzbek_finetuned.onnx` | **unknown** — origin and training data not recorded | — | `NOT VERIFIED` |
| `Uzbek_TTS-test` code and `UZ.safetensors` (male voice, since 2026-10-17) | **no license file** in `github.com/Saidakmal02/Uzbek_TTS`; the architecture is F5-TTS (code MIT), and F5-TTS base weights are CC-BY-NC-4.0 — if this checkpoint was fine-tuned from them, non-commercial terms may apply | local clone | `NOT VERIFIED` |
| Male voice reference recording `test_erkak.wav` | **unknown** speaker and consent; the service clones this person's voice | — | `NOT VERIFIED` |
| `stt-tts-uz` source (`text/` front end) | **no license file** in the repository (`github.com/3936010/STT-TTS-Uz`) → no explicit permission to redistribute | local clone | `VERIFIED` absence |
| NLLB-200 (legacy, unused) | believed CC-BY-NC-4.0 (non-commercial) | not recorded locally | `NOT VERIFIED` |

### Kokoro-RU / OpenRAIL — must be reviewed separately

The Russian voice is the most restricted asset in the system:

- OpenRAIL licenses allow use and redistribution **subject to use-based restrictions** that travel with the model. The exact restriction text for this model was not reviewed.
- The model card states the voices come from the "Dialogs corpus (studio, consented actors, OpenRAIL)". The corpus terms were not reviewed.
- **Before any commercial use, redistribution of the weights/voicepack, or shipping a product with the `masha` voice, read the OpenRAIL text attached to `zaakirio/kokoro-ru` and the Dialogs corpus terms, and get them checked.** Nothing in this repository should be taken as clearance.

## 3. Python packages (from installed metadata, `VERIFIED` 2026-10-13)

| Package | Version | License (as declared) | Environment |
|---|---|---|---|
| torch | 2.14.1 / 2.14.1+cpu | Apache-2.0 AND … BSD (compound expression) | `.venv`, `.venv-kokoro` |
| ctranslate2 | 4.8.2 | MIT | `.venv` |
| transformers | 4.57.6 / 5.19.0 | Apache 2.0 | `.venv`, `.venv-kokoro` |
| sentencepiece | 0.2.2 | Apache-2.0 | `.venv` |
| requests | 2.34.2 | Apache-2.0 | `.venv` |
| onnxruntime | 1.31.0 | MIT | three envs |
| numpy | 2.5.4 | BSD-3-Clause AND others | all |
| scipy | 1.18.1 | BSD | Uzbek TTS |
| Unidecode | 1.4.0 | **GPLv2+** | Uzbek TTS |
| piper-tts | 1.8.0 | **GPL-3.0-or-later** | `.venv-piper` |
| kokoro | 0.9.4 | Apache | `.venv-kokoro` |
| misaki | 0.9.4 | Apache | `.venv-kokoro` |
| ruaccent | 1.5.8.3 | Apache Software License | `.venv-kokoro` |
| phonemizer-fork | 3.3.2 | **GPLv3+** | `.venv-kokoro` |
| espeakng-loader | 0.2.4 | not declared in metadata (bundles espeak-ng, GPL-3.0) | `.venv-kokoro` |
| spacy | 3.8.16 | MIT | `.venv-kokoro` |
| soundfile | 0.14.0 | BSD 3-Clause | `.venv-kokoro` |
| psutil | 7.2.2 | BSD-3-Clause | `.venv-kokoro` |

Transitive dependencies (≈ 100 more in `.venv-kokoro`) were not reviewed.

## 4. Open licensing questions

1. ~~Which license for the project's own code?~~ Resolved 2026-10-13: MIT.
2. Exact OpenRAIL restrictions for Kokoro-RU and the Dialogs corpus terms.
3. Origin and license of the Uzbek VITS model and of the `STT-TTS-Uz` code it depends on (ask the upstream author for a license).
4. Per-voice terms of the two Piper voices.
5. Exact source repository and license of the MADLAD CTranslate2 conversion.
6. Whether GPL components in the dependency set affect the intended distribution model.
