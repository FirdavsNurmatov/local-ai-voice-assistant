Set-Location "C:\local-ai-translator"
$python = ".\stt-tts-uz\.venv-tts\Scripts\python.exe"
if (!(Test-Path $python)) { throw "TTS venv topilmadi: $python" }
& $python .\tts_onnx_server.py
