r"""Uzbek TTS speed benchmark: female voice (VITS ONNX, 8766 code) vs male voice (Uzbek_TTS, 8770 settings).

usage (from C:\local-ai-translator):
  stt-tts-uz\.venv-tts\Scripts\python.exe stt-eval\scripts\tts_uz_benchmark.py female
  Uzbek_TTS-test\.venv\Scripts\python.exe   stt-eval\scripts\tts_uz_benchmark.py male cuda
  Uzbek_TTS-test\.venv\Scripts\python.exe   stt-eval\scripts\tts_uz_benchmark.py male cpu
Writes stt-eval\tts_uz\<voice>[_<device>].json (and WAVs, not tracked by git). One warm-up sentence is not counted.
"""
import contextlib, io, json, os, platform, sys, time, wave
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
OUT = R / "stt-eval" / "tts_uz"
voice = sys.argv[1]
device = sys.argv[2] if len(sys.argv) > 2 else "cpu"
SENTENCES = [
    "Assalomu alaykum! Men OrionStar robotining mahalliy ovoz yordamchisiman. Sizga qanday yordam bera olaman?",
    "Oʻzbekiston poytaxti Toshkent shahridir.",
    "Haftada etti kun bor. Yana biror narsani bilishingiz kerakmi?",
    "Kutubxona ikkinchi qavatda joylashgan, liftdan chiqib chapga buriling.",
]
WARMUP = "Salom."

if voice == "female":
    sys.path.insert(0, str(R))
    os.chdir(R)
    with contextlib.redirect_stdout(io.StringIO()):
        import tts_onnx_server as srv                       # loads the ONNX session at import, server not started

    def synth(text):
        with contextlib.redirect_stdout(io.StringIO()):
            data = srv.make_audio(text)
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / w.getframerate(), data, None
    settings = {"model": srv.MODEL_PATH.name, "provider": srv.SESSION.get_providers()}
    load_s = None
else:
    import torch
    sys.path.insert(0, str(R))
    started = time.perf_counter()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import uz_male_tts_server as srv                        # chdir + sys.path to Uzbek_TTS-test; server not started
    from hydra.utils import get_class
    from omegaconf import OmegaConf
    from tts import TTS
    cfg = OmegaConf.load("config/UZTTS_conf.yaml")
    with contextlib.redirect_stdout(io.StringIO()):
        model = TTS(ref_audio_path=str(srv.REF_AUDIO), ref_text=srv.REF_TEXT, model_cfg=cfg,
                    model_cls=get_class(f"uz_tts.model.{cfg.model.backbone}"), vocab="config/uz_vocab.txt",
                    ckpt_path=str(srv.CKPT), device=device, preload_models=True, speed=srv.SPEED, nfe_step=srv.NFE_STEP)
    srv.tts = model
    srv.state.update(ready=True, sample_rate=model.target_sample_rate)
    load_s = round(time.perf_counter() - started, 1)
    transformer = model.model.transformer
    timer = {"s": 0.0, "calls": 0}
    original = transformer.forward

    def timed(*a, **k):
        if device == "cuda": torch.cuda.synchronize()
        t = time.perf_counter(); r = original(*a, **k)
        if device == "cuda": torch.cuda.synchronize()
        timer["s"] += time.perf_counter() - t; timer["calls"] += 1
        return r
    transformer.forward = timed

    def synth(text):
        timer.update(s=0.0, calls=0)
        data = srv.make_audio(text)                          # same code path as the service (sentence chunks)
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / w.getframerate(), data, {"transformer_s": round(timer["s"], 2), "transformer_calls": timer["calls"]}
    settings = {"model": srv.CKPT.name, "ref_audio": srv.REF_AUDIO.name, "nfe_step": srv.NFE_STEP, "speed": srv.SPEED,
                "device": torch.cuda.get_device_name(0) if device == "cuda" else platform.processor(),
                "torch_threads": torch.get_num_threads(), "torch": torch.__version__}

synth(WARMUP)
rows = []
name = voice if voice == "female" else f"male_{device}"
OUT.mkdir(parents=True, exist_ok=True)
for i, text in enumerate(SENTENCES):
    t = time.perf_counter()
    audio_s, data, extra = synth(text)
    gen_s = time.perf_counter() - t
    (OUT / f"{name}_{i}.wav").write_bytes(data)
    rows.append({"text": text, "chars": len(text), "audio_s": round(audio_s, 2), "generation_s": round(gen_s, 2),
                 "real_time_factor": round(gen_s / audio_s, 2), **(extra or {})})
    print(rows[-1], flush=True)
result = {"voice": voice, "device": device, "date": time.strftime("%Y-%m-%d"), "load_s": load_s, "settings": settings,
          "median_generation_s": float(np.median([r["generation_s"] for r in rows])),
          "median_real_time_factor": float(np.median([r["real_time_factor"] for r in rows])), "sentences": rows}
if voice == "male" and device == "cuda":
    import torch
    result["vram_peak_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
(OUT / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "sentences"}, ensure_ascii=False))
