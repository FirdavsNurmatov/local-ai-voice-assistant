# Environment snapshots

Generated on 2026-10-13 with `<env>\Scripts\python.exe -m pip freeze --all` (read-only; nothing was
installed or changed). One file per environment — they are **not interchangeable** and must not be merged.

| File | Environment | Used by |
|---|---|---|
| [chat-venv.freeze.txt](chat-venv.freeze.txt) | `.venv` | `server.py` |
| [uzbek-tts-venv.freeze.txt](uzbek-tts-venv.freeze.txt) | `stt-tts-uz\.venv-tts` | `tts_onnx_server.py` |
| [piper-venv.freeze.txt](piper-venv.freeze.txt) | `.venv-piper` | Piper CLI started by `piper_tts_server.py` |
| [kokoro-venv.freeze.txt](kokoro-venv.freeze.txt) | `.venv-kokoro` | `kokoro_tts_server.py` |
| [stt-venv.freeze.txt](stt-venv.freeze.txt) | `.venv-stt` (generated 2026-10-14) | `stt_server.py` |

All four: CPython 3.12.10, 64-bit, Windows.

Notes

- `torch==2.14.1+cpu` (Kokoro) comes from `https://download.pytorch.org/whl/cpu`, not PyPI.
- `en_core_web_sm` is recorded as a direct URL with hash.
- `pip`/`setuptools` lines are included because of `--all`; they can be ignored when reinstalling.
- The files were written by Windows PowerShell and start with a UTF-8 byte-order mark; `pip install -r` accepts that.
- A matching Python environment is necessary but not sufficient — see [../DEPENDENCIES.md](../DEPENDENCIES.md#what-the-snapshots-do-and-do-not-give-you).

Regenerate after any deliberate dependency change:

```powershell
Set-Location C:\local-ai-translator
.\.venv-kokoro\Scripts\python.exe -m pip freeze --all | Set-Content -Encoding utf8 docs\requirements\kokoro-venv.freeze.txt
```
