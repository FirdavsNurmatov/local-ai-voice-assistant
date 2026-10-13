
import time
import requests
import torch
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\nllb-int8"
TOKENIZER_ID = "facebook/nllb-200-distilled-600M"
OLLAMA_URL = "http://localhost:11434/api/chat"
QWEN_MODEL = "qwen3:1.7b"

LANGUAGES = {
    "uz": "uzn_Latn",
    "ru": "rus_Cyrl",
    "en": "eng_Latn",
}

UZ_WORDS = {
    "salom", "assalomu", "alaykum", "qayerda", "qanday",
    "nima", "uchun", "rahmat", "iltimos", "bugun",
    "yaxshi", "yomon", "men", "siz", "menga", "kerak",
    "mumkin", "robot", "kutubxona", "joylashgan", "toshkent",
    "o'zbekiston", "ozbekiston", "bilan", "qil", "qiladi",
}

def detect_language(text):
    lower = text.lower()

    if any("\u0400" <= c <= "\u04ff" for c in text):
        return "ru"

    if any(mark in lower for mark in ("o‘", "o'", "g‘", "g'", "ʻ")):
        return "uz"

    words = set(lower.replace("?", "").replace("!", "")
                    .replace(",", "").replace(".", "").split())

    if words & UZ_WORDS:
        return "uz"

    return "en"


print("INT8 tarjimon yuklanmoqda...")
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)
translator = ctranslate2.Translator(
    MODEL_DIR,
    device="cpu",
    compute_type="int8",
)
print("INT8 tarjimon tayyor.")

def translate(text, source, target):
    if source == target or not text:
        return text, 0.0

    tokenizer.src_lang = source
    encoded = tokenizer(text, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(encoded)

    start = time.perf_counter()
    result = translator.translate_batch(
        [tokens],
        target_prefix=[[target]],
        max_decoding_length=128,
        beam_size=1,
    )

    output_tokens = result[0].hypotheses[0][1:]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(output_ids, skip_special_tokens=True).strip()

    return output, time.perf_counter() - start


while True:
    try:
        text = input("\nSiz (exit — chiqish): ").strip()

        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue

        total_start = time.perf_counter()
        lang = detect_language(text)
        print(f"[Til: {lang}]")

        english, input_time = translate(
            text, LANGUAGES[lang], "eng_Latn"
        )

        qwen_start = time.perf_counter()
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": QWEN_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful, friendly assistant. "
                            "Answer in English in 1-3 concise sentences. "
                            "Do not include reasoning or thinking."
                        ),
                    },
                    {"role": "user", "content": english},
                ],
                "stream": False,
                "think": False,
                "keep_alive": "10m",
                "options": {
                    "num_ctx": 2048,
                    "num_predict": 100,
                    "temperature": 0.4,
                },
            },
            timeout=180,
        )
        response.raise_for_status()
        answer_en = response.json()["message"]["content"].strip()
        qwen_time = time.perf_counter() - qwen_start

        answer, output_time = translate(
            answer_en, "eng_Latn", LANGUAGES[lang]
        )

        print(f"[Kirish inglizcha: {english}]")
        print(f"[Qwen inglizcha: {answer_en}]")
        print(f"\nAssistant: {answer}")
        print(f"[Kirish tarjimasi: {input_time:.2f}s]")
        print(f"[Qwen: {qwen_time:.2f}s]")
        print(f"[Chiqish tarjimasi: {output_time:.2f}s]")
        print(f"[Jami: {time.perf_counter() - total_start:.2f}s]")

    except KeyboardInterrupt:
        print("\nTo‘xtatildi.")
        break
    except requests.RequestException as error:
        print(f"\nOllama bilan ulanish xatosi: {error}")
    except Exception as error:
        print(f"\nXato: {error}")
