# ============================================================================
# AccountOCR — Professional Backend Server (Gemini Powered)
# CNI Extraction: Gemini 1.5 Flash (Multimodal)
# Plan Extraction: Gemini 1.5 Flash (Multimodal)
# ============================================================================

from __future__ import annotations

import os
import re
import json
import time
import logging
import tempfile
import traceback
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
import base64
from io import BytesIO
import google.generativeai as genai
import mimetypes
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, Field
from groq import Groq, APIError, APIConnectionError, RateLimitError
from PIL import Image
from dotenv import load_dotenv


# ----------------------------------------------------------------------------
# Configuration & Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AccountOCR")

load_dotenv()
logger = logging.getLogger("cni_extractor")
 
# ----------------------------------------------------------------------------
# Config centrale du serveur (clés API, réglages)
# ----------------------------------------------------------------------------
class ServerConfig:
    """Centralise les clés API et réglages lus depuis .env."""
 
    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
 
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY manquante dans .env — l'extraction CNI échouera.")
 
 
# ----------------------------------------------------------------------------
# Extraction CNI via Qwen (Groq)
# ----------------------------------------------------------------------------
CNI_MODEL_NAME = "qwen/qwen3.6-27b"
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 60
 
CNI_SCHEMA_KEYS = (
    "nom", "prenoms", "date_naissance", "lieu_naissance", "date_expiration",
    "nom_pere", "nom_mere", "profession", "numero_cni", "date_delivrance",
)
 
CNI_SYSTEM_PROMPT = """Tu es un système spécialisé dans l'extraction de données à partir \
de photos de Carte Nationale d'Identité (CNI) camerounaise.
 
Tu recevras soit :
- UNE SEULE image contenant déjà le recto et le verso (ou juste le recto), soit
- DEUX images séparées : la première est le RECTO, la seconde est le VERSO.
 
Dans tous les cas, tu dois FUSIONNER les informations trouvées sur l'ensemble \
des images reçues en un seul objet JSON. Si une information n'apparaît sur \
aucune image, laisse sa valeur à null. Ne devine jamais une valeur que tu ne \
peux pas lire clairement.
 
Réponds STRICTEMENT avec un objet JSON respectant exactement ce format, \
sans aucun texte avant ou après, sans balises markdown :
 
{
  "nom": null,
  "prenoms": null,
  "date_naissance": null,
  "lieu_naissance": null,
  "date_expiration": null,
  "nom_pere": null,
  "nom_mere": null,
  "profession": null,
  "numero_cni": null,
  "date_delivrance": null
}
 
Règles :
- Les dates doivent être renvoyées au format JJ/MM/AAAA si lisible.
- "nom" et "prenoms" doivent être en MAJUSCULES, tels qu'imprimés sur la carte.
- "numero_cni" doit être renvoyé sans espaces.
- Si le texte est partiellement illisible, renvoie uniquement la partie certaine ; \
si rien n'est certain, renvoie null pour ce champ.
"""
 
 
class CNIExtractionError(Exception):
    """Erreur métier levée quand l'extraction CNI échoue de façon définitive."""
 
 
@dataclass
class CNIExtractionResult:
    data: dict = field(default_factory=dict)
    raw_model_output: Optional[str] = None
    warnings: list = field(default_factory=list)
 
    def to_dict(self) -> dict:
        return {"success": True, "data": self.data, "warnings": self.warnings}
 
 
def _encode_image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise CNIExtractionError(f"Fichier introuvable : {image_path}")
 
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        raise CNIExtractionError(
            f"Format d'image non supporté pour '{path.name}' (détecté: {mime_type})."
        )
 
    if path.stat().st_size > 20 * 1024 * 1024:
        raise CNIExtractionError(f"Image trop volumineuse : '{path.name}' dépasse 20 Mo.")
 
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"
 
 
def _build_user_content(image_paths: list[str]) -> list[dict]:
    if len(image_paths) == 1:
        instruction = (
            "Voici l'image de la CNI (recto, ou recto+verso sur une seule image). "
            "Extrais les informations demandées."
        )
    elif len(image_paths) == 2:
        instruction = (
            "Voici deux images de la même CNI : la première est le RECTO, "
            "la seconde est le VERSO. Fusionne les informations des deux faces "
            "en un seul objet JSON."
        )
    else:
        raise CNIExtractionError(
            f"Nombre d'images invalide : attendu 1 ou 2, reçu {len(image_paths)}."
        )
 
    content: list[dict] = [{"type": "text", "text": instruction}]
    for image_path in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": _encode_image_to_data_url(image_path)},
        })
    return content
 
 
def _validate_and_normalize(parsed: dict) -> tuple[dict, list]:
    warnings = []
    normalized = {}
    for key in CNI_SCHEMA_KEYS:
        value = parsed.get(key, None)
        if isinstance(value, str):
            value = value.strip() or None
        normalized[key] = value
        if key not in parsed:
            warnings.append(f"Champ manquant dans la réponse du modèle : '{key}'")
    unexpected = set(parsed.keys()) - set(CNI_SCHEMA_KEYS)
    if unexpected:
        warnings.append(f"Champs inattendus ignorés : {sorted(unexpected)}")
    return normalized, warnings
 
 
def extract_cni(image_paths: list[str], api_key: Optional[str] = None) -> dict:
    """Extrait les infos d'une CNI (1 image, ou 2 pour recto/verso) via Qwen/Groq."""
    if not image_paths:
        raise CNIExtractionError("Aucune image fournie.")
 
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise CNIExtractionError("Clé API Groq manquante (GROQ_API_KEY).")
 
    client = Groq(api_key=key)
    user_content = _build_user_content(image_paths)
 
    last_error: Optional[Exception] = None
    raw_output = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=CNI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": CNI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_completion_tokens=1024,
                top_p=1,
                stream=False,
                response_format={"type": "json_object"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            raw_output = completion.choices[0].message.content
            break
        except RateLimitError as exc:
            last_error = exc
            wait = RETRY_BASE_DELAY_SECONDS * attempt
            logger.warning("Groq rate limit (tentative %s/%s), retry dans %ss", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
        except APIConnectionError as exc:
            last_error = exc
            wait = RETRY_BASE_DELAY_SECONDS * attempt
            logger.warning("Connexion Groq échouée (tentative %s/%s), retry dans %ss", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
        except APIError as exc:
            raise CNIExtractionError(f"Erreur API Groq : {exc}") from exc
    else:
        raise CNIExtractionError(f"Échec après {MAX_RETRIES} tentatives : {last_error}") from last_error
 
    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CNIExtractionError(f"Réponse du modèle non exploitable : {exc}\nBrut : {raw_output!r}") from exc
 
    if not isinstance(parsed, dict):
        raise CNIExtractionError(f"Réponse du modèle inattendue : {parsed!r}")
 
    normalized, warnings = _validate_and_normalize(parsed)
    return CNIExtractionResult(data=normalized, raw_model_output=raw_output, warnings=warnings).to_dict()
# ----------------------------------------------------------------------------
# Plan Processor: Gemini-Based Extraction
# ----------------------------------------------------------------------------
class PlanProcessor:
    """Handles extraction of location plans using Gemini."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_plan_data(self, image_path: str) -> Dict[str, Any]:
        """Sends the location plan image to Gemini."""
        prompt = """Tu es un expert en extraction de données manuscrites pour des documents bancaires.
Analyse l'image de ce plan de localisation et extrais les informations suivantes sous forme de JSON strict.
Si une information est manquente ou illisible, mets une chaîne vide "".
Ne rajoute aucun texte avant ou après le JSON, pas de balises markdown.

FORMAT JSON ATTENDU :
{
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
}"""
        return self.llm_client.call_gemini_multimodal(prompt, [image_path])

# ----------------------------------------------------------------------------
# OCR Server: Flask API
# ----------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# Initialize components
config = ServerConfig()
llm_client = LLMClient(config)
cni_processor = CniProcessor(llm_client)
plan_processor = PlanProcessor(llm_client)

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "message": "AccountOCR Professional API (Gemini Powered)",
        "version": "6.3"
    })

@app.route("/extraire-tout", methods=["POST"])
def extraire_tout():
    """
    Main endpoint: Extracts data from CNI and Plan using Gemini.
    Expects multiple files for 'cni' and one file for 'plan'.
    """
    if "cni" not in request.files or "plan" not in request.files:
        return jsonify({"erreur": "Les fichiers 'cni' et 'plan' sont requis"}), 400

    fichiers_cni = request.files.getlist("cni")
    fichier_plan = request.files["plan"]

    temp_paths = []
    try:
        # 1. Save CNI images
        cni_paths = []
        for f in fichiers_cni:
            suffix = os.path.splitext(f.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                f.save(tmp.name)
                cni_paths.append(tmp.name)
                temp_paths.append(tmp.name)

        # 2. Save Plan image
        suffix_plan = os.path.splitext(fichier_plan.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_plan) as tmp_plan:
            fichier_plan.save(tmp_plan.name)
            plan_path = tmp_plan.name
            temp_paths.append(plan_path)

        # --- Processing Pipeline (All powered by Gemini 1.5 Flash) ---

        # A. CNI Extraction
        logger.info(f"Processing {len(cni_paths)} CNI images via Gemini...")
        cni_data = cni_processor.extract_cni_data(cni_paths)

        # B. Plan Extraction
        logger.info("Processing Location Plan via Gemini...")
        plan_data = plan_processor.extract_plan_data(plan_path)

        # Combine results
        final_data = {**cni_data, **plan_data}

        return jsonify({
            "succes": True,
            "champs": final_data
        })

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        traceback.print_exc()
        return jsonify({"erreur": str(e)}), 500

    finally:
        # Guaranteed cleanup
        for path in temp_paths:
            try:
                os.remove(path)
            except Exception:
                pass

@app.route("/debug", methods=["POST"])
def debug_ocr():
    """Direct multimodal test for a single image."""
    if "fichier" not in request.files:
        return jsonify({"erreur": "Aucun fichier fourni"}), 400

    f = request.files["fichier"]
    suffix = os.path.splitext(f.filename)[1] or ".jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        f.save(tmp.name)
        path = tmp.name

    try:
        res = llm_client.call_gemini_multimodal("Décris cette image brièvement", [path])
        return jsonify({"resultat": res})
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500
    finally_cleanup = True
    try: os.remove(path)
    except: pass

if __name__ == "__main__":
    logger.info("🚀 AccountOCR Professional API starting...")
    logger.info("📡 Server available at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)






import { useState, useRef, useEffect } from "react";

// ============================================================
// UTILS
// ============================================================
const fileToBase64 = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.readAsDataURL(file);
  reader.onload = () => resolve(reader.result);
  reader.onerror = error => reject(error);
});

// ============================================================
// TRADUCTIONS
// ============================================================
const T = {
  fr: {
    appName: "AccountOCR", bankName: "CCA BANK",
    welcome: "Bienvenue sur AccountOCR",
    welcomeSub: "Système de digitalisation des ouvertures de compte — CCA BANK",
    dashboard: "Tableau de bord",
    comptesJour: "Comptes créés aujourd'hui",
    nouveauCompte: "Nouveau compte ➕",
    extraction: "Extraction Documents",
    importerCNI: "Cliquer pour importer la CNI",
    importerPlan: "Cliquer pour importer le plan de localisation",
    importFormats: "JPG, PNG ou PDF",
    lancerExtraction: "Lancer l'extraction",
    extractionEnCours: "Extraction en cours...",
    extractionReussie: "Extraction réussie",
    donneesExtraites: "Données extraites",
    cni: "CNI", plan: "Plan de localisation",
    personnesContacter: "Personnes à contacter",
    continuer: "Continuer",
    infosCNI: "Identité (CNI)", infosCSO: "Informations complémentaires",
    infosPlan: "Localisation", recapitulatif: "Récapitulatif",
    toutesInfos: "Toutes les informations",
    copierTout: "Copier tout", copie: "Copié !",
    collerAmplitude: "Copiez chaque champ et collez dans Amplitude.",
    imprimer: "Imprimer la fiche client 🖨️",
    choixCompte: "Choix du compte →", choixCompteTitre: "Choix du Compte",
    selectionnerCompte: "Sélectionnez le type de compte",
    voirServices: "Voir les services →",
    erreurServeur: "Serveur OCR non connecté. Lancez server.py.",
    erreurExtraction: "Erreur lors de l'extraction.",
    champsObl: "Champ obligatoire",
    infosCSOManuelles: "Informations complémentaires",
    infosCSOManuelleSub: "Ces informations sont à collecter auprès du client.",
    retour: "←", etape1: "Extraction", etape2: "Infos",
    etape3: "Récapitulatif", etape4: "Compte",
    nonRenseigne: "Non renseigné", importerFichiers: "Importez les 2 fichiers d'abord",
    verifierChamps: "Vérifiez et corrigez si nécessaire",
    serveurOK: "Serveur connecté", serveurKO: "Serveur déconnecté",
  },
  en: {
    appName: "AccountOCR", bankName: "CCA BANK",
    welcome: "Welcome to AccountOCR",
    welcomeSub: "Account opening digitalization system — CCA BANK",
    dashboard: "Dashboard",
    comptesJour: "Accounts created today",
    nouveauCompte: "New account ➕",
    extraction: "Document Extraction",
    importerCNI: "Click to import the ID card",
    importerPlan: "Click to import the location plan",
    importFormats: "JPG, PNG or PDF",
    lancerExtraction: "Start extraction",
    extractionEnCours: "Extraction in progress...",
    extractionReussie: "Extraction successful",
    donneesExtraites: "Extracted data",
    cni: "ID Card", plan: "Location Plan",
    personnesContacter: "Persons to contact",
    continuer: "Continue",
    infosCNI: "Identity (ID Card)", infosCSO: "Additional info",
    infosPlan: "Location", recapitulatif: "Summary",
    toutesInfos: "All information",
    copierTout: "Copy all", copie: "Copied!",
    collerAmplitude: "Copy each field and paste into Amplitude.",
    imprimer: "Print client form 🖨️",
    choixCompte: "Choose account →", choixCompteTitre: "Account Selection",
    selectionnerCompte: "Select account type",
    voirServices: "See services →",
    erreurServeur: "OCR server not connected. Run server.py.",
    erreurExtraction: "Extraction failed.",
    champsObl: "Required field",
    infosCSOManuelles: "Additional information",
    infosCSOManuelleSub: "Collect this information from the client.",
    retour: "←", etape1: "Extraction", etape2: "Info",
    etape3: "Summary", etape4: "Account",
    nonRenseigne: "Not provided", importerFichiers: "Import both files first",
    verifierChamps: "Check and correct if needed",
    serveurOK: "Server connected", serveurKO: "Server disconnected",
  },
};

// ============================================================
// CHAMPS
// ============================================================
const CHAMPS_CNI = [
  { key: "nom", label: "Nom / Surname" },
  { key: "prenom", label: "Prénom / Given Name" },
  { key: "dateNaissance", label: "Date de naissance / Date of Birth" },
  { key: "dateExpiration", label: "Date d'expiration / Date of Expiry" },
  { key: "nomPere", label: "Nom du père / Father's Name" },
  { key: "nomMere", label: "Nom de la mère / Mother's Name" },
  { key: "lieuNaissance", label: "Lieu de naissance / Place of Birth" },
  { key: "profession", label: "Profession / Occupation" },
  { key: "dateDelivrance", label: "Date de délivrance / Date of Issue" },
  { key: "numeroCNI", label: "N° CNI / NIC Number" },
];

const CHAMPS_PLAN = [
  { key: "ville", label: "Ville / City" },
  { key: "quartier", label: "Quartier / District" },
  { key: "tel1", label: "Tél 1" },
  { key: "tel2", label: "Tél 2 (optionnel)" },
  { key: "email", label: "Email (optionnel)" },
  { key: "datePlan", label: "Date" },
];

const CHAMPS_CONTACTS = [
  { key: "contact1Nom", label: "Personne à contacter 01 — Nom" },
  { key: "contact1Tel1", label: "Personne à contacter 01 — Tél 1" },
  { key: "contact1Tel2", label: "Personne à contacter 01 — Tél 2" },
  { key: "contact2Nom", label: "Personne à contacter 02 — Nom" },
  { key: "contact2Tel1", label: "Personne à contacter 02 — Tél 1" },
  { key: "contact2Tel2", label: "Personne à contacter 02 — Tél 2" },
];

// ============================================================
// LOCALSTORAGE
// ============================================================
const LS_DONNEES = "accountocr_donnees";
const LS_PAGE = "accountocr_page";
const LS_COMPTES_JOUR = "accountocr_comptes_jour";
const LS_DATE = "accountocr_date";

function sauvegarder(donnees, page) {
  try { localStorage.setItem(LS_DONNEES, JSON.stringify(donnees)); localStorage.setItem(LS_PAGE, page); } catch (e) { }
}
function charger() {
  try {
    const d = localStorage.getItem(LS_DONNEES);
    const p = localStorage.getItem(LS_PAGE);
    return { donnees: d ? JSON.parse(d) : {}, page: p || "dashboard" };
  } catch (e) { return { donnees: {}, page: "dashboard" }; }
}
function getComptesJour() {
  try {
    const today = new Date().toDateString();
    if (localStorage.getItem(LS_DATE) !== today) {
      localStorage.setItem(LS_DATE, today);
      localStorage.setItem(LS_COMPTES_JOUR, "0");
      return 0;
    }
    return parseInt(localStorage.getItem(LS_COMPTES_JOUR) || "0");
  } catch (e) { return 0; }
}
function incrementerComptesJour() {
  try { const n = getComptesJour() + 1; localStorage.setItem(LS_COMPTES_JOUR, String(n)); return n; } catch (e) { return 0; }
}

// ============================================================
// LOGO ACCOUNTOCR
// ============================================================
function LogoAccountOCR() {
  return (
    <svg width="38" height="38" viewBox="0 0 38 38" fill="none">
      <circle cx="19" cy="19" r="18" fill="url(#g1)" />
      <ellipse cx="19" cy="19" rx="11" ry="7" stroke="white" strokeWidth="2" fill="none" />
      <circle cx="19" cy="19" r="3.5" fill="white" />
      <circle cx="20.5" cy="17.5" r="1.2" fill="url(#g1)" />
      <text x="4" y="23" fontSize="10" fontWeight="900" fill="white" fontFamily="Arial Black">A</text>
      <text x="27" y="23" fontSize="10" fontWeight="900" fill="white" fontFamily="Arial Black">O</text>
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="38" y2="38" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3B0764" />
          <stop offset="1" stopColor="#6B21A8" />
        </linearGradient>
      </defs>
    </svg>
  );
}

// Logo CCA Bank textuel professionnel
function LogoCCABank({ dark }) {
  return (
    <img
    src="/logo1.webp"
    alt="CCA BANK"
    style={{ height: 56, objectFit: "contain"}}
    />
  );
}

// ============================================================
// HEADER
// ============================================================
function Header({ titre, onRetour, dark, setDark, langue, setLangue, t, serveurOK }) {
  return (
    <div className="sticky top-0 z-20" style={{
      background: dark ? "linear-gradient(90deg,#1a0533,#2d0a5e)" : "linear-gradient(90deg,#3B0764,#6B21A8)"
    }}>
      <div className="flex items-center gap-3 px-5 h-14">
        {onRetour && <button onClick={onRetour} className="text-purple-200 hover:text-white text-xl font-bold mr-1">{t.retour}</button>}

        {/* Logo + Nom AccountOCR */}
        <div className="flex items-center gap-2 flex-1">
          <LogoAccountOCR />
          <div>
            <div className="text-white font-black text-base leading-none">{t.appName}</div>
            <div className="text-purple-300 text-xs leading-none mt-0.5">{titre}</div>
          </div>
        </div>

        {/* Options à droite */}
        <div className="flex items-center gap-2">
          {/* Indicateur serveur */}
          <div className={`hidden sm:flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${serveurOK ? "bg-green-500 bg-opacity-25 text-green-300" : "bg-red-500 bg-opacity-25 text-red-300"
            }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${serveurOK ? "bg-green-400" : "bg-red-400"}`} />
            {serveurOK ? t.serveurOK : t.serveurKO}
          </div>

          {/* Langue */}
          <button onClick={() => setLangue(langue === "fr" ? "en" : "fr")}
            className="text-xs font-bold text-purple-200 hover:text-white bg-white bg-opacity-10 hover:bg-opacity-20 px-3 py-1.5 rounded-lg transition-all">
            {langue === "fr" ? "🇬🇧 EN" : "🇫🇷 FR"}
          </button>

          {/* Dark/Light */}
          <button onClick={() => setDark(!dark)}
            className="text-xs font-bold text-purple-200 hover:text-white bg-white bg-opacity-10 hover:bg-opacity-20 px-3 py-1.5 rounded-lg transition-all">
            {dark ? "☀️" : "🌙"}
          </button>

          {/* Logo CCA BANK à droite en gros */}
          <LogoCCABank/>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// ETAPES
// ============================================================
function EtapeIndicateur({ etape, dark, t }) {
  const etapes = [t.etape1, t.etape2, t.etape3, t.etape4];
  return (
    <div className={`flex items-center justify-center gap-1 py-3 border-b flex-wrap px-4 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100"}`}>
      {etapes.map((e, i) => (
        <div key={i} className="flex items-center gap-1">
          <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold transition-all ${i + 1 === etape ? "text-white shadow" :
              i + 1 < etape ? dark ? "bg-purple-900 text-purple-300" : "bg-purple-100 text-purple-700" :
                dark ? "bg-gray-800 text-gray-500" : "bg-gray-100 text-gray-400"
            }`} style={i + 1 === etape ? { background: "linear-gradient(90deg,#3B0764,#6B21A8)" } : {}}>
            <span>{i + 1 < etape ? "✓" : i + 1}</span><span>{e}</span>
          </div>
          {i < etapes.length - 1 && <div className={`w-4 h-0.5 ${i + 1 < etape ? "bg-purple-600" : dark ? "bg-gray-700" : "bg-gray-200"}`} />}
        </div>
      ))}
    </div>
  );
}

// ============================================================
// CHAMP COPIE
// ============================================================
function ChampCopie({ label, valeur, dark, t }) {
  const [copie, setCopie] = useState(false);
  const copier = async () => {
    try { await navigator.clipboard.writeText(valeur || ""); } catch (e) { }
    setCopie(true); setTimeout(() => setCopie(false), 1400);
  };
  return (
    <div className={`flex items-center justify-between rounded-xl p-3 mb-2 border transition-all ${copie ? "border-green-400 bg-green-50" :
        dark ? "border-purple-900 bg-gray-800 hover:border-purple-700" : "border-purple-100 bg-purple-50 hover:border-purple-300"
      }`}>
      <div className="flex-1 min-w-0 mr-3">
        <div className="text-xs font-bold text-purple-500 uppercase tracking-wide mb-0.5">{label}</div>
        <div className={`text-sm font-semibold truncate ${dark ? "text-gray-200" : "text-gray-800"}`}>
          {valeur || <span className={`italic text-xs ${dark ? "text-gray-600" : "text-gray-300"}`}>{t.nonRenseigne}</span>}
        </div>
      </div>
      <button onClick={copier} className={`px-3 py-1.5 rounded-lg text-xs font-bold flex-shrink-0 transition-all ${copie ? "bg-green-500 text-white" :
          dark ? "bg-purple-900 text-purple-300 border border-purple-700 hover:bg-purple-700 hover:text-white" :
            "bg-white text-purple-700 border border-purple-200 hover:bg-purple-700 hover:text-white"
        }`}>
        {copie ? "✓" : "📋"}
      </button>
    </div>
  );
}

// ============================================================
// PAGE DASHBOARD
// ============================================================
function PageDashboard({ onNouveauDossier, dark, setDark, langue, setLangue, t, comptesJour, serveurOK }) {
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.dashboard} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <div className="p-5 max-w-2xl mx-auto">

        {/* Bienvenue */}
        <div className={`rounded-2xl p-5 mb-5 border shadow-sm ${card}`}>
          <div className="flex items-center gap-3">
            <LogoAccountOCR />
            <div>
              <h1 className={`text-lg font-black ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.welcome} 👋</h1>
              <p className={`text-xs mt-0.5 ${dark ? "text-gray-400" : "text-gray-500"}`}>{t.welcomeSub}</p>
            </div>
          </div>
        </div>

        {/* Alerte serveur */}
        {!serveurOK && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mb-5">
            <p className="text-sm font-bold text-red-700">⚠️ {t.serveurKO}</p>
            <p className="text-xs text-red-500 mt-1">Lancez <code className="bg-red-100 px-1 rounded">python server.py</code> dans un terminal.</p>
          </div>
        )}

        {/* Compteur du jour */}
        <div className={`rounded-2xl p-6 mb-5 border shadow-sm ${card}`} style={{
          background: dark ? undefined : "linear-gradient(135deg, #F5F0FF, #EDE9FF)"
        }}>
          <p className="text-xs font-bold uppercase tracking-widest mb-2 text-purple-500">{t.comptesJour}</p>
          <div className="text-6xl font-black" style={{ color: dark ? "#C084FC" : "#3B0764" }}>{comptesJour}</div>
        </div>

        {/* Bouton nouveau compte */}
        <button onClick={onNouveauDossier}
          className="w-full py-4 rounded-2xl font-black text-white text-base shadow-lg mb-2 transition-all hover:opacity-90"
          style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
          {t.nouveauCompte}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// PAGE EXTRACTION
// ============================================================
function PageExtraction({ onRetour, onContinuer, dark, setDark, langue, setLangue, t, serveurOK, donneesInitiales }) {
  const [fichiersCNI, setFichiersCNI] = useState([]);
  const [fichierPlan, setFichierPlan] = useState(null);
  const [enCours, setEnCours] = useState(false);
  const [progression, setProgression] = useState(0);
  const [etape, setEtape] = useState("");
  const [termine, setTermine] = useState(false);
  const [donnees, setDonnees] = useState(donneesInitiales || {});
  const [erreur, setErreur] = useState("");

  const estIncertain = (val) => !val || val.trim() === "" || val.toLowerCase().includes("[illisible]");

  const refCNI = useRef();
  const refPlan = useRef();
  const peutExtraire = fichiersCNI.length > 0 && fichierPlan && !enCours && !termine && serveurOK;
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";


  const lancerExtraction = async () => {
    setEnCours(true); setErreur(""); setProgression(0); setTermine(false);
    try {
      setEtape("envoi"); setProgression(15);
      const formData = new FormData();
      fichiersCNI.forEach(file => formData.append("cni", file));
      formData.append("plan", fichierPlan);
      setEtape("traitement"); setProgression(40);
      const response = await fetch("http://localhost:5000/extraire-tout", { method: "POST", body: formData });
      setProgression(85);
      if (!response.ok) throw new Error(`Erreur serveur: ${response.status}`);
      const data = await response.json();
      setProgression(100);
      if (data.succes && data.champs) {
        setDonnees(data.champs);
        sauvegarder(data.champs, "extraction");
        setTermine(true);
      } else throw new Error(data.erreur || t.erreurExtraction);
    } catch (e) {
      setErreur(e.message.includes("fetch") || e.message.includes("Failed") ? t.erreurServeur : e.message);
    } finally { setEnCours(false); setEtape(""); }
  };

  const msgEtape = etape === "envoi" ? "📤 Envoi des fichiers..." : "🔍 Analyse en cours...";

  const zoneImport = (fichiers, label, onClic) => {
    const hasFiles = Array.isArray(fichiers) ? fichiers.length > 0 : !!fichiers;
    const displayText = Array.isArray(fichiers)
      ? (fichiers.length > 1 ? `${fichiers.length} fichiers sélectionnés` : (fichiers[0]?.name || "Aucun fichier"))
      : (fichiers ? fichiers.name : `Cliquer pour importer ${label === "CNI" ? "la CNI" : "le plan de localisation"}`);

    return (
      <div onClick={!enCours ? onClic : undefined}
        className={`rounded-xl border-2 border-dashed p-5 flex flex-col items-center justify-center transition-all mb-3 ${enCours ? "cursor-not-allowed opacity-60" : "cursor-pointer"} ${hasFiles ? dark ? "border-purple-600 bg-purple-950" : "border-purple-600 bg-purple-50" :
            dark ? "border-gray-700 bg-gray-800 hover:border-purple-600" : "border-purple-200 bg-purple-50 hover:border-purple-500"
          }`}>
        <span className="text-3xl mb-2">{hasFiles ? "✅" : label === "CNI" ? "🪪" : "📍"}</span>
        <span className={`text-sm font-bold text-center ${dark ? hasFiles ? "text-purple-300" : "text-purple-500" : hasFiles ? "text-purple-800" : "text-purple-400"}`}>
          {displayText}
        </span>
        {!hasFiles && <span className={`text-xs mt-1 ${dark ? "text-gray-500" : "text-gray-400"}`}>{t.importFormats}</span>}
      </div>
    );
  };

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.extraction} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={1} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>Importer les documents</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-500"}`}>JPG, PNG ou PDF — EasyOCR + IA analysent automatiquement.</p>
          <input ref={refCNI} type="file" accept="image/*,.pdf" multiple className="hidden" onChange={async e => {
            const files = Array.from(e.target.files);
            setFichiersCNI(files); setTermine(false); setErreur("");
            if (files.length > 0) {
              try {
                const b64 = await fileToBase64(files[0]);
                localStorage.setItem("accountocr_img_cni", b64);
              } catch (err) { console.error("Erreur storage CNI", err); }
            }
          }} />
          {zoneImport(fichiersCNI, "CNI", () => refCNI.current.click())}
          <input ref={refPlan} type="file" accept="image/*,.pdf" className="hidden" onChange={async e => {
            const file = e.target.files[0];
            setFichierPlan(file); setTermine(false); setErreur("");
            if (file) {
              try {
                const b64 = await fileToBase64(file);
                localStorage.setItem("accountocr_img_plan", b64);
              } catch (err) { console.error("Erreur storage Plan", err); }
            }
          }} />
          {zoneImport(fichierPlan, "Plan", () => refPlan.current.click())}

          {enCours && (
            <div className="mb-4 mt-2">
              <div className="flex justify-between mb-1">
                <span className={`text-xs font-bold ${dark ? "text-purple-300" : "text-purple-800"}`}>{msgEtape}</span>
                <span className={`text-xs font-bold ${dark ? "text-purple-300" : "text-purple-800"}`}>{progression}%</span>
              </div>
              <div className={`w-full rounded-full h-3 ${dark ? "bg-gray-800" : "bg-purple-100"}`}>
                <div className="h-3 rounded-full transition-all duration-500" style={{ width: `${progression}%`, background: "linear-gradient(90deg,#3B0764,#6B21A8)" }} />
              </div>
            </div>
          )}
          {erreur && <div className="bg-red-50 border border-red-200 rounded-xl p-3 mb-4 text-xs text-red-700 font-semibold">⚠️ {erreur}</div>}
          {!serveurOK && <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 mb-4 text-xs text-yellow-800 font-semibold">⚠️ Lancez <code className="bg-yellow-100 px-1 rounded">python server.py</code></div>}
          {!termine && (
            <button onClick={lancerExtraction} disabled={!peutExtraire}
              className="w-full py-3 rounded-xl font-bold text-sm text-white transition-all"
              style={{ background: peutExtraire ? "linear-gradient(90deg,#3B0764,#6B21A8)" : dark ? "#1f0a3d" : "#D1D5DB" }}>
              {!fichiersCNI.length || !fichierPlan ? t.importerFichiers : !serveurOK ? t.serveurKO : t.lancerExtraction}
            </button>
          )}
        </div>

        {termine && (
          <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className={`font-bold ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.donneesExtraites}</h3>
              <span className="text-xs bg-green-100 text-green-700 font-bold px-3 py-1 rounded-full">✅ {t.extractionReussie}</span>
            </div>
            <p className={`text-xs mb-4 ${dark ? "text-gray-500" : "text-gray-400"}`}>{t.verifierChamps}</p>

            <p className={`text-xs font-black uppercase tracking-widest mb-2 ${dark ? "text-purple-500" : "text-purple-500"}`}>{t.cni}</p>
            {CHAMPS_CNI.map(c => (
              <div key={c.key} className="mb-2">
                <label className={`block text-xs font-bold uppercase tracking-wide mb-1 ${dark ? "text-purple-400" : "text-purple-600"}`}>{c.label}</label>
                <input value={donnees[c.key] || ""} onChange={e => setDonnees({ ...donnees, [c.key]: e.target.value })}
                  className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition-all ${estIncertain(donnees[c.key]) ? (dark ? "bg-red-900/30 border-red-800 text-red-300" : "bg-red-50 border-red-200 text-red-700") : (dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600")}`} />
              </div>
            ))}

            <p className={`text-xs font-black uppercase tracking-widest mb-2 mt-4 ${dark ? "text-purple-500" : "text-purple-500"}`}>{t.plan}</p>
            {CHAMPS_PLAN.map(c => (
              <div key={c.key} className="mb-2">
                <label className={`block text-xs font-bold uppercase tracking-wide mb-1 ${dark ? "text-purple-400" : "text-purple-600"}`}>{c.label}</label>
                <input value={donnees[c.key] || ""} onChange={e => setDonnees({ ...donnees, [c.key]: e.target.value })}
                  className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`} />
              </div>
            ))}

            <p className={`text-xs font-black uppercase tracking-widest mb-2 mt-4 ${dark ? "text-purple-500" : "text-purple-500"}`}>{t.personnesContacter}</p>
            {CHAMPS_CONTACTS.map(c => (
              <div key={c.key} className="mb-2">
                <label className={`block text-xs font-bold uppercase tracking-wide mb-1 ${dark ? "text-purple-400" : "text-purple-600"}`}>{c.label}</label>
                <input value={donnees[c.key] || ""} onChange={e => setDonnees({ ...donnees, [c.key]: e.target.value })}
                  className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`} />
              </div>
            ))}

            <button onClick={() => onContinuer(donnees)}
              className="w-full mt-4 py-3 rounded-xl font-bold text-white text-sm"
              style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
              {t.continuer} → {t.etape2}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================
// COMPOSANT RADIO/CHECKBOX GROUPE
// ============================================================
function GroupeChoix({ label, options, valeur, onChange, dark, multiple = false }) {
  return (
    <div className="mb-4">
      <label className={`block text-xs font-bold uppercase tracking-wide mb-2 ${dark ? "text-purple-400" : "text-purple-700"}`}>{label}</label>
      <div className="flex flex-wrap gap-3">
        {options.map(opt => {
          const selectionne = multiple ? (valeur || []).includes(opt) : valeur === opt;
          return (
            <label key={opt} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all text-sm font-semibold ${selectionne
                ? "border-purple-600 text-white"
                : dark ? "border-gray-700 text-gray-300 hover:border-purple-600" : "border-purple-200 text-gray-700 hover:border-purple-500"
              }`} style={selectionne ? { background: "linear-gradient(90deg,#3B0764,#6B21A8)" } : {}}>
              <input
                type={multiple ? "checkbox" : "radio"}
                name={label}
                value={opt}
                checked={selectionne}
                onChange={() => {
                  if (multiple) {
                    const arr = valeur || [];
                    onChange(arr.includes(opt) ? arr.filter(x => x !== opt) : [...arr, opt]);
                  } else {
                    onChange(opt);
                  }
                }}
                className="hidden"
              />
              <span className={`w-4 h-4 rounded-sm border-2 flex items-center justify-center flex-shrink-0 ${selectionne ? "border-white" : dark ? "border-gray-500" : "border-purple-300"}`}>
                {selectionne && <span className="text-white text-xs font-black">✓</span>}
              </span>
              {opt}
            </label>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// PAGE INFOS CSO
// ============================================================
function PageInfosCSO({ onRetour, onContinuer, donneesOCR, dark, setDark, langue, setLangue, t, serveurOK }) {
  const [champs, setChamps] = useState({
    nomEntreprise: "", nomEmployeur: "", dateEmbauche: "",
    situationMatrimoniale: "", regimeMatrimonial: "", communauteBiens: "",
    agenceBase: "", autreCompteCCA: "",
    compte1Numero: "", compte1Intitule: "",
    compte2Numero: "", compte2Intitule: "",
    situationImmobiliere: "", periodiciteRevenu: "",
    nomEpoux: "", personnesCharge: "", salaire: "",
  });

  const set = (key, val) => setChamps(prev => ({ ...prev, [key]: val }));
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const inputCls = `w-full px-4 py-2.5 rounded-xl border-2 text-sm outline-none transition-all ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`;

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.infosCSOManuelles} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={2} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.infosCSOManuelles}</h3>
          <p className={`text-xs mb-5 ${dark ? "text-gray-400" : "text-gray-500"}`}>{t.infosCSOManuelleSub}</p>

          {/* Infos professionnelles */}
          <p className={`text-xs font-black uppercase tracking-widest mb-3 ${dark ? "text-purple-500" : "text-purple-500"}`}>Informations professionnelles</p>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Nom de votre entreprise <span className="font-normal text-gray-400">(si applicable)</span></label>
            <input value={champs.nomEntreprise} onChange={e => set("nomEntreprise", e.target.value)} placeholder="Nom de l'entreprise" className={inputCls} />
          </div>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Nom de l'employeur <span className="font-normal text-gray-400">(si applicable)</span></label>
            <input value={champs.nomEmployeur} onChange={e => set("nomEmployeur", e.target.value)} placeholder="Nom de l'employeur" className={inputCls} />
          </div>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Date d'embauche ou début d'activité</label>
            <input type="date" value={champs.dateEmbauche} onChange={e => set("dateEmbauche", e.target.value)} className={inputCls} />
          </div>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Salaire (FCFA) <span className="text-red-400">*</span></label>
            <input value={champs.salaire} onChange={e => set("salaire", e.target.value)} placeholder="Ex: 150000" className={inputCls} />
          </div>

          <GroupeChoix label="Périodicité de revenu" options={["MENSUEL", "TRIMESTRIEL", "SEMESTRIEL", "ANNUEL"]}
            valeur={champs.periodiciteRevenu} onChange={v => set("periodiciteRevenu", v)} dark={dark} />

          {/* Situation personnelle */}
          <p className={`text-xs font-black uppercase tracking-widest mb-3 mt-5 ${dark ? "text-purple-500" : "text-purple-500"}`}>Situation personnelle</p>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Nom de l'époux/épouse</label>
            <input value={champs.nomEpoux} onChange={e => set("nomEpoux", e.target.value)} placeholder="Si célibataire, laisser vide" className={inputCls} />
          </div>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Nombre de personnes à charge</label>
            <input value={champs.personnesCharge} onChange={e => set("personnesCharge", e.target.value)} placeholder="Ex: 2" className={inputCls} />
          </div>

          <GroupeChoix label="Situation matrimoniale" options={["CÉLIBATAIRE", "MARIÉ(E)", "DIVORCÉ(E)", "VEUF(VE)"]}
            valeur={champs.situationMatrimoniale} onChange={v => set("situationMatrimoniale", v)} dark={dark} />

          <GroupeChoix label="Régime matrimonial" options={["MONOGAMIE", "POLYGAMIE", "NON CONCERNÉ"]}
            valeur={champs.regimeMatrimonial} onChange={v => set("regimeMatrimonial", v)} dark={dark} />

          <GroupeChoix label="Communauté de biens" options={["BIENS COMMUNS", "BIENS SÉPARÉS"]}
            valeur={champs.communauteBiens} onChange={v => set("communauteBiens", v)} dark={dark} />

          <GroupeChoix label="Situation immobilière" options={["LOCATAIRE", "PROPRIÉTAIRE", "FAMILLE D'ACCUEIL"]}
            valeur={champs.situationImmobiliere} onChange={v => set("situationImmobiliere", v)} dark={dark} />

          {/* Infos bancaires */}
          <p className={`text-xs font-black uppercase tracking-widest mb-3 mt-5 ${dark ? "text-purple-500" : "text-purple-500"}`}>Informations bancaires</p>

          <div className="mb-4">
            <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>Agence de base</label>
            <input value={champs.agenceBase} onChange={e => set("agenceBase", e.target.value)} placeholder="Nom de l'agence" className={inputCls} />
          </div>

          <GroupeChoix label="Avez-vous un autre compte au CCA ?" options={["OUI", "NON"]}
            valeur={champs.autreCompteCCA} onChange={v => set("autreCompteCCA", v)} dark={dark} />

          {champs.autreCompteCCA === "OUI" && (
            <div className={`rounded-xl p-4 mb-4 border ${dark ? "border-gray-700 bg-gray-800" : "border-purple-100 bg-purple-50"}`}>
              <p className={`text-xs font-bold mb-3 ${dark ? "text-purple-400" : "text-purple-700"}`}>Si OUI, le(s) quel(s) :</p>
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div>
                  <label className={`block text-xs font-bold mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>1. N° Compte</label>
                  <input value={champs.compte1Numero} onChange={e => set("compte1Numero", e.target.value)} placeholder="Numéro" className={inputCls} />
                </div>
                <div>
                  <label className={`block text-xs font-bold mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Intitulé</label>
                  <input value={champs.compte1Intitule} onChange={e => set("compte1Intitule", e.target.value)} placeholder="Intitulé" className={inputCls} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className={`block text-xs font-bold mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>2. N° Compte</label>
                  <input value={champs.compte2Numero} onChange={e => set("compte2Numero", e.target.value)} placeholder="Numéro" className={inputCls} />
                </div>
                <div>
                  <label className={`block text-xs font-bold mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Intitulé</label>
                  <input value={champs.compte2Intitule} onChange={e => set("compte2Intitule", e.target.value)} placeholder="Intitulé" className={inputCls} />
                </div>
              </div>
            </div>
          )}

          <p className={`text-xs mb-4 ${dark ? "text-gray-600" : "text-gray-400"}`}>* {t.champsObl}</p>

          <button
            onClick={() => { const d = { ...donneesOCR, ...champs }; sauvegarder(d, "cso"); onContinuer(d); }}
            disabled={!champs.salaire}
            className="w-full py-3 rounded-xl font-bold text-white text-sm transition-all"
            style={{ background: champs.salaire ? "linear-gradient(90deg,#3B0764,#6B21A8)" : dark ? "#1f0a3d" : "#D1D5DB" }}>
            {t.continuer} → {t.etape3}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// PAGE RÉCAPITULATIF + IMPRESSION
// ============================================================
function PageRecapitulatif({ onRetour, onContinuer, donnees, dark, setDark, langue, setLangue, t, serveurOK }) {
  const [toutCopie, setToutCopie] = useState(false);
  const imgCni = localStorage.getItem("accountocr_img_cni");
  const imgPlan = localStorage.getItem("accountocr_img_plan");
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";

  const sections = [
    { titre: t.infosCNI, champs: CHAMPS_CNI },
    { titre: t.infosPlan, champs: CHAMPS_PLAN },
    { titre: t.personnesContacter, champs: CHAMPS_CONTACTS },
    {
      titre: "Informations complémentaires", champs: [
        { key: "nomEntreprise", label: "Nom de l'entreprise" },
        { key: "nomEmployeur", label: "Nom de l'employeur" },
        { key: "dateEmbauche", label: "Date d'embauche" },
        { key: "salaire", label: "Salaire (FCFA)" },
        { key: "periodiciteRevenu", label: "Périodicité de revenu" },
        { key: "nomEpoux", label: "Nom de l'époux/épouse" },
        { key: "personnesCharge", label: "Personnes à charge" },
        { key: "situationMatrimoniale", label: "Situation matrimoniale" },
        { key: "regimeMatrimonial", label: "Régime matrimonial" },
        { key: "communauteBiens", label: "Communauté de biens" },
        { key: "situationImmobiliere", label: "Situation immobilière" },
        { key: "agenceBase", label: "Agence de base" },
        { key: "autreCompteCCA", label: "Autre compte CCA" },
        { key: "compte1Numero", label: "Compte 1 — N°" },
        { key: "compte1Intitule", label: "Compte 1 — Intitulé" },
        { key: "compte2Numero", label: "Compte 2 — N°" },
        { key: "compte2Intitule", label: "Compte 2 — Intitulé" },
      ]
    },
  ];

  const copierTout = async () => {
    const lignes = sections.flatMap(s => s.champs.map(c => `${c.label}: ${donnees[c.key] || "—"}`));
    try { await navigator.clipboard.writeText(lignes.join("\n")); } catch (e) { }
    setToutCopie(true); setTimeout(() => setToutCopie(false), 2000);
  };

  
    const imprimer = () => {
      const date = new Date().toLocaleDateString("fr-FR");
      const contenu = `
      <html><head><title>Fiche Client — AccountOCR</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; font-size: 11px; color: #111; }

        /* ---- PAGE RECTO ---- */
        .page {
          width: 210mm;
          min-height: 297mm;
          padding: 12mm 15mm;
          page-break-after: always;
        }
        .page:last-child { page-break-after: auto; }

        /* En-tête */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 3px solid #3B0764;
          padding-bottom: 8px;
          margin-bottom: 12px;
        }
        .header-left { display: flex; flex-direction: column; }
        .header-title { font-size: 16px; font-weight: 900; color: #3B0764; letter-spacing: 1px; }
        .header-sub { font-size: 9px; color: #666; margin-top: 2px; }
        .header-right { text-align: right; font-size: 9px; color: #555; }
        .header-bank { font-size: 14px; font-weight: 900; color: #6B21A8; }

        /* Sections */
        .section { margin-bottom: 10px; }
        .section-title {
          background: linear-gradient(90deg, #3B0764, #6B21A8);
          color: white;
          padding: 4px 10px;
          font-size: 10px;
          font-weight: 900;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 6px;
          border-radius: 3px;
        }

        /* Grille 2 colonnes */
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px 12px; }

        .champ {
          display: flex;
          flex-direction: column;
          border-bottom: 1px solid #E5E7EB;
          padding: 3px 0;
        }
        .label { font-size: 8px; color: #6B21A8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }
        .valeur { font-size: 11px; color: #111; font-weight: 600; min-height: 14px; }

        /* Cases à cocher dans la fiche */
        .cases { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 2px; }
        .case-item { display: flex; align-items: center; gap: 4px; font-size: 10px; }
        .case-box {
          width: 12px; height: 12px; border: 1.5px solid #3B0764;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .case-box.checked { background: #3B0764; }
        .case-check { color: white; font-size: 9px; font-weight: 900; }

        /* Signature */
        .signature-zone {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          margin-top: 15px;
          padding-top: 10px;
          border-top: 1px solid #E5E7EB;
        }
        .signature-box {
          border: 1px solid #3B0764;
          height: 60px;
          border-radius: 4px;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          padding: 4px 8px;
        }
        .signature-label { font-size: 8px; color: #6B21A8; font-weight: 700; text-transform: uppercase; }

        /* Footer */
        .footer {
          text-align: center;
          margin-top: 10px;
          font-size: 8px;
          color: #9CA3AF;
          border-top: 1px solid #E5E7EB;
          padding-top: 6px;
        }

        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .page { margin: 0; }
        }
      </style></head><body>

      <!-- ============ PAGE RECTO ============ -->
      <div class="page">
        <div class="header">
          <div class="header-left">
            <div class="header-title">📄 FICHE D'OUVERTURE DE COMPTE</div>
            <div class="header-sub">Généré par AccountOCR — ${date}</div>
          </div>
          <div class="header-right">
            <div class="header-bank">CCA BANK</div>
            <div>Confidentiel — Usage interne</div>
          </div>
        </div>

        <!-- IDENTITÉ CNI -->
        <div class="section">
          <div class="section-title">Identité — CNI</div>
          <div class="grid-2">
            <div class="champ"><div class="label">Nom / Surname</div><div class="valeur">${donnees.nom || "—"}</div></div>
            <div class="champ"><div class="label">Prénom / Given Name</div><div class="valeur">${donnees.prenom || "—"}</div></div>
            <div class="champ"><div class="label">Date de naissance</div><div class="valeur">${donnees.dateNaissance || "—"}</div></div>
            <div class="champ"><div class="label">Lieu de naissance</div><div class="valeur">${donnees.lieuNaissance || "—"}</div></div>
            <div class="champ"><div class="label">Nom du père</div><div class="valeur">${donnees.nomPere || "—"}</div></div>
            <div class="champ"><div class="label">Nom de la mère</div><div class="valeur">${donnees.nomMere || "—"}</div></div>
            <div class="champ"><div class="label">Profession / Occupation</div><div class="valeur">${donnees.profession || "—"}</div></div>
            <div class="champ"><div class="label">Date d'expiration CNI</div><div class="valeur">${donnees.dateExpiration || "—"}</div></div>
            <div class="champ"><div class="label">Date de délivrance</div><div class="valeur">${donnees.dateDelivrance || "—"}</div></div>
            <div class="champ"><div class="label">N° CNI / NIC Number</div><div class="valeur">${donnees.numeroCNI || "—"}</div></div>
          </div>
        </div>

        <!-- LOCALISATION -->
        <div class="section">
          <div class="section-title">Localisation</div>
          <div class="grid-3">
            <div class="champ"><div class="label">Ville</div><div class="valeur">${donnees.ville || "—"}</div></div>
            <div class="champ"><div class="label">Quartier</div><div class="valeur">${donnees.quartier || "—"}</div></div>
            <div class="champ"><div class="label">Date</div><div class="valeur">${donnees.datePlan || "—"}</div></div>
            <div class="champ"><div class="label">Tél 1</div><div class="valeur">${donnees.tel1 || "—"}</div></div>
            <div class="champ"><div class="label">Tél 2</div><div class="valeur">${donnees.tel2 || "—"}</div></div>
            <div class="champ"><div class="label">Email</div><div class="valeur">${donnees.email || "—"}</div></div>
          </div>
        </div>

        <!-- PERSONNES À CONTACTER -->
        <div class="section">
          <div class="section-title">Personnes à contacter</div>
          <div class="grid-2">
            <div class="champ"><div class="label">Contact 01 — Nom</div><div class="valeur">${donnees.contact1Nom || "—"}</div></div>
            <div class="champ"><div class="label">Contact 02 — Nom</div><div class="valeur">${donnees.contact2Nom || "—"}</div></div>
            <div class="champ"><div class="label">Contact 01 — Tél 1</div><div class="valeur">${donnees.contact1Tel1 || "—"}</div></div>
            <div class="champ"><div class="label">Contact 02 — Tél 1</div><div class="valeur">${donnees.contact2Tel1 || "—"}</div></div>
            <div class="champ"><div class="label">Contact 01 — Tél 2</div><div class="valeur">${donnees.contact1Tel2 || "—"}</div></div>
            <div class="champ"><div class="label">Contact 02 — Tél 2</div><div class="valeur">${donnees.contact2Tel2 || "—"}</div></div>
          </div>
        </div>

        <!-- SITUATION PERSONNELLE -->
        <div class="section">
          <div class="section-title">Situation personnelle</div>
          <div class="grid-2">
            <div class="champ"><div class="label">Nom de l'époux/épouse</div><div class="valeur">${donnees.nomEpoux || "—"}</div></div>
            <div class="champ"><div class="label">Personnes à charge</div><div class="valeur">${donnees.personnesCharge || "—"}</div></div>
          </div>
          <div style="margin-top:6px;">
            <div class="label" style="margin-bottom:4px;">Situation matrimoniale</div>
            <div class="cases">
              ${["CÉLIBATAIRE", "MARIÉ(E)", "DIVORCÉ(E)", "VEUF(VE)"].map(opt => `
                <div class="case-item">
                  <div class="case-box ${donnees.situationMatrimoniale === opt ? 'checked' : ''}">
                    ${donnees.situationMatrimoniale === opt ? '<span class="case-check">✓</span>' : ''}
                  </div>
                  <span>${opt}</span>
                </div>`).join("")}
            </div>
          </div>
          <div style="margin-top:6px;">
            <div class="label" style="margin-bottom:4px;">Régime matrimonial</div>
            <div class="cases">
              ${["MONOGAMIE", "POLYGAMIE", "NON CONCERNÉ"].map(opt => `
                <div class="case-item">
                  <div class="case-box ${donnees.regimeMatrimonial === opt ? 'checked' : ''}">
                    ${donnees.regimeMatrimonial === opt ? '<span class="case-check">✓</span>' : ''}
                  </div>
                  <span>${opt}</span>
                </div>`).join("")}
            </div>
          </div>
          <div style="margin-top:6px;">
            <div class="label" style="margin-bottom:4px;">Communauté de biens</div>
            <div class="cases">
              ${["BIENS COMMUNS", "BIENS SÉPARÉS"].map(opt => `
                <div class="case-item">
                  <div class="case-box ${donnees.communauteBiens === opt ? 'checked' : ''}">
                    ${donnees.communauteBiens === opt ? '<span class="case-check">✓</span>' : ''}
                  </div>
                  <span>${opt}</span>
                </div>`).join("")}
            </div>
          </div>
          <div style="margin-top:6px;">
            <div class="label" style="margin-bottom:4px;">Situation immobilière</div>
            <div class="cases">
              ${["LOCATAIRE", "PROPRIÉTAIRE", "FAMILLE D'ACCUEIL"].map(opt => `
                <div class="case-item">
                  <div class="case-box ${donnees.situationImmobiliere === opt ? 'checked' : ''}">
                    ${donnees.situationImmobiliere === opt ? '<span class="case-check">✓</span>' : ''}
                  </div>
                  <span>${opt}</span>
                </div>`).join("")}
            </div>
          </div>
        </div>

        <div class="footer">RECTO — Page 1/2 — AccountOCR CCA BANK — ${date}</div>
      </div>

      <!-- ============ PAGE VERSO ============ -->
      <div class="page">
        <div class="header">
          <div class="header-left">
            <div class="header-title">📄 FICHE D'OUVERTURE DE COMPTE</div>
            <div class="header-sub">Suite — Informations professionnelles & bancaires</div>
          </div>
          <div class="header-right">
            <div class="header-bank">CCA BANK</div>
            <div>Confidentiel — Usage interne</div>
          </div>
        </div>

        <!-- INFORMATIONS PROFESSIONNELLES -->
        <div class="section">
          <div class="section-title">Informations professionnelles</div>
          <div class="grid-2">
            <div class="champ"><div class="label">Nom de l'entreprise</div><div class="valeur">${donnees.nomEntreprise || "—"}</div></div>
            <div class="champ"><div class="label">Nom de l'employeur</div><div class="valeur">${donnees.nomEmployeur || "—"}</div></div>
            <div class="champ"><div class="label">Date d'embauche</div><div class="valeur">${donnees.dateEmbauche || "—"}</div></div>
            <div class="champ"><div class="label">Salaire (FCFA)</div><div class="valeur">${donnees.salaire || "—"}</div></div>
          </div>
          <div style="margin-top:6px;">
            <div class="label" style="margin-bottom:4px;">Périodicité de revenu</div>
            <div class="cases">
              ${["MENSUEL", "TRIMESTRIEL", "SEMESTRIEL", "ANNUEL"].map(opt => `
                <div class="case-item">
                  <div class="case-box ${donnees.periodiciteRevenu === opt ? 'checked' : ''}">
                    ${donnees.periodiciteRevenu === opt ? '<span class="case-check">✓</span>' : ''}
                  </div>
                  <span>${opt}</span>
                </div>`).join("")}
            </div>
          </div>
        </div>

        <!-- INFORMATIONS BANCAIRES -->
        <div class="section">
          <div class="section-title">Informations bancaires</div>
          <div class="grid-2">
            <div class="champ"><div class="label">Agence de base</div><div class="valeur">${donnees.agenceBase || "—"}</div></div>
            <div class="champ">
              <div class="label">Autre compte CCA ?</div>
              <div class="cases" style="margin-top:4px;">
                ${["OUI", "NON"].map(opt => `
                  <div class="case-item">
                    <div class="case-box ${donnees.autreCompteCCA === opt ? 'checked' : ''}">
                      ${donnees.autreCompteCCA === opt ? '<span class="case-check">✓</span>' : ''}
                    </div>
                    <span>${opt}</span>
                  </div>`).join("")}
              </div>
            </div>
          </div>
          ${donnees.autreCompteCCA === "OUI" ? `
          <div style="margin-top:6px; padding:8px; border:1px solid #E5E7EB; border-radius:4px;">
            <div class="label" style="margin-bottom:6px;">Si OUI, le(s) quel(s) :</div>
            <div class="grid-2">
              <div class="champ"><div class="label">1. N° Compte</div><div class="valeur">${donnees.compte1Numero || "—"}</div></div>
              <div class="champ"><div class="label">Intitulé</div><div class="valeur">${donnees.compte1Intitule || "—"}</div></div>
              <div class="champ"><div class="label">2. N° Compte</div><div class="valeur">${donnees.compte2Numero || "—"}</div></div>
              <div class="champ"><div class="label">Intitulé</div><div class="valeur">${donnees.compte2Intitule || "—"}</div></div>
            </div>
          </div>` : ""}
        </div>

        <!-- ZONES SIGNATURE -->
        <div class="section" style="margin-top: 20px;">
          <div class="section-title">Signatures</div>
          <div class="signature-zone">
            <div>
              <div class="signature-box"></div>
              <div class="signature-label" style="margin-top:4px;">Signature du client</div>
            </div>
            <div>
              <div class="signature-box"></div>
              <div class="signature-label" style="margin-top:4px;">Signature du CSO</div>
            </div>
          </div>
        </div>

        <!-- MENTIONS LÉGALES -->
        <div style="margin-top: 20px; padding: 10px; border: 1px solid #E5E7EB; border-radius: 4px; background: #F9FAFB;">
          <div style="font-size: 8px; color: #555; line-height: 1.6;">
            <strong>Déclaration du client :</strong> Je soussigné(e) certifie l'exactitude des informations fournies ci-dessus 
            et m'engage à informer la CCA Bank de tout changement. Je reconnais avoir pris connaissance des conditions 
            générales d'ouverture de compte et les accepte sans réserve.
          </div>
        </div>

        <div class="footer">VERSO — Page 2/2 — AccountOCR CCA BANK — ${date}</div>
      </div>

      </body></html>
    `;
      const win = window.open("", "_blank");
      win.document.write(contenu);
      win.document.close();
      win.print();
    };
  

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.recapitulatif} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={3} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className={`font-bold ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.toutesInfos}</h3>
            <button onClick={copierTout} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${toutCopie ? "bg-green-500 text-white" :
                dark ? "bg-purple-900 text-purple-300 hover:bg-purple-700 hover:text-white" : "bg-purple-100 text-purple-700 hover:text-white"
              }`} style={!toutCopie ? { background: toutCopie ? undefined : undefined } : {}}>
              {toutCopie ? `✓ ${t.copie}` : t.copierTout}
            </button>
          </div>
          <p className={`text-xs mb-4 ${dark ? "text-gray-500" : "text-gray-400"}`}>{t.collerAmplitude}</p>

          <div className={`rounded-2xl shadow-sm border p-4 mb-6 ${card}`}>
            <h3 className={`font-bold text-xs uppercase tracking-widest mb-3 ${dark ? "text-purple-400" : "text-purple-700"}`}>Aperçu des documents</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col items-center gap-2">
                <span className="text-[10px] font-bold uppercase text-purple-500">{t.cni}</span>
                <div className={`w-full h-32 rounded-lg border overflow-hidden bg-gray-100 ${dark ? "bg-gray-800 border-gray-700" : "border-purple-100"}`}>
                  {imgCni ? <img src={imgCni} className="w-full h-full object-contain" /> : <div className="flex items-center justify-center h-full text-gray-400 text-[10px]">Aucune image</div>}
                </div>
              </div>
              <div className="flex flex-col items-center gap-2">
                <span className="text-[10px] font-bold uppercase text-purple-500">{t.plan}</span>
                <div className={`w-full h-32 rounded-lg border overflow-hidden bg-gray-100 ${dark ? "bg-gray-800 border-gray-700" : "border-purple-100"}`}>
                  {imgPlan ? <img src={imgPlan} className="w-full h-full object-contain" /> : <div className="flex items-center justify-center h-full text-gray-400 text-[10px]">Aucune image</div>}
                </div>
              </div>
            </div>
          </div>

          {sections.map(s => (
            <div key={s.titre} className="mb-4">
              <p className={`text-xs font-black uppercase tracking-widest mb-2 ${dark ? "text-purple-500" : "text-purple-500"}`}>{s.titre}</p>
              {s.champs.map(c => <ChampCopie key={c.key} label={c.label} valeur={donnees[c.key]} dark={dark} t={t} />)}
            </div>
          ))}
        </div>

        {/* Bouton imprimer */}
        <button onClick={imprimer}
          className="w-full py-3.5 rounded-xl font-bold text-white text-sm shadow-lg mb-3 flex items-center justify-center gap-2"
          style={{ background: "linear-gradient(90deg,#065F46,#059669)" }}>
          {t.imprimer}
        </button>

        <button onClick={onContinuer}
          className="w-full py-3.5 rounded-xl font-bold text-white text-sm shadow-lg"
          style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
          {t.choixCompte}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// PAGE COMPTES
// ============================================================
function PageComptes({ onRetour, onTerminer, dark, setDark, langue, setLangue, t, serveurOK }) {
  const comptes = [
    { key: "epargne", label: "Compte Épargne", icon: "🏦", desc: "Placement et économies" },
    { key: "courant", label: "Compte Courant", icon: "💳", desc: "Usage quotidien" },
    { key: "salaire", label: "Compte Salaire", icon: "💼", desc: "Virement de salaire" },
    { key: "entreprise", label: "Compte Entreprise", icon: "🏢", desc: "Personnes morales" },
  ];
  const [choix, setChoix] = useState(null);
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.choixCompteTitre} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={4} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.selectionnerCompte}</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-400"}`}>Cliquez sur le compte souhaité.</p>
          <div className="grid grid-cols-2 gap-3 mb-5">
            {comptes.map(c => (
              <button key={c.key} onClick={() => setChoix(c.key)}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 font-bold text-sm transition-all ${choix === c.key ? "border-purple-800 text-white shadow-md" :
                    dark ? "border-gray-700 bg-gray-800 text-purple-300 hover:border-purple-600" : "border-purple-100 bg-white text-purple-800 hover:border-purple-500"
                  }`} style={choix === c.key ? { background: "linear-gradient(135deg,#3B0764,#6B21A8)" } : {}}>
                <span className="text-3xl">{c.icon}</span>
                <span>{c.label}</span>
                <span className={`text-xs font-normal ${choix === c.key ? "text-purple-200" : dark ? "text-gray-500" : "text-gray-400"}`}>{c.desc}</span>
              </button>
            ))}
          </div>
          <button onClick={onTerminer} disabled={!choix}
            className="w-full py-3 rounded-xl font-bold text-white text-sm"
            style={{ background: choix ? "linear-gradient(90deg,#3B0764,#6B21A8)" : dark ? "#1f0a3d" : "#D1D5DB" }}>
            {t.voirServices}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// APP
// ============================================================
export default function App() {
  const [dark, setDark] = useState(false);
  const [langue, setLangue] = useState("fr");
  const [comptesJour, setComptesJour] = useState(getComptesJour());
  const [serveurOK, setServeurOK] = useState(false);
  const [page, setPage] = useState("dashboard");
  const [donnees, setDonnees] = useState({});
  const t = T[langue];

  useEffect(() => {
    const verifier = async () => {
      try {
        const res = await fetch("http://localhost:5000/", { signal: AbortSignal.timeout(2000) });
        setServeurOK(res.ok);
      } catch (e) { setServeurOK(false); }
    };
    verifier();
    const interval = setInterval(verifier, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const s = charger();
    if (s.page && s.page !== "dashboard" && Object.keys(s.donnees).length > 0) {
      setDonnees(s.donnees); setPage(s.page);
    }
  }, []);

  const allerVers = (p, d = donnees) => { setPage(p); setDonnees(d); sauvegarder(d, p); };
  const terminer = () => {
    localStorage.removeItem(LS_DONNEES); localStorage.removeItem(LS_PAGE);
    localStorage.removeItem("accountocr_img_cni"); localStorage.removeItem("accountocr_img_plan");
    setComptesJour(incrementerComptesJour()); setDonnees({}); setPage("dashboard");
  };

  const props = { dark, setDark, langue, setLangue, t, serveurOK };
  if (page === "dashboard") return <PageDashboard {...props} comptesJour={comptesJour} onNouveauDossier={() => allerVers("extraction", {})} />;
  if (page === "extraction") return <PageExtraction {...props} donneesInitiales={donnees} onRetour={() => allerVers("dashboard", {})} onContinuer={d => allerVers("cso", d)} />;
  if (page === "cso") return <PageInfosCSO {...props} donneesOCR={donnees} onRetour={() => allerVers("extraction")} onContinuer={d => allerVers("recap", d)} />;
  if (page === "recap") return <PageRecapitulatif {...props} donnees={donnees} onRetour={() => allerVers("cso")} onContinuer={() => allerVers("comptes")} />;
  if (page === "comptes") return <PageComptes {...props} onRetour={() => allerVers("recap")} onTerminer={terminer} />;
}







from __future__ import annotations

import os
import json
import time
import logging
import tempfile
import traceback
import mimetypes
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

import base64
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------------
# Configuration & Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("AccountOCR")

# ----------------------------------------------------------------------------
# Config centrale du serveur (clés API, réglages)
# ----------------------------------------------------------------------------
class ServerConfig:
    """Centralise les clés API et réglages lus depuis .env."""

    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")

        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY manquante dans .env — l'extraction CNI échouera.")
        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY manquante dans .env — l'extraction du plan échouera.")
        else:
            genai.configure(api_key=self.gemini_api_key)


# ----------------------------------------------------------------------------
# Client Gemini (pour le plan de localisation uniquement)
# ----------------------------------------------------------------------------
class LLMClient:
    """Wrapper simple autour de Gemini, utilisé pour l'extraction du plan."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.model = genai.GenerativeModel("gemini-flash-latest")

    def call_gemini_multimodal(self, prompt: str, image_paths: list[str]) -> Dict[str, Any]:
        images = [{"mime_type": mimetypes.guess_type(p)[0] or "image/jpeg",
                   "data": Path(p).read_bytes()} for p in image_paths]
        response = self.model.generate_content([prompt, *images],
        request_options={"timeout": 60},
        )
        
        raw_text = (response.text or "").strip()
        raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("Réponse Gemini non-JSON : %s", raw_text)
            raise ValueError(f"Réponse Gemini invalide : {exc}") from exc


# ----------------------------------------------------------------------------
# Extraction CNI via Qwen (Groq)
# ----------------------------------------------------------------------------
CNI_MODEL_NAME = "qwen/qwen3.6-27b"
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 60

CNI_SCHEMA_KEYS = (
    "nom", "prenoms", "date_naissance", "lieu_naissance", "date_expiration",
    "nom_pere", "nom_mere", "profession", "numero_cni", "date_delivrance",
)

CNI_SYSTEM_PROMPT = """Tu es un système spécialisé dans l'extraction de données à partir \
de photos de Carte Nationale d'Identité (CNI) camerounaise.

Tu recevras soit :
- UNE SEULE image contenant déjà le recto et le verso (ou juste le recto), soit
- DEUX images séparées : la première est le RECTO, la seconde est le VERSO.

Dans tous les cas, tu dois FUSIONNER les informations trouvées sur l'ensemble \
des images reçues en un seul objet JSON. Si une information n'apparaît sur \
aucune image, laisse sa valeur à null. Ne devine jamais une valeur que tu ne \
peux pas lire clairement.

Réponds STRICTEMENT avec un objet JSON respectant exactement ce format, \
sans aucun texte avant ou après, sans balises markdown :

    {
        "nom": null,
        "prenoms": null,
        "date_naissance": null,
        "lieu_naissance": null,
        "date_expiration": null,
        "nom_pere": null,
        "nom_mere": null,
        "profession": null,
        "numero_cni": null,
        "date_delivrance": null,
    }

Règles :
- Les dates doivent être renvoyées au format JJ/MM/AAAA si lisible.
- "nom" et "prenoms" doivent être en MAJUSCULES, tels qu'imprimés sur la carte.
- "numero_cni" doit être renvoyé sans espaces.
- Si le texte est partiellement illisible, renvoie uniquement la partie certaine ; \
si rien n'est certain, renvoie null pour ce champ.
"""


class CNIExtractionError(Exception):
    """Erreur métier levée quand l'extraction CNI échoue de façon définitive."""


@dataclass
class CNIExtractionResult:
    data: dict = field(default_factory=dict)
    raw_model_output: Optional[str] = None
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"success": True, "data": self.data, "warnings": self.warnings}


def _encode_image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise CNIExtractionError(f"Fichier introuvable : {image_path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type not in ("image/jpeg", "image/png", "image/webp"):
        raise CNIExtractionError(
            f"Format d'image non supporté pour '{path.name}' (détecté: {mime_type})."
        )

    if path.stat().st_size > 20 * 1024 * 1024:
        raise CNIExtractionError(f"Image trop volumineuse : '{path.name}' dépasse 20 Mo.")

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _build_user_content(image_paths: list[str]) -> list[dict]:
    if len(image_paths) == 1:
        instruction = (
            "Voici l'image de la CNI (recto, ou recto+verso sur une seule image). "
            "Extrais les informations demandées."
        )
    elif len(image_paths) == 2:
        instruction = (
            "Voici deux images de la même CNI : la première est le RECTO, "
            "la seconde est le VERSO. Fusionne les informations des deux faces "
            "en un seul objet JSON."
        )
    else:
        raise CNIExtractionError(
            f"Nombre d'images invalide : attendu 1 ou 2, reçu {len(image_paths)}."
        )

    content: list[dict] = [{"type": "text", "text": instruction}]
    for image_path in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": _encode_image_to_data_url(image_path)},
        })
    return content


def _validate_and_normalize(parsed: dict) -> tuple[dict, list]:
    warnings = []
    normalized = {}
    for key in CNI_SCHEMA_KEYS:
        value = parsed.get(key, None)
        if isinstance(value, str):
            value = value.strip() or None
        normalized[key] = value
        if key not in parsed:
            warnings.append(f"Champ manquant dans la réponse du modèle : '{key}'")
    unexpected = set(parsed.keys()) - set(CNI_SCHEMA_KEYS)
    if unexpected:
        warnings.append(f"Champs inattendus ignorés : {sorted(unexpected)}")
    return normalized, warnings


def extract_cni(image_paths: list[str], api_key: Optional[str] = None) -> dict:
    """Extrait les infos d'une CNI (1 image, ou 2 pour recto/verso) via Qwen/Groq."""
    if not image_paths:
        raise CNIExtractionError("Aucune image fournie.")

    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise CNIExtractionError("Clé API Groq manquante (GROQ_API_KEY).")

    client = Groq(api_key=key)
    user_content = _build_user_content(image_paths)

    last_error: Optional[Exception] = None
    raw_output = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=CNI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": CNI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_completion_tokens=2048,
                top_p=1,
                stream=False,
                response_format={"type": "json_object"},
                timeout=REQUEST_TIMEOUT_SECONDS,
                reasoning_effort="none",
            )
            raw_output = completion.choices[0].message.content
            logger.info("Réponse brute Qwen : %r", raw_output)
            break
        except RateLimitError as exc:
            last_error = exc
            wait = RETRY_BASE_DELAY_SECONDS * attempt
            logger.warning("Groq rate limit (tentative %s/%s), retry dans %ss", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
        except APIConnectionError as exc:
            last_error = exc
            wait = RETRY_BASE_DELAY_SECONDS * attempt
            logger.warning("Connexion Groq échouée (tentative %s/%s), retry dans %ss", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
        except APIError as exc:
            raise CNIExtractionError(f"Erreur API Groq : {exc}") from exc
    else:
        raise CNIExtractionError(f"Échec après {MAX_RETRIES} tentatives : {last_error}") from last_error

    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CNIExtractionError(f"Réponse du modèle non exploitable : {exc}\nBrut : {raw_output!r}") from exc

    if not isinstance(parsed, dict):
        raise CNIExtractionError(f"Réponse du modèle inattendue : {parsed!r}")

    normalized, warnings = _validate_and_normalize(parsed)
    return CNIExtractionResult(data=normalized, raw_model_output=raw_output, warnings=warnings).to_dict()


# ----------------------------------------------------------------------------
# Plan Processor: Gemini-Based Extraction
# ----------------------------------------------------------------------------
class PlanProcessor:
    """Extraction du plan de localisation via Gemini."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_plan_data(self, image_path: str) -> Dict[str, Any]:
        prompt = """Tu es un expert en extraction de données manuscrites pour des documents bancaires.
Analyse l'image de ce plan de localisation et extrais les informations suivantes sous forme de JSON strict.
Si une information est manquante ou illisible, mets une chaîne vide "".
Ne rajoute aucun texte avant ou après le JSON, pas de balises markdown.

FORMAT JSON ATTENDU :
{
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
}"""
        return self.llm_client.call_gemini_multimodal(prompt, [image_path])


# ----------------------------------------------------------------------------
# OCR Server: Flask API
# ----------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

config = ServerConfig()
llm_client = LLMClient(config)
plan_processor = PlanProcessor(llm_client)


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "message": "AccountOCR Professional API (Qwen + Gemini)",
        "version": "6.4",
    })

def _cni_keys_to_camel_case(data: dict) -> dict:
    mapping = {
        "nom": "nom",
        "prenoms": "prenom",
        "date_naissance": "dateNaissance",
        "lieu_naissance": "lieuNaissance",
        "date_expiration": "dateExpiration",
        "nom_pere": "nomPere",
        "nom_mere": "nomMere",
        "profession": "profession",
        "numero_cni": "numeroCNI",
        "date_delivrance": "dateDelivrance",
    }
    return {mapping[k]: v for k, v in data.items() if k in mapping}


@app.route("/extraire-tout", methods=["POST"])
def extraire_tout():
    """
    Endpoint principal : extrait la CNI (Qwen/Groq) et le plan (Gemini).
    Attend un ou plusieurs fichiers pour 'cni' et un fichier pour 'plan'.
    """
    if "cni" not in request.files or "plan" not in request.files:
        return jsonify({"erreur": "Les fichiers 'cni' et 'plan' sont requis"}), 400

    fichiers_cni = request.files.getlist("cni")
    fichier_plan = request.files["plan"]

    temp_paths = []
    try:
        # 1. Sauvegarde des images CNI (1 = recto seul/recto+verso réunis, 2 = recto+verso séparés)
        cni_paths = []
        for f in fichiers_cni:
            suffix = os.path.splitext(f.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                f.save(tmp.name)
                cni_paths.append(tmp.name)
                temp_paths.append(tmp.name)

        # 2. Sauvegarde de l'image du plan
        suffix_plan = os.path.splitext(fichier_plan.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_plan) as tmp_plan:
            fichier_plan.save(tmp_plan.name)
            plan_path = tmp_plan.name
            temp_paths.append(plan_path)

        # A. Extraction CNI (Qwen/Groq)
        logger.info("Extraction CNI (%s image(s)) via Qwen/Groq...", len(cni_paths))
        cni_result = extract_cni(cni_paths)

        # B. Extraction du plan (Gemini)
        logger.info("Extraction du plan via Gemini...")
        plan_data = plan_processor.extract_plan_data(plan_path)

        final_data = {**_cni_keys_to_camel_case(cni_result["data"]), **plan_data}

        return jsonify({
            "succes": True,
            "champs": final_data,
            "avertissements_cni": cni_result.get("warnings", []),
        })

    except CNIExtractionError as exc:
        logger.error("Erreur extraction CNI : %s", exc)
        return jsonify({"erreur": str(exc)}), 422

    except Exception as e:
        logger.error("Erreur pipeline : %s", e)
        traceback.print_exc()
        return jsonify({"erreur": str(e)}), 500

    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except Exception:
                pass


@app.route("/debug", methods=["POST"])
def debug_ocr():
    """Test direct multimodal Gemini pour une seule image."""
    if "fichier" not in request.files:
        return jsonify({"erreur": "Aucun fichier fourni"}), 400

    f = request.files["fichier"]
    suffix = os.path.splitext(f.filename)[1] or ".jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        f.save(tmp.name)
        path = tmp.name

    try:
        res = llm_client.call_gemini_multimodal("Décris cette image brièvement", [path])
        return jsonify({"resultat": res})
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    logger.info("AccountOCR Professional API starting...")
    logger.info("Server available at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)