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
    "<2uz> Hello, how are you today?",
    "<2uz> The robot can help people in a library.",
    "<2uz> Thank you for your help.",
    "<2uz> Where is Tashkent located?",
]

for prompt in tests:
    ids = tokenizer(prompt, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(ids)
    result = translator.translate_batch(
        [tokens], max_decoding_length=100, beam_size=1
    )
    output = tokenizer.decode(
        tokenizer.convert_tokens_to_ids(result[0].hypotheses[0]),
        skip_special_tokens=True,
    ).strip()
    print(f"\nKirish: {prompt}")
    print(f"Chiqish: {output}")
