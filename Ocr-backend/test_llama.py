"""
Script de test — Extraction de données CNI via Groq Vision API
----------------------------------------------------------------
Usage :
    export GROQ_API_KEY="ta_cle_api"
    python test_cni_groq.py chemin/vers/cni.jpg

Nécessite : pip install groq
"""

import base64
import json
import os
import sys
import time

from groq import Groq

# Modèle vision actuellement supporté par Groq (juillet 2026).
# Les anciens modèles Llama vision (llama-3.2-90b-vision-preview,
# llama-4-scout-17b-16e-instruct) sont dépréciés — remplace ici si
# Groq propose un modèle plus récent au moment où tu testes.
MODEL = "qwen/qwen3.6-27b"

# Champs qu'on veut extraire d'une CNI camerounaise/française — adapte
# la liste selon le format exact de tes documents.
PROMPT = """Tu es un système d'extraction de données pour des cartes nationales d'identité (CNI) camerounaises.

Tu reçois deux images : le RECTO (première image) et le VERSO (deuxième image) de la même carte. Certains champs ne sont présents que sur une seule des deux faces (par exemple le nom et le prénom sont typiquement sur le recto, tandis que le numéro de CNI, les dates de délivrance/expiration ou l'autorité de délivrance peuvent être sur le verso selon le modèle de carte).

Analyse les DEUX images ensemble et combine les informations trouvées sur chacune pour produire un JSON unique et complet, sans aucun texte avant ou après :

{
  "nom": "",
  "prenom": "",
  "date_naissance": "",
  "lieu_naissance": "",
  "sexe": "",
  "numero_cni": "",
  "date_delivrance": "",
  "date_expiration": "",
  "autorite_delivrance": ""
}

Règles :
- Ne cherche PAS activement un champ que tu ne vois sur AUCUNE des deux images : mets directement "" sans essayer de deviner ou d'extrapoler.
- Si un champ est illisible sur les deux faces, mets aussi "".
- Ne devine jamais une valeur que tu ne peux pas lire clairement.
- Respecte les accents et la casse tels qu'affichés sur le document.
- Réponds uniquement avec le JSON, sans balises markdown ni commentaire.
"""


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_cni(recto_path: str, verso_path: str, api_key: str) -> dict:
    client = Groq(api_key=api_key)
    b64_recto = encode_image(recto_path)
    b64_verso = encode_image(verso_path)

    start = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_recto}"
                        },
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_verso}"
                        },
                    },
                ],
            }
        ],
        temperature=0.0,  # déterministe, on veut de l'extraction pas de la créativité
        max_tokens=2048,  # augmenté : marge de sécurité même sans réflexion
        reasoning_effort="none",  # désactive le mode réflexion de Qwen 3.6 — sinon <think>...</think> mange le budget de tokens et coupe le JSON final
        response_format={"type": "json_object"},  # force l'API à garantir un JSON valide en sortie, au lieu de compter uniquement sur le prompt
    )
    elapsed = time.time() - start

    raw_content = response.choices[0].message.content.strip()

    # Nettoyage au cas où le modèle encapsule quand même le JSON dans des ```
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("`")
        if raw_content.lower().startswith("json"):
            raw_content = raw_content[4:].strip()

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        print("⚠️  Le modèle n'a pas renvoyé un JSON valide. Réponse brute :")
        print(raw_content)
        return {}

    data["_meta"] = {
        "model": MODEL,
        "temps_traitement_s": round(elapsed, 2),
        "tokens_utilises": response.usage.total_tokens if response.usage else None,
    }
    return data


def main():
    if len(sys.argv) < 2:
        print("Usage : python test_cni_groq.py chemin/vers/cni.jpg")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Fichier introuvable : {image_path}")
        sys.exit(1)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Erreur : variable d'environnement GROQ_API_KEY non définie.")
        print('Fais : export GROQ_API_KEY="ta_cle_api"')
        sys.exit(1)

    print(f"Extraction en cours sur : {image_path}")
    result = extract_cni(image_path, api_key)

    print("\n--- Résultat ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()