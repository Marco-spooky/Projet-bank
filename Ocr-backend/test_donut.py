import torch
from PIL import Image
from transformers import DonutProcessor, VisionEncoderDecoderModel
import re

def extract_info_donut(image_path):
    print("Chargement du modèle Donut... (Ceci peut prendre du temps la première fois)")

    # 1. Chargement du processeur et du modèle
    processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
    model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base")

    # On passe le modèle en mode évaluation
    model.eval()

    # 2. Préparation de l'image
    image = Image.open(image_path).convert("RGB")
    pixel_values = processor(image, return_tensors="pt").pixel_values

    # 3. Préparation du prompt
    task_prompt = "<s_cord-v2>"
    decoder_input_ids = processor.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt").input_ids

    print("Analyse de l'image en cours...")

    # 4. Génération du texte
    with torch.no_grad():
        outputs = model.generate(
            pixel_values,
            decoder_input_ids=decoder_input_ids,
            max_length=512,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
            use_cache=True,
            bad_words_ids=[[processor.tokenizer.unk_token_id]],
            return_dict_in_generate=True,
        )

    # 5. Décodage du résultat
    sequence = processor.batch_decode(outputs.sequences)[0]

    # Nettoyage du résultat
    sequence = sequence.replace(processor.tokenizer.eos_token, "").replace(processor.tokenizer.pad_token, "")
    sequence = re.sub(r"<.*?>", " ", sequence).strip()

    return sequence

if __name__ == "__main__":
    # IMPORTANT: Remplace 'local.jpeg' par le chemin réel de ton image si nécessaire
    image_path = "local.jpeg"

    try:
        resultat = extract_info_donut(image_path)
        print("\n--- Résultat de l'extraction Donut ---")
        print(resultat)
        print("--------------------------------------")
    except Exception as e:
        print(f"Erreur lors de l'extraction : {e}")
