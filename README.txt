LOCAL BROWSER CHAT + FINE-TUNED UZBEK ONNX TTS

Files:
- server.py: updated main MADLAD + Ollama server; adds /api/tts proxy.
- local_voice_chat.html: browser UI with local ONNX TTS and browser TTS options.
- tts_onnx_server.py: separate persistent ONNX TTS service on 127.0.0.1:8766.
- start_tts.ps1: starts the TTS service from the dedicated .venv-tts.

Expected paths on the user's PC:
C:\local-ai-translator\server.py
C:\local-ai-translator\local_voice_chat.html
C:\local-ai-translator\tts_onnx_server.py
C:\local-ai-translator\stt-tts-uz\.venv-tts\Scripts\python.exe
C:\local-ai-translator\stt-tts-uz\models\vits_uzbek_finetuned.onnx
C:\local-ai-translator\stt-tts-uz\models\uz_tts_base.json
C:\local-ai-translator\madlad400-3b-ct2-int8

INSTALL:
1. Back up existing server.py and local_voice_chat.html first.
2. Copy the three files into C:\local-ai-translator, replacing server.py and local_voice_chat.html.
3. Confirm model/config exist under stt-tts-uz\models.
4. Terminal 1:
   cd C:\local-ai-translator
   .\start_tts.ps1
   Wait for "TTS modeli tayyor".
5. Terminal 2 (Ollama should already be running):
   cd C:\local-ai-translator
   .\.venv\Scripts\python.exe .\server.py
6. Open http://localhost:8765 and select "Mahalliy Uzbek TTS (ONNX)".
7. Click "Test ovozi" or send an Uzbek chat message. It should generate a WAV on the server and play it in the browser.
8. For laptop browser, use http://MAIN-PC-IP:8765 on the same trusted LAN. TTS service remains bound to 127.0.0.1 and is not exposed to LAN.

NOTES:
- The TTS ONNX session stays loaded in memory, rather than reloading for each sentence.
- Local ONNX TTS is used only when selected and the response language is Uzbek. Russian/English fall back to browser TTS.
- The browser rate/pitch controls affect browser TTS only; the ONNX model's synthesis parameters are currently fixed.
- STT/microphone transcription is not implemented here.
- This service has no authentication. Use only on a trusted LAN and do not port-forward it.
- Python syntax compilation was checked when packaging; runtime needs to be verified on the user's Windows machine.
