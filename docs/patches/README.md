# Local patches to third-party code

## `stt-tts-uz-text-cleaners.patch`

- **Applies to:** `text/cleaners.py` in <https://github.com/3936010/STT-TTS-Uz> at commit `a2d726f` (the clone in `stt-tts-uz\`).
- **Generated:** 2026-10-13 with `git -C stt-tts-uz diff -- text/cleaners.py` (read-only export of an existing, uncommitted modification; the working tree was not changed).
- **What it does:** wraps `from phonemizer import phonemize` in `try/except ImportError` and makes the two English cleaners return un-phonemized text when `phonemizer` is absent.
- **Why it matters:** `tts_onnx_server.py` imports this module. The Uzbek TTS environment (`stt-tts-uz\.venv-tts`) does not contain `phonemizer`, so without the patch the service fails at import. The Uzbek cleaner itself (`uzbek_cleaners`) is not modified.
- **Who made it / when:** not recorded (present before the 2026-10-13 audit).

Apply to a fresh clone:

```powershell
git -C stt-tts-uz checkout a2d726f
git -C stt-tts-uz apply ..\docs\patches\stt-tts-uz-text-cleaners.patch
```

The patch file is UTF-8 without BOM, LF line endings. It was checked on 2026-10-13 with
`git apply --check --reverse` against the modified working tree (exit code 0), i.e. it exactly
describes the local modification. Applying it to a fresh clone has not been tested.

Other untracked local files in that clone: `models\` (the Uzbek model and config), `.venv-tts\`,
`test_finetuned_tts.py`, `outputs\finetuned_test.wav`.

The upstream repository has **no license file**; this patch is kept as a record for reproducibility,
not as a redistribution of upstream code beyond the few context lines of the diff. See [../LICENSING.md](../LICENSING.md).

## `uzbek-tts-male-voice.patch`

- **Applies to:** `tts.py`, `uz_tts/model/backbones/dit.py`, `uz_tts/model/cfm.py`, `uz_tts/model/modules.py` in
  <https://github.com/Saidakmal02/Uzbek_TTS> at commit `37b7400` (the clone in `Uzbek_TTS-test\`).
- **Generated:** 2026-10-17 with `git -C Uzbek_TTS-test diff --output=… -- <the four files>`; checked with
  `git apply --check --reverse` against the working tree (exit code 0). Applying it to a fresh clone has not been tested.
- **What it does:** the model runs in fp16 on CUDA, but the convolutional position embedding is computed in fp32
  (`modules.py`; fp16 produced NaN/Inf on the GTX 1650); `dit.py`/`cfm.py`/`tts.py` add NaN/Inf diagnostics (printed
  lines; `uz_male_tts_server.py` swallows them), `torch.compile` is disabled.
- **Why it matters:** `uz_male_tts_server.py` imports this code; the approved sample `test_uzbek_tts.wav` was made with it.
- **Who made it / when:** 2026-10-12 (before this session; not recorded further).

Other untracked local files in that clone: `ckpts\UZ.safetensors`, `.venv\`, `test_generate*.py`, `test_load.py`,
`check_*.py`, `*.backup`, `uz_tts\model\modules.py.*.bak`, the generated test WAVs.
The upstream repository has **no license file**; see [../LICENSING.md](../LICENSING.md).
