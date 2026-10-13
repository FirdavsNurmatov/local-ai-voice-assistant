import time
import ctranslate2
from transformers import AutoTokenizer

MODEL_DIR = r"C:\local-ai-translator\nllb-int8"
TOKENIZER_ID = "facebook/nllb-200-distilled-600M"

print("INT8 tarjimon yuklanmoqda...")
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)
translator = ctranslate2.Translator(MODEL_DIR, device="cpu", compute_type="int8")
print("Tayyor!")

def translate(text, source, target):
    tokenizer.src_lang = source
    encoded = tokenizer(text, add_special_tokens=True)["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(encoded)

    start = time.time()
    result = translator.translate_batch(
        [tokens],
        target_prefix=[[target]]
    )
    output_tokens = result[0].hypotheses[0][1:]
    output_ids = tokenizer.convert_tokens_to_ids(output_tokens)
    output = tokenizer.decode(output_ids, skip_special_tokens=True)

    print(f"\nAsl matn: {text}")
    print(f"Tarjima: {output}")
    print(f"Vaqt: {time.time() - start:.2f} soniya")

translate("Bugun havo juda yaxshi, sayrga chiqamizmi?", "uzn_Latn", "eng_Latn")
translate("The robot can help people in a library.", "eng_Latn", "uzn_Latn")
translate("Сегодня робот помогает посетителям библиотеки.", "rus_Cyrl", "eng_Latn")