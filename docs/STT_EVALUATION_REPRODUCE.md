# Reproducing the Uzbek STT evaluation

- **Written:** 2026-10-14 · commands below are the ones actually used
- **Related:** [STT_EVALUATION.md](STT_EVALUATION.md) (results), [STT.md](STT.md) (production service)

Everything runs from `C:\local-ai-translator` in Windows PowerShell 5.1. Nothing here touches the
production environment `.venv-stt`, the production model, or any running service. Internet access is
needed **only** for steps 1–3 (downloads); every transcription in step 5 runs offline
(`HF_HUB_OFFLINE=1`, `local_files_only=True`).

Disk: ≈ 3.5 GB (models 1.7 GB, FLEURS archive 0.5 GB, evaluation venv ≈ 1.3 GB without CUDA, + ≈ 1.5 GB with CUDA wheels).

## 1. Evaluation environment (separate from production)

```powershell
py -3.12 -m venv .venv-stt-eval
.\.venv-stt-eval\Scripts\python.exe -m pip install --upgrade pip
.\.venv-stt-eval\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv-stt-eval\Scripts\python.exe -m pip install "faster-whisper==1.2.1" "av<17" transformers psutil
# optional, only for the GPU run:
.\.venv-stt-eval\Scripts\python.exe -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```

Exact versions used: [`stt-eval/requirements-eval.txt`](../stt-eval/requirements-eval.txt) (`pip freeze --all`).
`faster-whisper`, `ctranslate2` and `av` are the same versions as in production `.venv-stt`.
`uzbek-text-norm` (used by the NavAI model card) is not on PyPI; the evaluation uses its own
documented normaliser in `stt-eval/scripts/common.py`.

## 2. Candidate model (NavAI) and conversion

```powershell
$rev = '4b432caf21c2752bca3384b5df1d41cf0da2801d'
$d = 'stt-models\navai-whisper-small-uzbek-hf'
New-Item -ItemType Directory -Force $d | Out-Null
$files = (Invoke-RestMethod "https://huggingface.co/api/models/navai-uz/whisper-small-uzbek/tree/$rev") | Where-Object { $_.type -eq 'file' -and $_.path -ne 'family_scaling.png' }
foreach ($f in $files) { curl.exe -sSL --fail -o "$d\$($f.path)" "https://huggingface.co/navai-uz/whisper-small-uzbek/resolve/$rev/$($f.path)" }
# tokenizer.json is not shipped; faster-whisper needs it:
.\.venv-stt-eval\Scripts\python.exe -c "from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained(r'$d'); t.save_pretrained(r'$d')"
.\.venv-stt-eval\Scripts\ct2-transformers-converter.exe --model $d --output_dir stt-models\navai-whisper-small-uzbek-ct2-int8 --quantization int8 --copy_files tokenizer.json preprocessor_config.json --force
```

Check `model.safetensors` SHA256 = `3662e1baf3a9bc9a3b3df9bb75060c99708f8c461df19e0e3acd80ae6814411e` (= Hugging Face LFS id).
The production model `stt-models\faster-whisper-small` already exists (see [STT.md](STT.md)).

## 3. FLEURS Uzbek test data (real human speech, CC-BY-4.0)

```powershell
New-Item -ItemType Directory -Force stt-eval\fleurs | Out-Null
curl.exe -sSL --fail -o stt-eval\fleurs\test.tsv https://huggingface.co/datasets/google/fleurs/resolve/main/data/uz_uz/test.tsv
curl.exe -sSL --fail -o stt-eval\fleurs\test.tar.gz https://huggingface.co/datasets/google/fleurs/resolve/main/data/uz_uz/audio/test.tar.gz
```

Expected archive SHA256 `1c9e47b37064c4a84bb901e18c79cdc35b6f481673f500bf58ace0145dec057a` (dataset revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd` at download time).

## 4. Datasets

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$py = '.\.venv-stt-eval\Scripts\python.exe'
# 120 human recordings: one random speaker per sentence, 40 per duration tercile, seed 20261014; verifies hash, sample rate, length
& $py -I -X utf8 stt-eval\scripts\prepare_fleurs.py C:\local-ai-translator\stt-eval 120 20261014 1c9e47b37064c4a84bb901e18c79cdc35b6f481673f500bf58ace0145dec057a
# parity subset: every 6th clip of the sample (20 clips)
& $py -c "import csv; r=list(csv.DictReader(open(r'stt-eval\datasets\fleurs_uz_test_sample.csv',encoding='utf-8'))); p=r[2::6]; w=csv.DictWriter(open(r'stt-eval\datasets\fleurs_parity.csv','w',encoding='utf-8',newline=''),fieldnames=list(r[0])); w.writeheader(); w.writerows(p)"
# synthetic Uzbek (12 clips, already generated with the project's Uzbek TTS) and RU/EN regression clips
& $py -X utf8 stt-eval\scripts\make_datasets.py C:\local-ai-translator\stt-eval
& $py -X utf8 stt-eval\scripts\manifest.py C:\local-ai-translator
```

The 12 synthetic clips were produced once by `POST http://127.0.0.1:8766/api/tts` with the sentences
listed in `stt-eval\synthetic\subset.json` (the Uzbek TTS was started only for that step and stopped afterwards).

## 5. Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File stt-eval\scripts\run_all.ps1          # CPU matrix (~1 h on i7-9700K)
powershell -NoProfile -ExecutionPolicy Bypass -File stt-eval\scripts\run_all.ps1 -Gpu     # optional GTX 1650 run
& $py -X utf8 stt-eval\scripts\score.py stt-eval\runs stt-eval\datasets stt-eval\results
```

Each configuration runs in its own process, one after another, so the two models are never loaded
at the same time. Run files are named `<dataset>__<config>__<language>__<device>.json`; the
decoding options of every run are stored inside the file (`options`).

Outputs:

- `stt-eval\results\per_sample_results.csv` — one row per clip × configuration (raw reference, raw hypothesis, normalised copies, S/D/I, WER, CER, flags, latency).
- `stt-eval\results\summary.csv` — one row per dataset × configuration.
- `stt-eval\manifest_sha256.csv` — checksums of model and dataset files.

Before running, make sure no other heavy process is loaded (the evaluation records which project
services were listening at the start of each run in `services_at_start`).
