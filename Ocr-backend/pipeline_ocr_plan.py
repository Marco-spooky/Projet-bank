import easyocr
import cv2
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import numpy as np
import ollama
import json
import re

# ==============================================================================
# CONFIGURATION
# ==============================================================================
IMAGE_PATH = "local.jpeg"  # <--- Remplace par ton image de plan
LANGUAGE = 'fr'            # Langue pour EasyOCR

# Modèle TrOCR pour le manuscrit (Microsoft)
TROC_MODEL_NAME = "microsoft/trocr-base-handwritten"

# ==============================================================================
# STRUCTURATION AVEC OLLAMA/MISTRAL (Intégré depuis ton serveur.py)
# ==============================================================================
def structurer_plan_avec_mistral(fragments):
    """
    Prend les fragments de texte lus par TrOCR et utilise Mistral (via Ollama)
    pour reconstruire le JSON du plan de localisation.
    """
    text_block = "\n".join(fragments)

    prompt = f"""Tu es un assistant bancaire expert.
Voici des fragments de texte extraits par OCR d'un plan de localisation manuscrit.
Le texte peut être désordonné ou contenir des erreurs.

TEXTE BRUT EXTRAIT:
{text_block}

INSTRUCTIONS:
- Analyse ces fragments et extrait les informations pour remplir le plan de localisation.
- Si une information est absente ou illisible, mets une chaîne vide "".
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après, sans balises markdown.

FORMAT JSON ATTENDU:
{{
  "ville": "",
  "quartier": "",
  "tel1": "",
  "tel2": "",
  "email": "",
  "datePlan": "",
  "contact1Nom": "",
  "contact1Tel1": "",
  "contact1Tel2": "",
  "contact2Nom": "",
  "contact2Tel1": "",
  "contact2Tel2": ""
}}"""

    try:
        print("\n[Mistral] Structuration du JSON en cours...")
        response = ollama.chat(
            model="mistral",
            messages=[{"role": "user", "content": prompt}]
        )
        contenu = response['message']['content'].strip()

        # Nettoyage des balises markdown si Mistral en ajoute
        contenu = re.sub(r'```json\s*', '', contenu)
        contenu = re.sub(r'```\s*', '', contenu)
        contenu = contenu.strip()

        return json.loads(contenu)
    except Exception as e:
        print(f"❌ Erreur Mistral/Ollama : {e}")
        return {
            "ville": "", "quartier": "", "tel1": "", "tel2": "",
            "email": "", "datePlan": "", "contact1Nom": "",
            "contact1Tel1": "", "contact1Tel2": "", "contact2Nom": "",
            "contact2Tel1": "", "contact2Tel2": ""
        }

# ==============================================================================
# PIPELINE PRINCIPAL
# ==============================================================================
def run_pipeline(image_path):
    # 1. Initialisation des modèles
    print("⏳ Chargement des modèles (EasyOCR et TrOCR)...")
    reader = easyocr.Reader([LANGUAGE], gpu=False) # Détecteur

    processor = TrOCRProcessor.from_pretrained(TROC_MODEL_NAME)
    model = VisionEncoderDecoderModel.from_pretrained(TROC_MODEL_NAME)

    # 2. Détection des zones de texte avec EasyOCR
    print(f"🔍 Analyse de l'image : {image_path}...")
    detections = reader.readtext(image_path)

    if not detections:
        print("❌ Aucun texte détecté sur l'image.")
        return None

    print(f"✅ {len(detections)} zones de texte trouvées. Lecture manuscrite via TrOCR...")

    # Charger l'image avec OpenCV pour le découpage
    img = cv2.imread(image_path)
    fragments = []

    # 3. Lecture de chaque zone avec TrOCR
    for i, (bbox, text, prob) in enumerate(detections):
        # Extraction des coordonnées de la boîte
        (tl, tr, br, bl) = bbox
        x_min, y_min = int(tl[0]), int(tl[1])
        x_max, y_max = int(br[0]), int(br[1])

        # Ajout d'une petite marge pour aider TrOCR
        margin = 5
        crop = img[max(0, y_min-margin):y_max+margin, max(0, x_min-margin):x_max+margin]

        if crop.size == 0:
            continue

        # Conversion BGR -> RGB pour PIL
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(crop_rgb)

        # Préparation et génération TrOCR
        pixel_values = processor(images=pil_img, return_tensors="pt").pixel_values
        generated_ids = model.generate(pixel_values)
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        fragments.append(generated_text)
        print(f"  Ligne {i+1}: {generated_text}")

    # 4. Structuration finale avec Mistral via Ollama
    json_final = structurer_plan_avec_mistral(fragments)
    return json_final

# ==============================================================================
# LANCEMENT
# ==============================================================================
if __name__ == "__main__":
    try:
        resultat_json = run_pipeline(IMAGE_PATH)
        if resultat_json:
            print("\n" + "="*50)
            print("🚀 RÉSULTAT FINAL STRUCTURÉ (JSON) :")
            print(json.dumps(resultat_json, indent=2, ensure_ascii=False))
            print("="*50)
    except Exception as e:
        print(f"❌ Erreur critique : {e}")
