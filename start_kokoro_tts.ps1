Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv-kokoro\Scripts\python.exe" -X utf8 "$PSScriptRoot\kokoro_tts_server.py"
