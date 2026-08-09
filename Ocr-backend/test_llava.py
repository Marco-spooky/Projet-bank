import ollama
import base64
import json

# ============================================================
# CONFIGURATION DU TEST
# ============================================================
IMAGE_PATH = "local.jpeg"  # <--- ASSURE-TOI QUE CE FICHIER EXISTE DANS LE DOSSIER
MODEL_NAME = "llava"

def image_to_base64(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def test_llava_vision():
    print(f"🚀 Démarrage du test de vision LLaVA avec l'image : {IMAGE_PATH}")

    try:
        # 1. Encodage de l'image
        image_b64 = image_to_base64(IMAGE_PATH)

        # 2. Prompt ultra-précis
        prompt = """You are a banking expert specialized in reading handwritten location plans.
Analyze this image carefully. I need you to extract the following specific information:
- City (Ville)
- Neighborhood (Quartier)
- Phone 1 (Tel 1)
- Phone 2 (Tel 2)
- Email
- Date of the plan (Date du plan)
- Contact 1 Name (Nom Contact 1)
- Contact 1 Phone 1 (Tel 1 Contact 1)
- Contact 1 Phone 2 (Tel 2 Contact 1)
- Contact 2 Name (Nom Contact 2)
- Contact 2 Phone 1 (Tel 1 Contact 2)
- Contact 2 Phone 2 (Tel 2 Contact 2)

If a field is empty or unreadable, write 'NOT FOUND'.
Please provide the results as a clear list. Do not say 'I cannot see the image', just analyze it."""

        # 3. Appel à Ollama
        print("⏳ LLaVA analyse l'image... (cela peut prendre quelques secondes)")
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }]
        )

        print("\n" + "="*50)
        print("✅ RÉPONSE DE LLaVA :")
        print("="*50)
        print(response['message']['content'])
        print("="*50)

    except FileNotFoundError:
        print(f"❌ Erreur : Le fichier {IMAGE_PATH} est introuvable. Place l'image dans le dossier ou change IMAGE_PATH.")
    except Exception as e:
        print(f"❌ Erreur critique lors du test : {e}")

if __name__ == "__main__":
    test_llava_vision()