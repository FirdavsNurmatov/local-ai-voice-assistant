import time
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\madlad400-3b-ct2-int8"

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_DIR, local_files_only=True, use_fast=False
)
translator = ctranslate2.Translator(
    MODEL_DIR, device="cpu", compute_type="int8",
    inter_threads=1, intra_threads=4
)

tests = [
    ("uz", "en", "Salom, bugun qalaysan?"),
    ("en", "uz", "The robot can help people in a library."),
    ("ru", "en", "Сегодня робот помогает посетителям библиотеки."),
    ("en", "ru", "Hello, how are you today?"),
    ("uz", "en", "Toshkent O'zbekistonning qayerida joylashgan?"),
    ("en", "uz", "Thank you for your help."),
    ("ru", "en", "Привет! Что ты умеешь делать?"),
    ("en", "ru", "The library is open today."),
]

for source, target, text in tests:
    prompt = f"<2{target}> {text}"
    ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)

    start = time.perf_counter()
    result = translator.translate_batch(
        [tokens], max_decoding_length=128, beam_size=1
    )
    elapsed = time.perf_counter() - start

    output_tokens = result[0].hypotheses[0]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(output_ids, skip_special_tokens=True).strip()

    print(f"\n[{source} -> {target}] {text}")
    print(f"Natija: {output}")
    print(f"Vaqt: {elapsed:.2f}s")
