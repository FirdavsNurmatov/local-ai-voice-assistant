# Development setup (rebuilding the environment)

- **Last verified:** 2026-10-13
- **Status:** the Kokoro steps were executed on 2026-10-13 (`HISTORICAL TEST RESULT`). The steps for `.venv`, `.venv-piper` and `stt-tts-uz\.venv-tts` are **reconstructed** from the installed packages and have not been replayed on a clean machine (`NOT VERIFIED`).
- **Related:** [DEPENDENCIES.md](DEPENDENCIES.md), [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md), [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md)

> Do not run these steps on the working machine. They are for a new machine or a new folder.
> Never reinstall into the existing environments.

## 0. Requirements

- Windows 10/11 x64, Python **3.12** (`py -3.12`), Git, PowerShell 5.1.
- ≈ 15 GB free disk for environments and active models.
- Memory: 8 GB RAM runs everything except the Russian Kokoro voice; 16 GB or a larger pagefile is needed for the complete set ([MEMORY_AND_PERFORMANCE.md](MEMORY_AND_PERFORMANCE.md)).
- Internet access during setup only.

Target layout (everything relative to the project root, e.g. `C:\local-ai-translator`):

```
server.py  tts_onnx_server.py  piper_tts_server.py  kokoro_tts_server.py  local_voice_chat.html
.venv\  .venv-piper\  .venv-kokoro\
madlad400-3b-ct2-int8\
ru_RU-irina-medium.onnx(.json)  en_US-lessac-medium.onnx(.json)
stt-tts-uz\  (.venv-tts\, text\, models\)
kokoro-models\kokoro-82m\  kokoro-models\kokoro-ru\
```

## 1. Ollama

Install Ollama, then:

```powershell
ollama pull qwen3:1.7b
Invoke-RestMethod http://127.0.0.1:11434/api/version
```

## 2. Chat backend environment (`.venv`) — reconstructed

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r docs\requirements\chat-venv.freeze.txt
```

Minimal alternative (direct imports only): `ctranslate2`, `transformers`, `sentencepiece`, `requests`.

**MADLAD model:** place the CTranslate2 INT8 conversion of MADLAD-400 3B in `madlad400-3b-ct2-int8\`
(files listed in [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md)). The exact Hugging Face repository it
was downloaded from is **unknown** — only the commit hash `fd0b5572…` is recorded. Until that is
resolved, copy the folder from the working machine.

## 3. Uzbek TTS (`stt-tts-uz`) — reconstructed

```powershell
git clone https://github.com/3936010/STT-TTS-Uz.git stt-tts-uz
git -C stt-tts-uz checkout a2d726f
git -C stt-tts-uz apply ..\docs\patches\stt-tts-uz-text-cleaners.patch
py -3.12 -m venv stt-tts-uz\.venv-tts
.\stt-tts-uz\.venv-tts\Scripts\python.exe -m pip install -r docs\requirements\uzbek-tts-venv.freeze.txt
```

Then put `vits_uzbek_finetuned.onnx` and `uz_tts_base.json` into `stt-tts-uz\models\`. Their origin
is not recorded (the upstream README links a Google Drive folder; whether it contains these exact
files is `NOT VERIFIED`). Verify the ONNX file's SHA256 against [MODELS_AND_VOICES.md](MODELS_AND_VOICES.md);
otherwise copy both files from the working machine.

## 4. Piper (`.venv-piper`) — reconstructed

```powershell
py -3.12 -m venv .venv-piper
.\.venv-piper\Scripts\python.exe -m pip install -r docs\requirements\piper-venv.freeze.txt
```

Place `ru_RU-irina-medium.onnx`, `ru_RU-irina-medium.onnx.json`, `en_US-lessac-medium.onnx` and
`en_US-lessac-medium.onnx.json` in the project root (Piper voice collection; verify SHA256).

## 5. Kokoro (`.venv-kokoro`) — as executed on 2026-10-13

```powershell
py -3.12 -m venv .venv-kokoro
$py = '.\.venv-kokoro\Scripts\python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install "kokoro>=0.9.4" "misaki[en]" ruaccent soundfile psutil
& $py -m pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

For exact versions use `docs\requirements\kokoro-venv.freeze.txt` instead of the unpinned names
(install torch from the CPU index first).

**Models** — download from the pinned commits and verify SHA256:

```powershell
$ProgressPreference = 'SilentlyContinue'
$ru = 'kokoro-models\kokoro-ru';  $en = 'kokoro-models\kokoro-82m'
New-Item -ItemType Directory -Force "$ru\voices", "$ru\espeak-data", "$en\voices" | Out-Null
$rr = 'https://huggingface.co/zaakirio/kokoro-ru/resolve/d649c57b239b18c4c384378127cbf01dba039bc1'
$er = 'https://huggingface.co/hexgrad/Kokoro-82M/resolve/f3ff3571791e39611d31c381e3a41a3af07b4987'
foreach ($f in 'kokoro-ru-v2-base.pth','voices/masha.pt','ru_g2p.py','config.json','kokoro-config.json','README.md') {
    curl.exe -sSL --fail -o (Join-Path $ru ($f -replace '/','\')) "$rr/$f" }
foreach ($f in 'kokoro-v1_0.pth','voices/af_heart.pt','config.json') {
    curl.exe -sSL --fail -o (Join-Path $en ($f -replace '/','\')) "$er/$f" }
```

`espeak-data\` (364 files, with sub-folders and names containing spaces and `!`) must also be
mirrored from the same `kokoro-ru` commit, e.g. by listing
`https://huggingface.co/api/models/zaakirio/kokoro-ru/tree/<commit>/espeak-data?recursive=true`
and downloading each `path` with URL-escaped segments. Check that the count is 364 and that
`espeak-data\ru_dict` has SHA256 `fec9c58731c7670b31ec6c36045d954760308234057c449565878b7e17266433`.
Without the correct `espeak-data`, Russian stress is silently wrong.

**RUAccent models** are fetched automatically the first time `RuG2P()` is constructed, into
`.venv-kokoro\Lib\site-packages\ruaccent\` (≈ 693 MB). The server forces offline mode, so do the first load once by hand with network access:

```powershell
& $py -X utf8 -c "import sys; sys.path.insert(0, r'kokoro-models\kokoro-ru'); from ru_g2p import RuG2P; g = RuG2P(); print(g('Привет, как дела?'))"
```

This one command needs ≈ 2.5 GB of free commit.

## 6. First start and verification

Follow [WINDOWS_RUNBOOK.md](WINDOWS_RUNBOOK.md) §4–§6, then [TESTING.md](TESTING.md).

## 7. Working on the code

- The frontend is re-read from disk on each page load — edit and refresh.
- A Python service must be restarted to pick up changes. Restarting `server.py` reloads MADLAD (tens of seconds and ≈ 10 GB commit); avoid having two copies alive at once.
- Rules for safe changes: [../CONTRIBUTING.md](../CONTRIBUTING.md).
