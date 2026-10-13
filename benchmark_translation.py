import csv
import gc
import sys
import time
from pathlib import Path

import ctranslate2
from transformers import AutoTokenizer

ROOT = Path(r"C:\local-ai-translator")
OUT = ROOT / "benchmarks"
NLLB_DIR = ROOT / "nllb-int8"
MADLAD_DIR = ROOT / "madlad400-3b-ct2-int8"
NLLB_TOKENIZER = "facebook/nllb-200-distilled-600M"

LANG = {
    "uz": "uzn_Latn",
    "en": "eng_Latn",
    "ru": "rus_Cyrl",
}

TESTS = [
    ("uz_en_01", "uz", "en", "Salom, bugun qalaysan?"),
    ("uz_en_02", "uz", "en", "Toshkent O'zbekistonning qayerida joylashgan?"),
    ("uz_en_03", "uz", "en", "Kutubxonada odamga yordam kerak."),
    ("uz_en_04", "uz", "en", "Bugun havo juda yaxshi, sayrga chiqamizmi?"),
    ("uz_en_05", "uz", "en", "Robot kutubxonaga kelgan mehmonlarga yordam beradi."),

    ("en_uz_01", "en", "uz", "Hello, how are you today?"),
    ("en_uz_02", "en", "uz", "The robot can help people in a library."),
    ("en_uz_03", "en", "uz", "Thank you for your help."),
    ("en_uz_04", "en", "uz", "Where is Tashkent located?"),
    ("en_uz_05", "en", "uz", "The library is open today."),

    ("ru_en_01", "ru", "en", "Сегодня робот помогает посетителям библиотеки."),
    ("ru_en_02", "ru", "en", "Привет! Что ты умеешь делать?"),
    ("ru_en_03", "ru", "en", "Спасибо за помощь."),
    ("ru_en_04", "ru", "en", "Где находится Ташкент?"),
    ("ru_en_05", "ru", "en", "Сегодня погода очень хорошая, пойдем гулять?"),

    ("en_ru_01", "en", "ru", "Hello, how are you today?"),
    ("en_ru_02", "en", "ru", "The robot can help people in a library."),
    ("en_ru_03", "en", "ru", "Thank you for your help."),
    ("en_ru_04", "en", "ru", "Where is Tashkent located?"),
    ("en_ru_05", "en", "ru", "The library is open today."),
]

# Uzbek Cyrillic -> approximate Latin transliteration.
# This changes script only; it does not repair spelling or meaning.
CYR_TO_LAT = {
    "а":"a", "б":"b", "в":"v", "г":"g", "д":"d",
    "е":"e", "ё":"yo", "ж":"j", "з":"z", "и":"i",
    "й":"y", "к":"k", "л":"l", "м":"m", "н":"n",
    "о":"o", "п":"p", "р":"r", "с":"s", "т":"t",
    "у":"u", "ф":"f", "х":"x", "ц":"ts", "ч":"ch",
    "ш":"sh", "щ":"shch", "ъ":"'", "ы":"i", "ь":"",
    "э":"e", "ю":"yu", "я":"ya", "қ":"q", "ғ":"g'",
    "ҳ":"h", "ў":"o'",
}

def to_latin(text):
    result = []
    for char in text:
        lower = char.lower()
        if lower in CYR_TO_LAT:
            value = CYR_TO_LAT[lower]
            if char.isupper() and value:
                value = value[0].upper() + value[1:]
            result.append(value)
        else:
            result.append(char)
    return "".join(result)

def translate_nllb(tokenizer, translator, text, source, target):
    tokenizer.src_lang = LANG[source]
    ids = tokenizer(text, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)

    result = translator.translate_batch(
        [tokens],
        target_prefix=[[LANG[target]]],
        max_decoding_length=128,
        beam_size=1,
    )
    output_tokens = result[0].hypotheses[0][1:]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    return tokenizer.decode(output_ids, skip_special_tokens=True).strip()

def translate_madlad(tokenizer, translator, text, source, target):
    prompt = f"<2{target}> {text}"
    ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)

    result = translator.translate_batch(
        [tokens],
        max_decoding_length=128,
        beam_size=1,
    )
    output_tokens = result[0].hypotheses[0]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    return tokenizer.decode(output_ids, skip_special_tokens=True).strip()

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("nllb", "madlad"):
        print("Foydalanish: python benchmark_translation.py nllb")
        print("Yoki:       python benchmark_translation.py madlad")
        return

    model = sys.argv[1]
    model_dir = NLLB_DIR if model == "nllb" else MADLAD_DIR
    output_csv = OUT / f"{model}_results.csv"

    if not (model_dir / "model.bin").exists():
        raise FileNotFoundError(f"Model topilmadi: {model_dir / 'model.bin'}")

    print(f"{model.upper()} tokenizer yuklanmoqda...")
    if model == "nllb":
        tokenizer = AutoTokenizer.from_pretrained(NLLB_TOKENIZER)
    else:
        tokenizer = AutoTokenizer.from_pretrained(
            str(MADLAD_DIR), local_files_only=True, use_fast=False
        )

    print(f"{model.upper()} INT8 modeli yuklanmoqda...")
    translator = ctranslate2.Translator(
        str(model_dir),
        device="cpu",
        compute_type="int8",
        inter_threads=1,
        intra_threads=4,
    )

    rows = []
    for index, (test_id, source, target, text) in enumerate(TESTS, start=1):
        start = time.perf_counter()
        try:
            if model == "nllb":
                raw = translate_nllb(
                    tokenizer, translator, text, source, target
                )
            else:
                raw = translate_madlad(
                    tokenizer, translator, text, source, target
                )
            elapsed = time.perf_counter() - start
            latin = to_latin(raw) if model == "madlad" and target == "uz" else raw
            error = ""
        except Exception as exc:
            raw = ""
            latin = ""
            elapsed = time.perf_counter() - start
            error = repr(exc)

        rows.append({
            "test_id": test_id,
            "model": model,
            "source_lang": source,
            "target_lang": target,
            "input_text": text,
            "output_raw": raw,
            "output_latin": latin,
            "latency_seconds": round(elapsed, 3),
            "error": error,
        })
        print(f"\n[{index}/{len(TESTS)}] {source}->{target}: {text}")
        print(f"Natija: {latin}")
        print(f"Vaqt: {elapsed:.2f}s")
        if error:
            print(f"XATO: {error}")

    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    valid = [r for r in rows if not r["error"]]
    times = sorted(r["latency_seconds"] for r in valid)
    avg = sum(times) / len(times) if times else 0
    median = (
        times[len(times)//2] if len(times) % 2
        else (times[len(times)//2-1] + times[len(times)//2]) / 2
    ) if times else 0

    print("\n--- YAKUN ---")
    print(f"Model: {model}")
    print(f"Muvaffaqiyatli: {len(valid)}/{len(rows)}")
    print(f"O'rtacha vaqt: {avg:.3f}s")
    print(f"Median vaqt: {median:.3f}s")
    print(f"CSV: {output_csv}")

    del translator
    del tokenizer
    gc.collect()

    nllb_csv = OUT / "nllb_results.csv"
    madlad_csv = OUT / "madlad_results.csv"
    if nllb_csv.exists() and madlad_csv.exists():
        with nllb_csv.open(encoding="utf-8-sig", newline="") as f:
            nllb_rows = {r["test_id"]: r for r in csv.DictReader(f)}
        with madlad_csv.open(encoding="utf-8-sig", newline="") as f:
            madlad_rows = {r["test_id"]: r for r in csv.DictReader(f)}

        comparison_csv = OUT / "comparison.csv"
        with comparison_csv.open("w", encoding="utf-8-sig", newline="") as f:
            fields = [
                "test_id", "source_lang", "target_lang", "input_text",
                "nllb_output", "nllb_seconds",
                "madlad_raw", "madlad_latin", "madlad_seconds",
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for test_id, _, _, _ in TESTS:
                n = nllb_rows.get(test_id, {})
                m = madlad_rows.get(test_id, {})
                writer.writerow({
                    "test_id": test_id,
                    "source_lang": n.get("source_lang", m.get("source_lang", "")),
                    "target_lang": n.get("target_lang", m.get("target_lang", "")),
                    "input_text": n.get("input_text", m.get("input_text", "")),
                    "nllb_output": n.get("output_raw", ""),
                    "nllb_seconds": n.get("latency_seconds", ""),
                    "madlad_raw": m.get("output_raw", ""),
                    "madlad_latin": m.get("output_latin", ""),
                    "madlad_seconds": m.get("latency_seconds", ""),
                })
        print(f"Taqqoslash CSV: {comparison_csv}")

if __name__ == "__main__":
    main()
