import sys
import easyocr
import cv2

print("⏳ Chargement EasyOCR...")
reader = easyocr.Reader(['fr', 'en'], gpu=False)
print("✅ EasyOCR pret !\n")

if len(sys.argv) < 2:
    print("Usage : python debug_plan.py chemin/vers/local.jpeg")
    sys.exit(1)

    chemin = sys.argv[1]

    img = cv2.imread(chemin)
    if img is None:
        print(f"❌Impossible de lire : {chemin}")
        sys.exit(1)

        print(f"📄 Image : {chemin}")
        print(f"📐 Taille : {img.shape[1]}*{img.shape[0]} pixels/n")

        print("="*50)
        print("TEST - Image originale (sans pretraitement)")
        print("="*50)

        resultats = reader.readtext(chemin, detail=1, paragraph=False)
        resultats.sort(key=lambda x: x[0][0][1])

        for r in resultats:
            print(f" [{r[2]*100:.0f}%] {r[1]}")