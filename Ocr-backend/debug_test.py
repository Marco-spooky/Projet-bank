# ============================================================
# Script de debug — voir ce qu'EasyOCR lit exactement
# Usage: python debug_test.py image_cni.jpg
# ============================================================
import sys
import easyocr
import cv2
import numpy as np

print("⏳ Chargement EasyOCR...")
reader = easyocr.Reader(['fr', 'en'], gpu=False)
print("✅ EasyOCR prêt !\n")

def tester_image(chemin):
    # Lire l'image
    img = cv2.imread(chemin)
    if img is None:
        print(f"❌ Impossible de lire : {chemin}")
        return

    print(f"📄 Image : {chemin}")
    print(f"📐 Taille originale : {img.shape[1]}x{img.shape[0]} pixels\n")

    # ---- TEST 1 : Image originale ----
    print("=" * 50)
    print("TEST 1 — Image originale (sans prétraitement)")
    print("=" * 50)
    resultats = reader.readtext(chemin, detail=1, paragraph=False)
    resultats.sort(key=lambda x: x[0][0][1])
    for r in resultats:
        print(f"  [{r[2]*100:.0f}%] {r[1]}")

    # ---- TEST 2 : Avec prétraitement ----
    print("\n" + "=" * 50)
    print("TEST 2 — Avec prétraitement OpenCV")
    print("=" * 50)

    # Agrandir x2
    img2 = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # Niveaux de gris
    gris = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    # Débruitage
    gris = cv2.fastNlMeansDenoising(gris, h=10)
    # Contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gris = clahe.apply(gris)
    # Binarisation
    binaire = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    # Sauvegarder temporairement
    chemin_temp = chemin + "_pretraite.png"
    cv2.imwrite(chemin_temp, binaire)

    resultats2 = reader.readtext(chemin_temp, detail=1, paragraph=False)
    resultats2.sort(key=lambda x: x[0][0][1])
    for r in resultats2:
        print(f"  [{r[2]*100:.0f}%] {r[1]}")

    print(f"\n✅ Image prétraitée sauvegardée : {chemin_temp}")
    print("📌 Ouvre cette image pour voir ce qu'EasyOCR analyse exactement.\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_test.py chemin_image.jpg")
        print("Exemple: python debug_test.py C:\\Users\\Spooky\\cni.jpg")
    else:
        tester_image(sys.argv[1])