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
