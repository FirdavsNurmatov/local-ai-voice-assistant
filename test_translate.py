import time
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL = "facebook/nllb-200-distilled-600M"

print("Tarjimon modeli yuklanmoqda...")
print("Birinchi marta model fayllari internetdan yuklanadi.")

tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL)
model.eval()

def translate(text, source, target):
    tokenizer.src_lang = source
    inputs = tokenizer(text, return_tensors="pt", truncation=True)

    start = time.time()
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(target),
            max_new_tokens=128,
            num_beams=1
        )

    result = tokenizer.batch_decode(output, skip_special_tokens=True)[0]
    print(f"\nAsl matn: {text}")
    print(f"Tarjima:  {result}")
    print(f"Vaqt:     {time.time() - start:.2f} soniya")

translate("Bugun havo juda yaxshi, sayrga chiqamizmi?", "uzn_Latn", "eng_Latn")
translate("The robot can help people in a library.", "eng_Latn", "uzn_Latn")
translate("Сегодня робот помогает посетителям библиотеки.", "rus_Cyrl", "eng_Latn")
