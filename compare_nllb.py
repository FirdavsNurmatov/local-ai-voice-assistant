import time
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\nllb-int8"
TOKENIZER_ID = "facebook/nllb-200-distilled-600M"

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)
translator = ctranslate2.Translator(
    MODEL_DIR, device="cpu", compute_type="int8",
    inter_threads=1, intra_threads=4
)

tests = [
    ("Hello, how are you today?", "eng_Latn", "uzn_Latn"),
    ("The robot can help people in a library.", "eng_Latn", "uzn_Latn"),
    ("Thank you for your help.", "eng_Latn", "uzn_Latn"),
    ("Where is Tashkent located?", "eng_Latn", "uzn_Latn"),
]

for text, source, target in tests:
    tokenizer.src_lang = source
    ids = tokenizer(text, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)

    start = time.perf_counter()
    result = translator.translate_batch(
        [tokens], target_prefix=[[target]],
        max_decoding_length=128, beam_size=1
    )
    elapsed = time.perf_counter() - start

    output_tokens = result[0].hypotheses[0][1:]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(output_ids, skip_special_tokens=True).strip()

    print(f"\nEN: {text}")
    print(f"UZ: {output}")
    print(f"Time: {elapsed:.2f}s")
