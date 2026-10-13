
import time
import requests
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL = "facebook/nllb-200-distilled-600M"
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
    "mumkin", "robot", "kutubxona", "joylashgan"
}

def detect_language(text):
    lower = text.lower()
    if any("\u0400" <= c <= "\u04ff" for c in text):
        return "ru"
    words = set(lower.replace("?", "").replace("!", "").replace(",", "").split())
    if any(ch in lower for ch in ("o‘", "o'", "g‘", "g'", "ʻ")):
        return "uz"
    if words & UZ_WORDS:
        return "uz"
    return "en"

print("Tarjimon yuklanmoqda...")
tokenizer = AutoTokenizer.from_pretrained(MODEL)
translator = AutoModelForSeq2SeqLM.from_pretrained(MODEL)
translator.eval()
print("Tayyor. Chiqish uchun exit yozing.")

def translate(text, source, target):
    if source == target or not text:
        return text

    tokenizer.src_lang = source
    inputs = tokenizer(text, return_tensors="pt", truncation=True)

    with torch.inference_mode():
        output = translator.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(target),
            max_new_tokens=128,
            num_beams=1,
        )

    return tokenizer.batch_decode(output, skip_special_tokens=True)[0]

while True:
    try:
        text = input("\nSiz: ").strip()
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue

        total_start = time.time()
        lang = detect_language(text)
        print(f"[Aniqlangan til: {lang}]")

        t0 = time.time()
        english = translate(text, LANGUAGES[lang], "eng_Latn")
        translation_in_time = time.time() - t0

        t0 = time.time()
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
                "options": {"num_ctx": 2048, "temperature": 0.4},
            },
            timeout=180,
        )
        response.raise_for_status()
        answer_en = response.json()["message"]["content"].strip()
        qwen_time = time.time() - t0

        t0 = time.time()
        answer = translate(answer_en, "eng_Latn", LANGUAGES[lang])
        translation_out_time = time.time() - t0

        print(f"\nAssistant: {answer}")
        print(f"[Kirish tarjimasi: {translation_in_time:.2f}s]")
        print(f"[Qwen: {qwen_time:.2f}s]")
        print(f"[Chiqish tarjimasi: {translation_out_time:.2f}s]")
        print(f"[Jami: {time.time() - total_start:.2f}s]")

    except KeyboardInterrupt:
        print("\nTo‘xtatildi.")
        break
    except Exception as e:
        print(f"\nXato: {e}")
