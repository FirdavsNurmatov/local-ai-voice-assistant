import time
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\madlad400-3b-ct2-int8"

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

text = "Salom, bugun qalaysan?"
source = "<2en> " + text

source_ids = tokenizer(
    source,
    add_special_tokens=True,
)["input_ids"]

source_tokens = tokenizer.convert_ids_to_tokens(source_ids)

print("Tarjima boshlanmoqda...")
start = time.perf_counter()

result = translator.translate_batch(
    [source_tokens],
    max_decoding_length=64,
    beam_size=1,
)

output_tokens = result[0].hypotheses[0]
output_ids = tokenizer.convert_tokens_to_ids(output_tokens)

translation = tokenizer.decode(
    output_ids,
    skip_special_tokens=True,
).strip()

print(f"\nO'zbekcha: {text}")
print(f"Inglizcha: {translation}")
print(f"Tarjima vaqti: {time.perf_counter() - start:.2f} soniya")
