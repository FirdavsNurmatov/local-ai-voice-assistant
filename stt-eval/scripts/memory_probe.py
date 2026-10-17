"""Measure STT memory step by step in ONE process: base model, then NavAI next to it, then unload/reload.

usage: python memory_probe.py <out.json> [min_free_commit_mb=4000]
Stops (without loading the next model) when free system commit drops below the limit.
"""
import gc, json, os, sys, time
from pathlib import Path
os.environ["HF_HUB_OFFLINE"] = "1"
import psutil
ROOT = Path(__file__).resolve().parents[2]
out_path = Path(sys.argv[1]); MIN_FREE = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
P = psutil.Process(); steps = []

def free_commit_mb():
    import ctypes
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in (
            "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
    s = MS(); s.dwLength = ctypes.sizeof(s); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return int(s.ullAvailPageFile / 1e6)

def mark(name, t=None):
    gc.collect(); m = P.memory_info()
    row = {"step": name, "rss_mb": round(m.rss / 1e6), "commit_mb": round(m.private / 1e6),
           "process_peak_commit_mb": round(m.peak_pagefile / 1e6), "process_peak_rss_mb": round(m.peak_wset / 1e6),
           "system_free_commit_mb": free_commit_mb(), "seconds": round(t, 2) if t is not None else None}
    steps.append(row); print(row, flush=True)
    out_path.write_text(json.dumps(steps, indent=1), encoding="utf-8")

def guard(next_step):
    if free_commit_mb() < MIN_FREE:
        mark(f"STOPPED before {next_step}: free commit below {MIN_FREE} MB"); sys.exit(2)

mark("start")
from faster_whisper import WhisperModel, decode_audio
mark("import faster_whisper")
audio_uz = decode_audio(str(ROOT / "stt-test-audio" / "uz_long.wav"), sampling_rate=16000)
audio_ru = decode_audio(str(ROOT / "stt-test-audio" / "ru_long.wav"), sampling_rate=16000)
kw = dict(device="cpu", compute_type="int8", cpu_threads=4, num_workers=1, local_files_only=True)

guard("base model"); t = time.perf_counter()
base = WhisperModel(str(ROOT / "stt-models" / "faster-whisper-small"), **kw); mark("base model loaded", time.perf_counter() - t)
t = time.perf_counter(); list(base.transcribe(audio_ru, language="ru", beam_size=5, vad_filter=True)[0]); mark("base model after RU inference (16 s audio)", time.perf_counter() - t)

guard("NavAI"); t = time.perf_counter()
uz = WhisperModel(str(ROOT / "stt-models" / "navai-whisper-small-uzbek-ct2-int8"), **kw); mark("NavAI loaded next to base", time.perf_counter() - t)
t = time.perf_counter(); list(uz.transcribe(audio_uz, language="uz", beam_size=5, vad_filter=True, without_timestamps=True, no_repeat_ngram_size=4)[0]); mark("both loaded, after NavAI inference (9 s audio)", time.perf_counter() - t)
t = time.perf_counter(); list(base.transcribe(audio_ru, language="ru", beam_size=5, vad_filter=True)[0]); mark("both loaded, after base inference", time.perf_counter() - t)

del uz; gc.collect(); time.sleep(1); mark("NavAI unloaded (del + gc)")
guard("NavAI reload"); t = time.perf_counter()
uz = WhisperModel(str(ROOT / "stt-models" / "navai-whisper-small-uzbek-ct2-int8"), **kw); mark("NavAI reloaded", time.perf_counter() - t)
del uz, base; gc.collect(); time.sleep(1); mark("both unloaded")
