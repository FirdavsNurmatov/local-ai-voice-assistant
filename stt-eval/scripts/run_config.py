"""Run ONE model/decoding configuration over ONE dataset in a fresh process.

usage: python run_config.py <config> <lang|auto> <dataset.csv> <out.json> [cpu|cuda] [limit]

Configs (all decoding options are written into the output file):
  small_prod     production model + production pipeline (stt_server.transcribe, unchanged code)
  navai_prod     NavAI CT2 model through the same production pipeline (identical options)
  small_neutral  production model, plain faster-whisper call, no prompt, no_repeat_ngram_size=4
  navai_neutral  NavAI CT2 model, same plain call
  navai_card     NavAI CT2, greedy (beam 1), no VAD, no_repeat_ngram_size=4 -> parity with the HF reference
  hf_navai       NavAI original weights via Transformers/PyTorch pipeline, greedy, generation_config (card usage)
  *_nots         any of the plain configs above + without_timestamps=True (post-hoc fix, see docs/STT_EVALUATION.md)
"""
import csv, json, os, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(r"C:\local-ai-translator")
os.environ["HF_HUB_OFFLINE"] = "1"
cfg, lang_mode, ds_path, out_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
device = sys.argv[5] if len(sys.argv) > 5 else "cpu"
limit = int(sys.argv[6]) if len(sys.argv) > 6 else None
forced = None if lang_mode == "auto" else lang_mode
clips = list(csv.DictReader(open(ds_path, encoding="utf-8")))[:limit]

import psutil
P = psutil.Process()

def listening():
    ports = {8765: "chat", 8766: "uz_tts", 8767: "piper", 8768: "kokoro", 8769: "stt", 11434: "ollama"}
    up = {c.laddr.port for c in psutil.net_connections("tcp") if c.status == "LISTEN"}
    return {name: (port in up) for port, name in ports.items()}

def gpu_query():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().splitlines()[0]
        used, util = (int(x) for x in out.split(","))
        return used, util
    except Exception:
        return None, None

state = {"services_at_start": listening(), "sys_free_commit_mb_at_start": round(psutil.virtual_memory().available / 1e6)}
gpu = {"base_mb": None, "peak_mb": 0, "util_samples": []}
stop = threading.Event()
if device == "cuda":
    gpu["base_mb"] = gpu_query()[0]
    def gpu_sampler():
        while not stop.is_set():
            used, util = gpu_query()
            if used is not None:
                gpu["peak_mb"] = max(gpu["peak_mb"], used); gpu["util_samples"].append(util)
            time.sleep(0.25)
    threading.Thread(target=gpu_sampler, daemon=True).start()

SMALL = ROOT / "stt-models" / "faster-whisper-small"
NAVAI_CT2 = ROOT / "stt-models" / "navai-whisper-small-uzbek-ct2-int8"
NAVAI_HF = ROOT / "stt-models" / "navai-whisper-small-uzbek-hf"
options = {}
t0 = time.perf_counter()
t0_wall = time.strftime("%Y-%m-%d %H:%M:%S")

if cfg == "hf_navai":
    import torch
    from transformers import pipeline
    from faster_whisper import decode_audio
    torch.set_num_threads(4)
    asr = pipeline("automatic-speech-recognition", model=str(NAVAI_HF), chunk_length_s=30,
                   device=0 if device == "cuda" else -1)
    gen = {"language": forced or "uz", "task": "transcribe"}
    options = {"runtime": f"transformers {__import__('transformers').__version__} / torch {torch.__version__} fp32",
               "generate_kwargs": gen, "generation_config": "shipped (greedy, no_repeat_ngram_size=4)", "chunk_length_s": 30, "vad": False}
    def run_one(data_path):
        a = decode_audio(data_path, sampling_rate=16000)
        r = asr({"array": a, "sampling_rate": 16000}, generate_kwargs=gen)
        return {"text": r["text"].strip(), "language": gen["language"], "duration": len(a) / 16000}
else:
    from faster_whisper import WhisperModel, decode_audio
    model_dir = NAVAI_CT2 if cfg.startswith("navai") else SMALL
    compute = "int8" if device == "cpu" else "int8_float16"
    model = WhisperModel(str(model_dir), device=device, compute_type=compute, cpu_threads=4, num_workers=1, local_files_only=True)
    options = {"runtime": f"faster-whisper {__import__('faster_whisper').__version__} / ctranslate2 {__import__('ctranslate2').__version__}",
               "model_dir": str(model_dir), "device": device, "compute_type": compute, "cpu_threads": 4}
    if cfg.endswith("_prod"):
        sys.path.insert(0, str(ROOT))
        import stt_server                      # production module, imported read-only; nothing is patched
        stt_server.ENGINE["model"] = model
        options.update({"pipeline": "stt_server.transcribe (production code)", "beam_size": 5, "vad_filter": True,
                        "condition_on_previous_text": False, "initial_prompt": dict(stt_server.INITIAL_PROMPTS),
                        "language_options": {k: {kk: str(vv) for kk, vv in v.items()} for k, v in stt_server.LANGUAGE_OPTIONS.items()},
                        "auto_rule": f"ru/en if p>={stt_server.LANGUAGE_THRESHOLD} else {stt_server.FALLBACK_LANGUAGE}"})
        def run_one(data_path):
            try:
                r = stt_server.transcribe(Path(data_path).read_bytes(), forced)
                return {"text": r["text"], "language": r["language"], "raw_language": r["detected_language"],
                        "raw_language_p": r["detected_language_probability"], "duration": r["duration"]}
            except stt_server.ApiError as e:
                a = decode_audio(data_path, sampling_rate=16000)
                return {"text": "", "error": f"{e.status} {e}", "language": forced, "duration": len(a) / 16000}
    else:
        kw = dict(task="transcribe", condition_on_previous_text=False, no_repeat_ngram_size=4)
        if cfg.endswith("_nots"):
            # Post-hoc variant (added after inspecting test-set errors): decode without timestamp
            # tokens, as the Transformers reference does (generation_config: return_timestamps=false).
            kw["without_timestamps"] = True
            cfg_base = cfg[:-5]
        else:
            cfg_base = cfg
        if cfg_base.endswith("_card"):
            kw.update(beam_size=1, vad_filter=False)
        else:
            kw.update(beam_size=5, vad_filter=True)
        options.update({"pipeline": "WhisperModel.transcribe", **kw, "temperature": "default (0.0..1.0 fallback)",
                        "initial_prompt": None, "language": forced or "auto (raw Whisper detection)"})
        def run_one(data_path):
            a = decode_audio(data_path, sampling_rate=16000)
            segs, info = model.transcribe(a, language=forced, **kw)
            text = " ".join(s.text.strip() for s in segs).strip()
            return {"text": text, "language": info.language, "raw_language": info.language,
                    "raw_language_p": round(info.language_probability, 4), "duration": len(a) / 16000}

load_s = time.perf_counter() - t0
after_load = P.memory_info()
inf = {"rss": 0, "commit": 0}
def mem_sampler():
    while not stop.is_set():
        m = P.memory_info()
        inf["rss"] = max(inf["rss"], m.rss); inf["commit"] = max(inf["commit"], m.private)
        time.sleep(0.05)
threading.Thread(target=mem_sampler, daemon=True).start()

# Crash safety: every finished clip is appended to <out>.partial.jsonl immediately; a re-run
# resumes after the last finished clip (the machine rebooted unexpectedly on 2026-10-14).
partial = out_path.with_suffix(".partial.jsonl")
results = []
if partial.exists():
    for line in partial.read_text(encoding="utf-8").splitlines():
        if line.strip():
            results.append(json.loads(line))
done = {r["id"] for r in results}
resumed_from = len(results)
if resumed_from:
    print(f"  {cfg} resuming after {resumed_from} finished clips", flush=True)
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(partial, "a", encoding="utf-8") as pf:
    for i, c in enumerate(clips, 1):
        if c["id"] in done:
            continue
        t = time.perf_counter()
        r = run_one(c["file"])
        r.update(id=c["id"], latency=round(time.perf_counter() - t, 3), process_start=t0_wall)
        results.append(r)
        pf.write(json.dumps(r, ensure_ascii=False) + "\n"); pf.flush(); os.fsync(pf.fileno())
        if i % 20 == 0:
            print(f"  {cfg} {i}/{len(clips)}", flush=True)
order = {c["id"]: k for k, c in enumerate(clips)}
results.sort(key=lambda r: order[r["id"]])

stop.set(); time.sleep(0.4)
mi = P.memory_info()
out = {"config": cfg, "lang_mode": lang_mode, "dataset": str(ds_path), "device": device, "n": len(results),
       "resumed_from": resumed_from,   # >0: memory/load figures cover only the last process
       "options": options, "load_s": round(load_s, 2), **state,
       "rss_after_load_mb": round(after_load.rss / 1e6), "commit_after_load_mb": round(after_load.private / 1e6),
       "peak_rss_inference_mb": round(inf["rss"] / 1e6), "peak_commit_inference_mb": round(inf["commit"] / 1e6),
       "peak_rss_process_mb": round(mi.peak_wset / 1e6), "peak_commit_process_mb": round(mi.peak_pagefile / 1e6),
       "gpu_base_mb": gpu["base_mb"], "gpu_peak_mb": gpu["peak_mb"] or None,
       "gpu_util_mean": round(sum(gpu["util_samples"]) / len(gpu["util_samples"]), 1) if gpu["util_samples"] else None,
       "gpu_util_max": max(gpu["util_samples"]) if gpu["util_samples"] else None,
       "results": results}
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
partial.unlink()   # complete result written; the partial log is no longer needed
print(f"{cfg} {lang_mode} {device} n={len(results)} load={out['load_s']}s peakRSS(inf)={out['peak_rss_inference_mb']}MB "
      f"peakCommit(proc)={out['peak_commit_process_mb']}MB gpu_peak={out['gpu_peak_mb']} util_max={out['gpu_util_max']}", flush=True)
