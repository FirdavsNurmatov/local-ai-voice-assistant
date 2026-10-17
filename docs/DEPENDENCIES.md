# Dependencies

- **Last verified:** 2026-10-13 · **Status:** `VERIFIED` (`pip freeze --all` and `pyvenv.cfg` of each environment, read-only)
- **Related:** [requirements/](requirements/README.md), [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md), [LICENSING.md](LICENSING.md)

## Four separate environments — by design

Each service has its own virtual environment. They **cannot** be merged into one
`requirements.txt`: for example `.venv` uses `transformers 4.57.6` / `huggingface_hub 0.36.2`
while `.venv-kokoro` uses `transformers 5.19.0` / `huggingface_hub 2.2.0`.

All four were created with `python -m venv` from the same base interpreter:
**CPython 3.12.10 (64-bit, MSC v.1943)** at `C:\Users\<user>\AppData\Local\Programs\Python\Python312`.

| Environment | Used by | Packages | Size | Snapshot |
|---|---|---|---|---|
| `.venv` | `server.py` | 43 | 879 MB | [requirements/chat-venv.freeze.txt](requirements/chat-venv.freeze.txt) |
| `stt-tts-uz\.venv-tts` | `tts_onnx_server.py` | 8 | 242 MB | [requirements/uzbek-tts-venv.freeze.txt](requirements/uzbek-tts-venv.freeze.txt) |
| `.venv-piper` | Piper CLI spawned by `piper_tts_server.py` | 8 | 157 MB | [requirements/piper-venv.freeze.txt](requirements/piper-venv.freeze.txt) |
| `.venv-kokoro` | `kokoro_tts_server.py` | 106 | 1 807 MB (incl. 693 MB RUAccent models, 502 MB torch) | [requirements/kokoro-venv.freeze.txt](requirements/kokoro-venv.freeze.txt) |

## Directly used packages

### `.venv` — chat backend

Imports in `server.py`: `requests`, `ctranslate2`, `transformers.AutoTokenizer` (slow SentencePiece tokenizer → `sentencepiece`).

| Package | Version | Note |
|---|---|---|
| ctranslate2 | 4.8.2 | translation runtime |
| transformers | 4.57.6 | tokenizer only |
| sentencepiece | 0.2.2 | |
| tokenizers | 0.22.2 | |
| huggingface_hub | 0.36.2 | not used at runtime (`local_files_only=True`) |
| requests | 2.34.2 | Ollama + TTS proxy |
| torch | 2.14.1 | installed (left from earlier experiments; `server.py` does not import it directly, `transformers` may) |
| numpy | 2.5.4 | |

### `stt-tts-uz\.venv-tts` — Uzbek TTS

Imports: `numpy`, `onnxruntime`, `scipy.io.wavfile`, and `text` / `text.symbols` from `stt-tts-uz\` (which import `unidecode`).

| Package | Version |
|---|---|
| onnxruntime | 1.31.0 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| Unidecode | 1.4.0 |

`phonemizer` is **not** installed; the local patch to `text/cleaners.py` makes it optional. The
upstream `stt-tts-uz\requirements.txt`, `pyproject.toml` and `uv.lock` describe a larger environment
that was not used to build this venv.

### `.venv-piper` — Piper

| Package | Version |
|---|---|
| piper-tts | 1.8.0 (provides `python -m piper` and `piper.exe`; bundles its own espeak-ng data — `NOT VERIFIED` in detail) |
| onnxruntime | 1.31.0 |
| numpy | 2.5.4 |

`piper_tts_server.py` itself needs only the standard library.

### `.venv-kokoro` — Kokoro

| Package | Version | Role |
|---|---|---|
| torch | 2.14.1+cpu | inference (installed from `https://download.pytorch.org/whl/cpu`) |
| kokoro | 0.9.4 | `KModel`, `KPipeline` |
| misaki | 0.9.4 | English G2P, espeak wrapper |
| ruaccent | 1.5.8.3 | Russian stress / ё / homographs (ONNX models inside the package directory) |
| onnxruntime | 1.31.0 | RUAccent models |
| transformers | 5.19.0 | RUAccent tokenizers, Kokoro |
| huggingface_hub | 2.2.0 | forced offline at runtime |
| phonemizer-fork | 3.3.2 | espeak-ng bindings |
| espeakng-loader | 0.2.4 | bundled espeak-ng shared library |
| spacy | 3.8.16 | English tokenization for misaki |
| en_core_web_sm | 3.8.0 | installed from the spaCy GitHub release wheel (URL + hash recorded in the freeze file) |
| num2words | 0.5.14 | number expansion |
| numpy | 2.5.4 | |
| soundfile | 0.14.0 | installed; the server writes WAV with the standard-library `wave` module |
| psutil | 7.2.2 | `memory_mb` in `/api/health` (optional: failure → `null`) |

## External (non-Python) dependencies

| Dependency | Version / state | Status |
|---|---|---|
| Ollama | 0.40.3, `C:\Users\<user>\AppData\Local\Programs\Ollama\ollama.exe`, listening on `127.0.0.1:11434` | `VERIFIED` |
| Ollama model `gemma3:4b` (digest 68ceab7e…, 3.3 GB) | present (2026-10-17) | `VERIFIED` |
| Windows PowerShell | 5.1 | `VERIFIED` |
| Web browser | Tests on 2026-10-13 used the Claude desktop app's built-in (Chromium-based) browser; the project owner uses Firefox (seen running). Browser-specific behaviour is otherwise `NOT VERIFIED`. | partial |
| espeak-ng | no system-wide install required; libraries come from `espeakng-loader` (Kokoro) and `piper-tts` (Piper) | `SOURCE-CODE CONFIRMED` for Kokoro |
| Git | used only inside the three nested third-party folders | `VERIFIED` |

## What the snapshots do and do not give you

The freeze files are an exact record of **these four environments on this machine on 2026-10-13**.
Reinstalling from them should reproduce the Python side, but a working system also needs:

- model weights and voicepacks at the right paths and revisions ([MODELS_AND_VOICES.md](MODELS_AND_VOICES.md));
- RUAccent's model files (downloaded on first `RuG2P()` load — requires network once, with `HF_HUB_OFFLINE` unset);
- the `stt-tts-uz` source at commit `a2d726f` with the local patch;
- Ollama with the model pulled;
- enough commit memory ([MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md)).

`torch==2.14.1+cpu` is not on PyPI under that name; install it from the PyTorch CPU index first
(see [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)). Reinstalling from the snapshots has **not** been tested (`NOT VERIFIED`).
