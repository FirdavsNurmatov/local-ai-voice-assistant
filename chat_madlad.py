import time
import re
import requests
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\madlad400-3b-ct2-int8"
OLLAMA_URL = "http://localhost:11434/api/chat"
QWEN_MODEL = "qwen3:1.7b"

LANGUAGES = {"uz": "uz", "ru": "ru", "en": "en"}

UZ_WORDS = {
    "salom", "assalomu", "alaykum", "qayerda", "qanday",
    "qalaysan", "qandaysan", "nima", "uchun", "rahmat",
    "iltimos", "bugun", "yaxshi", "yomon", "men", "siz",
    "menga", "kerak", "mumkin", "robot", "kutubxona",
    "kutubxonada", "kutubxonaga", "joylashgan", "toshkent",
    "o'zbekiston", "ozbekiston", "bilan", "qil", "qiladi",
    "beradi", "odamlar", "mehmonlar", "chiqamizmi",
    "yordam", "qilaman", "qilasiz", "qilasan"
}

CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    "ў": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h",
}


def uzbek_cyrillic_to_latin(text):
    result = []

    for char in text:
        lower = char.lower()
        converted = CYRILLIC_TO_LATIN.get(lower, char)

        if char.isupper() and converted:
            converted = converted[0].upper() + converted[1:]

        result.append(converted)

    text = "".join(result)

    # Common MADLAD vocabulary correction.
    # Transliteration alone cannot fix incorrect word choices.
    text = re.sub(
        r"\bkitobxona",
        "kutubxona",
        text,
        flags=re.IGNORECASE,
    )

    return text

def detect_language(text):
    lower = text.lower()

    # Cyrillic text is treated as Russian for this initial version.
    if any("\u0400" <= c <= "\u04ff" for c in text):
        return "ru"

    normalized = (
        lower.replace("'", "")
        .replace("’", "")
        .replace("ʻ", "")
        .replace("ʼ", "")
    )
    words = set(
        normalized.replace("?", " ")
        .replace("!", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
        .replace(";", " ")
        .split()
    )

    if words & UZ_WORDS:
        return "uz"

    # Common Uzbek-specific Latin letters.
    if any(char in lower for char in ("oʻ", "gʻ", "ў", "қ", "ғ")):
        return "uz"

    return "en"


print("MADLAD tokenizer yuklanmoqda...")
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_DIR,
    local_files_only=True,
    use_fast=False,
)

print("MADLAD INT8 modeli yuklanmoqda...")
translator = ctranslate2.Translator(
    MODEL_DIR,
    device="cpu",
    compute_type="int8",
    inter_threads=1,
    intra_threads=4,
)
print("MADLAD tarjimon tayyor.")


def translate(text, source, target):
    if source == target or not text.strip():
        return text, 0.0

    prompt = f"<2{target}> {text}"
    encoded = tokenizer(
        prompt, add_special_tokens=True
    )["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(encoded)

    start = time.perf_counter()
    result = translator.translate_batch(
        [tokens],
        max_decoding_length=128,
        beam_size=1,
    )

    output_tokens = result[0].hypotheses[0]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(
        output_ids, skip_special_tokens=True
    ).strip()

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
        print(f"[Aniqlangan til: {lang}]")

        english, input_time = translate(text, lang, "en")

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

        answer, output_time = translate(answer_en, "en", lang)

        if lang == "uz":
            answer = uzbek_cyrillic_to_latin(answer)

        print(f"[Inglizcha so'rov: {english}]")
        print(f"[Qwen javobi: {answer_en}]")
        print(f"\nAssistant: {answer}")
        print(f"[Kirish tarjimasi: {input_time:.2f}s]")
        print(f"[Qwen: {qwen_time:.2f}s]")
        print(f"[Chiqish tarjimasi: {output_time:.2f}s]")
        print(f"[Jami: {time.perf_counter() - total_start:.2f}s]")

    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
        break
    except requests.RequestException as error:
        print(f"\nOllama bilan ulanish xatosi: {error}")
    except Exception as error:
        print(f"\nXato: {type(error).__name__}: {error}")
