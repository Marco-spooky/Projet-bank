from __future__ import annotations

import os
import json
import time
import logging
import tempfile
import traceback
import mimetypes
import sqlite3
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from functools import wraps

import base64
import zipfile
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import google.generativeai as genai
import num2words
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from groq import Groq, APIError, APIConnectionError, RateLimitError
from werkzeug.security import generate_password_hash, check_password_hash
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
        request_options={"timeout": 180},
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
d'une photo de Carte Nationale d'Identité (CNI) camerounaise (une face à la fois : \
recto seul, verso seul, ou recto+verso réunis sur une même image).

Examine ATTENTIVEMENT l'image, y compris les champs en petits caractères comme les \
dates (date de naissance, date de délivrance, date d'expiration), qui peuvent être \
imprimées en plus petit ou moins contrastées que le nom et le prénom.

Pour chaque champ demandé : s'il n'apparaît pas sur cette image (par exemple parce \
que c'est l'autre face de la carte qui le contient), renvoie null pour ce champ — \
une autre image sera analysée séparément pour le retrouver le cas échéant. Ne devine \
jamais une valeur que tu ne peux pas lire clairement.

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


def _build_user_content_single(image_path: str) -> list[dict]:
    return [
        {"type": "text", "text": "Voici une image d'une CNI (ou d'une face de CNI). Extrais les informations demandées."},
        {"type": "image_url", "image_url": {"url": _encode_image_to_data_url(image_path)}},
    ]


def _call_qwen_extraction(user_content: list[dict], key: str) -> str:
    """Appelle Qwen/Groq avec retries, pour UN message (une ou plusieurs images). Renvoie le JSON brut."""
    client = Groq(api_key=key)
    last_error: Optional[Exception] = None
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
            return raw_output
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
    raise CNIExtractionError(f"Échec après {MAX_RETRIES} tentatives : {last_error}") from last_error


def _parse_and_normalize_raw(raw_output: str) -> tuple[dict, list]:
    try:
        parsed = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CNIExtractionError(f"Réponse du modèle non exploitable : {exc}\nBrut : {raw_output!r}") from exc
    if not isinstance(parsed, dict):
        raise CNIExtractionError(f"Réponse du modèle inattendue : {parsed!r}")
    return _validate_and_normalize(parsed)


def _fusionner_resultats_cni(resultats: list[dict]) -> tuple[dict, list]:
    """Fusionne plusieurs dicts normalisés : pour chaque champ, garde la première valeur non-nulle trouvée."""
    fusion = {key: None for key in CNI_SCHEMA_KEYS}
    warnings: list = []
    for resultat in resultats:
        for key in CNI_SCHEMA_KEYS:
            if fusion[key] is None and resultat.get(key) is not None:
                fusion[key] = resultat[key]
    return fusion, warnings


def extract_cni(image_paths: list[str], api_key: Optional[str] = None) -> dict:
    """Extrait les infos d'une CNI. Avec 2 images (recto/verso), fait UN APPEL PAR IMAGE
    (au lieu d'un seul appel multi-images) puis fusionne les résultats — Qwen/Groq ayant
    tendance à ne traiter fiablement que la dernière image d'un message multi-images."""
    if not image_paths:
        raise CNIExtractionError("Aucune image fournie.")

    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise CNIExtractionError("Clé API Groq manquante (GROQ_API_KEY).")

    if len(image_paths) == 1:
        raw_output = _call_qwen_extraction(_build_user_content_single(image_paths[0]), key)
        normalized, warnings = _parse_and_normalize_raw(raw_output)
        return CNIExtractionResult(data=normalized, raw_model_output=raw_output, warnings=warnings).to_dict()

    if len(image_paths) != 2:
        raise CNIExtractionError(
            f"Nombre d'images invalide : attendu 1 ou 2, reçu {len(image_paths)}."
        )

    # 2 images : un appel Groq indépendant par image, puis fusion en Python
    resultats_normalises = []
    tous_warnings: list = []
    for i, image_path in enumerate(image_paths, start=1):
        raw_output = _call_qwen_extraction(_build_user_content_single(image_path), key)
        normalized, warnings = _parse_and_normalize_raw(raw_output)
        resultats_normalises.append(normalized)
        tous_warnings.extend(f"[image {i}] {w}" for w in warnings)

    fusion, _ = _fusionner_resultats_cni(resultats_normalises)
    return CNIExtractionResult(data=fusion, raw_model_output=None, warnings=tous_warnings).to_dict()


# ----------------------------------------------------------------------------
# Plan Processor: Gemini-Based Extraction
# ----------------------------------------------------------------------------
class PlanProcessor:
    """Extraction du plan de localisation via Gemini."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_plan_data(self, image_paths: list[str]) -> Dict[str, Any]:
        if len(image_paths) == 1:
            instruction_images = (
                "Tu recevras UNE SEULE image de la fiche client (recto seul, ou recto+verso "
                "réunis sur une même image)."
            )
        elif len(image_paths) == 2:
            instruction_images = (
                "Tu recevras DEUX images de la même fiche client : la première est le RECTO, "
                "la seconde est le VERSO. Tu dois FUSIONNER les informations trouvées sur les "
                "deux faces en un seul objet JSON — chaque information ne se trouve en général "
                "que sur une seule des deux faces, remplis chaque champ avec la valeur trouvée "
                "quelle que soit la face où elle apparaît."
            )
        else:
            raise ValueError(f"Nombre d'images invalide pour la fiche client : attendu 1 ou 2, reçu {len(image_paths)}.")

        prompt = f"""Tu es un expert en extraction de données manuscrites pour des documents bancaires.
{instruction_images}
Analyse la ou les image(s) de cette fiche client (plan de localisation + informations complémentaires)
et extrais TOUTES les informations suivantes sous forme de JSON strict.
Si une information est manquante ou illisible, mets une chaîne vide "".
Ne rajoute aucun texte avant ou après le JSON, pas de balises markdown.

La fiche contient à la fois des champs à texte libre (écrits à la main) et des champs
à CASES À COCHER (le client coche une case parmi plusieurs choix). Pour les champs à cases
à cocher, identifie précisément quelle case est cochée (croix, coche, case remplie ou
entourée) et renvoie EXACTEMENT la valeur correspondante listée ci-dessous pour ce champ
(orthographe, accents et majuscules identiques). Si aucune case n'est cochée ou si c'est
ambigu, renvoie une chaîne vide "".

FORMAT JSON ATTENDU :
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
  "contact2Tel2": "",
  "nomEntreprise": "",
  "nomEmployeur": "",
  "dateEmbauche": "",
  "salaire": "",
  "periodiciteRevenu": "",
  "nomEpoux": "",
  "personnesCharge": "",
  "situationMatrimoniale": "",
  "regimeMatrimonial": "",
  "communauteBiens": "",
  "situationImmobiliere": "",
  "agenceBase": "",
  "autreCompteCCA": "",
  "compte1Numero": "",
  "compte1Intitule": "",
  "compte2Numero": "",
  "compte2Intitule": ""
}}

RÈGLES POUR LES CHAMPS À CASES À COCHER (valeurs autorisées EXACTES) :
- "periodiciteRevenu" : une seule valeur parmi "MENSUEL", "TRIMESTRIEL", "SEMESTRIEL", "ANNUEL"
- "situationMatrimoniale" : une seule valeur parmi "CÉLIBATAIRE", "MARIÉ(E)", "DIVORCÉ(E)", "VEUF(VE)"
- "regimeMatrimonial" : une seule valeur parmi "MONOGAMIE", "POLYGAMIE", "NON CONCERNÉ"
- "communauteBiens" : une seule valeur parmi "BIENS COMMUNS", "BIENS SÉPARÉS"
- "situationImmobiliere" : une seule valeur parmi "LOCATAIRE", "PROPRIÉTAIRE", "FAMILLE D'ACCUEIL"
- "autreCompteCCA" : une seule valeur parmi "OUI", "NON"

RÈGLES POUR LES AUTRES CHAMPS :
- "dateEmbauche" et "datePlan" au format JJ/MM/AAAA si lisible.
- "salaire" en chiffres uniquement, sans espace ni "FCFA" (ex: "150000").
- "personnesCharge" en chiffres uniquement (ex: "2").
- "compte1Numero"/"compte1Intitule"/"compte2Numero"/"compte2Intitule" ne sont utiles que si
  "autreCompteCCA" vaut "OUI" ; sinon laisse-les vides.
- Ne devine jamais une case cochée que tu ne peux pas identifier avec certitude."""
        return self.llm_client.call_gemini_multimodal(prompt, image_paths)


# ----------------------------------------------------------------------------
# AUTHENTIFICATION : base SQLite locale (portable avec le projet)
# ----------------------------------------------------------------------------
# Chemin RELATIF au fichier server.py -> reste valide peu importe la machine
# ou le disque dur sur lequel le projet est copié.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accountocr.db")

MIN_PASSWORD_LENGTH = 6
TOKEN_BYTES = 32


def get_db() -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec les lignes accessibles par nom de colonne."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Crée les tables users / sessions et gère les migrations de colonnes."""
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE,
                mot_de_passe_hash TEXT NOT NULL,
                date_creation TEXT NOT NULL,
                role TEXT DEFAULT 'CSO'
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date_creation TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL,
                zip_path TEXT NOT NULL,
                date_archivage TEXT NOT NULL,
                created_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                endpoint TEXT,
                error_message TEXT,
                traceback TEXT,
                user_id INTEGER,
                status_code INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            """
        )

        # Migration pour les anciennes versions de la DB
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'CSO'")
        except sqlite3.OperationalError:
            pass # Colonne déjà présente

        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_activity TEXT")
        except sqlite3.OperationalError:
            pass # Colonne déjà présente

        conn.commit()
        logger.info("Base SQLite prête (%s)", DB_PATH)
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normaliser_nom(nom: str) -> str:
    """Nettoie le nom pour la comparaison (espaces + casse), sans le modifier à l'affichage."""
    return " ".join((nom or "").strip().split()).lower()


def creer_session(user_id: int) -> str:
    token = secrets.token_hex(TOKEN_BYTES)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO sessions (token, user_id, date_creation, last_activity) VALUES (?, ?, ?, ?)",
            (token, user_id, _now_iso(), _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def update_activity(token: str) -> None:
    """Met à jour la date de dernière activité pour prolonger la session."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE sessions SET last_activity = ? WHERE token = ?",
            (_now_iso(), token),
        )
        conn.commit()
    finally:
        conn.close()


def utilisateur_depuis_token(token: str) -> Optional[sqlite3.Row]:
    if not token:
        return None
    conn = get_db()
    try:
        # 1. Récupération de la session et de l'utilisateur
        row = conn.execute(
            """
            SELECT users.id, users.nom, users.role, sessions.last_activity
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()

        if not row:
            return None

        # 2. Vérification du timeout (30 minutes)
        try:
            last_act = datetime.fromisoformat(row["last_activity"])
            now = datetime.now(timezone.utc)
            diff = (now - last_act).total_seconds()
            if diff > 30 * 60:
                logger.info("Session expirée pour l'utilisateur %s (inactivité > 30min)", row["nom"])
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
        except (ValueError, TypeError) as exc:
            logger.warning("Erreur format date activité : %s", exc)
            return None

        # 3. Mise à jour de l'activité
        update_activity(token)

        return row
    finally:
        conn.close()


def _extraire_token() -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    # tolère aussi un header simple "X-Auth-Token" si jamais utilisé
    return request.headers.get("X-Auth-Token")


def require_admin(f):
    """Décorateur : protège une route, exige un rôle ADMIN."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extraire_token()
        user = utilisateur_depuis_token(token)
        if not user:
            return jsonify({"erreur": "Non authentifié. Merci de vous reconnecter."}), 401
        if user.get("role") != "ADMIN":
            return jsonify({"erreur": "Accès refusé. Privilèges administrateur requis."}), 403
        g.user_id = user["id"]
        g.user_nom = user["nom"]
        g.user_role = user["role"]
        return f(*args, **kwargs)
    return wrapper

def require_auth(f):
    """Décorateur : protège une route, exige un token de session valide."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extraire_token()
        user = utilisateur_depuis_token(token)
        if not user:
            return jsonify({"erreur": "Non authentifié. Merci de vous reconnecter."}), 401
        g.user_id = user["id"]
        g.user_nom = user["nom"]
        g.user_role = user["role"]
        return f(*args, **kwargs)
    return wrapper


def generate_client_pdf(data: dict, pdf_path: str):
    """Génère une fiche client PDF professionnelle via reportlab."""
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.hexColor("#002147"), alignment=1, spaceAfter=12)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.white, backColor=colors.hexColor("#002147"), alignment=0, spaceBefore=12, spaceAfter=6, leftIndent=0, borderPadding=4)
    label_style = ParagraphStyle('LabelStyle', parent=styles['Normal'], fontSize=9, textColor=colors.hexColor("#003366"), fontName='Helvetica-Bold')
    value_style = ParagraphStyle('ValueStyle', parent=styles['Normal'], fontSize=10, textColor=colors.black)

    elements = []

    # Header
    elements.append(Paragraph("FICHE D'OUVERTURE DE COMPTE", title_style))
    elements.append(Paragraph(f"CCA BANK - Document Confidentiel - {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, alignment=1, spaceAfter=20)))

    def add_section(title, fields):
        elements.append(Paragraph(title, section_style))
        table_data = []
        for i in range(0, len(fields), 2):
            row = []
            for j in range(2):
                if i + j < len(fields):
                    f_key, f_label = fields[i + j]
                    val = data.get(f_key, "—")
                    row.append([Paragraph(f"<b>{f_label}</b>", label_style), Paragraph(str(val), value_style)])
                else:
                    row.append(["", ""])
            table_data.append(row)

        # On aplatit la structure pour reportlab Table
        flattened_table = []
        for r in table_data:
            row_cells = []
            for cell in r:
                if isinstance(cell, list):
                    row_cells.extend(cell)
                else:
                    row_cells.append(cell)
            flattened_table.append(row_cells)

        t = Table(flattened_table, colWidths=[100, 150, 100, 150])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # Sections
    add_section("IDENTITÉ (CNI)", [
        ("nom", "Nom"), ("prenom", "Prénoms"),
        ("dateNaissance", "Date Naissance"), ("lieuNaissance", "Lieu Naissance"),
        ("nomPere", "Nom Père"), ("nomMere", "Nom Mère"),
        ("profession", "Profession"), ("dateExpiration", "Expiration CNI"),
        ("dateDelivrance", "Délivrance"), ("numeroCNI", "N° CNI")
    ])

    add_section("LOCALISATION", [
        ("ville", "Ville"), ("quartier", "Quartier"),
        ("tel1", "Tél 1"), ("tel2", "Tél 2"),
        ("email", "Email"), ("datePlan", "Date Plan")
    ])

    add_section("PERSONNES À CONTACTER", [
        ("contact1Nom", "Contact 1 Nom"), ("contact1Tel1", "Contact 1 Tél 1"),
        ("contact2Nom", "Contact 2 Nom"), ("contact2Tel1", "Contact 2 Tél 1"),
    ])

    add_section("INFORMATIONS COMPLÉMENTAIRES", [
        ("nomEntreprise", "Entreprise"), ("nomEmployeur", "Employeur"),
        ("dateEmbauche", "Date Embauche"), ("salaire", "Salaire"),
        ("periodiciteRevenu", "Périodicité"), ("situationMatrimoniale", "Statut Matri."),
        ("regimeMatrimonial", "Régime"), ("communauteBiens", "Communauté"),
        ("situationImmobiliere", "Immobilier"), ("agenceBase", "Agence")
    ])

    # Compte et Services
    elements.append(Paragraph("SOUSTRIPTIONS", section_style))
    compte_info = f"Type : {data.get('compteTypeLabel', '—')} / {data.get('compteSousTypeLabel', '—')}"
    elements.append(Paragraph(compte_info, value_style))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("Services Obligatoires :", label_style))
    services_ob = ", ".join(data.get("servicesObligatoires", []))
    elements.append(Paragraph(services_ob or "—", value_style))

    elements.append(Paragraph("Services Facultatifs :", label_style))
    services_fac = ", ".join(data.get("servicesFacultatifsChoisis", []))
    elements.append(Paragraph(services_fac or "—", value_style))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Déclaration : Je certifie l'exactitude des informations fournies.", ParagraphStyle('Legal', parent=styles['Normal'], fontSize=8, italic=True)))

    doc.build(elements)

def create_client_zip(cni_b64: list[str], plan_b64: list[str], pdf_path: str, zip_name: str) -> str:
    """Crée un ZIP contenant les images CNI, Plan et le PDF généré."""
    zip_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archives")
    os.makedirs(zip_dir, exist_ok=True)
    zip_full_path = os.path.join(zip_dir, zip_name)

    with zipfile.ZipFile(zip_full_path, 'w') as zipf:
        # PDF
        zipf.write(pdf_path, os.path.basename(pdf_path))

        # CNI Images
        for i, b64 in enumerate(cni_b64):
            img_data = base64.b64decode(b64.split(",")[-1])
            zipf.writestr(f"CNI_face_{i+1}.jpg", img_data)

        # Plan Images
        for i, b64 in enumerate(plan_b64):
            img_data = base64.b64decode(b64.split(",")[-1])
            zipf.writestr(f"Plan_face_{i+1}.jpg", img_data)

    return zip_full_path

# ----------------------------------------------------------------------------
# OCR Server: Flask API
# ----------------------------------------------------------------------------
app = Flask(__name__)

CORS(app)

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler to mask technical details from the client and log them to DB."""
    if isinstance(e, HTTPException):
        # Let HTTP exceptions (like 404, 405) pass through but ensure JSON response
        return jsonify({"erreur": e.description}), e.code

    # 1. Log the full traceback for the admin (Railway logs)
    logger.error("Unhandled Exception occurred: %s\n%s", str(e), traceback.format_exc())

    # 2. Save to system_errors table in SQLite
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO system_errors (timestamp, endpoint, error_message, traceback, user_id, status_code) VALUES (?, ?, ?, ?, ?, ?)",
            (_now_iso(), request.path, str(e), traceback.format_exc(), getattr(g, "user_id", None), 500)
        )
        conn.commit()
        conn.close()
    except Exception as db_err:
        logger.error("Failed to log error to database: %s", db_err)

    # Return a sanitized message to the client
    return jsonify({"erreur": "Une erreur interne est survenue. Veuillez contacter l'administrateur."}), 500

config = ServerConfig()
llm_client = LLMClient(config)
plan_processor = PlanProcessor(llm_client)

init_db()


@app.route("/admin/logs", methods=["GET"])
@require_admin
def get_admin_logs():
    """Récupère les erreurs système pour l'administrateur."""
    conn = get_db()
    try:
        # On récupère les erreurs les plus récentes en premier
        rows = conn.execute(
            "SELECT id, timestamp, endpoint, error_message, traceback, user_id, status_code FROM system_errors ORDER BY timestamp DESC"
        ).fetchall()
        return jsonify({
            "succes": True,
            "logs": [dict(row) for row in rows]
        })
    finally:
        conn.close()

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "message": "AccountOCR Professional API (Qwen + Gemini)",
        "version": "6.4",
    })


# ----------------------------------------------------------------------------
# Routes d'authentification
# ----------------------------------------------------------------------------
@app.route("/inscription", methods=["POST"])
def inscription():
    payload = request.get_json(silent=True) or {}
    nom = (payload.get("nom") or "").strip()
    mot_de_passe = payload.get("motDePasse") or ""

    if not nom:
        return jsonify({"erreur": "Le nom est requis."}), 400
    if len(mot_de_passe) < MIN_PASSWORD_LENGTH:
        return jsonify({"erreur": f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."}), 400

    nom_normalise = _normaliser_nom(nom)
    conn = get_db()
    try:
        existe = conn.execute(
            "SELECT id FROM users WHERE LOWER(nom) = ?", (nom_normalise,)
        ).fetchone()
        if existe:
            return jsonify({"erreur": "Ce nom est déjà utilisé. Essayez de vous connecter."}), 409

        mot_de_passe_hash = generate_password_hash(mot_de_passe)
        cursor = conn.execute(
            "INSERT INTO users (nom, mot_de_passe_hash, date_creation, role) VALUES (?, ?, ?, ?)",
            (nom, mot_de_passe_hash, _now_iso(), 'CSO'),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()

    token = creer_session(user_id)
    logger.info("Nouveau CSO inscrit : %s", nom)
    return jsonify({"succes": True, "token": token, "nom": nom}), 201


@app.route("/connexion", methods=["POST"])
def connexion():
    payload = request.get_json(silent=True) or {}
    nom = (payload.get("nom") or "").strip()
    mot_de_passe = payload.get("motDePasse") or ""

    if not nom or not mot_de_passe:
        return jsonify({"erreur": "Nom et mot de passe requis."}), 400

    nom_normalise = _normaliser_nom(nom)
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, nom, mot_de_passe_hash FROM users WHERE LOWER(nom) = ?",
            (nom_normalise,),
        ).fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user["mot_de_passe_hash"], mot_de_passe):
        return jsonify({"erreur": "Nom ou mot de passe incorrect."}), 401

    token = creer_session(user["id"])
    logger.info("Connexion CSO : %s", user["nom"])
    return jsonify({"succes": True, "token": token, "nom": user["nom"], "role": user["role"]})


@app.route("/deconnexion", methods=["POST"])
def deconnexion():
    token = _extraire_token()
    if token:
        conn = get_db()
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()
    return jsonify({"succes": True})


@app.route("/verifier-session", methods=["GET"])
def verifier_session():
    token = _extraire_token()
    user = utilisateur_depuis_token(token)
    if not user:
        return jsonify({"erreur": "Session invalide ou expirée."}), 401
    return jsonify({"succes": True, "nom": user["nom"], "role": user["role"]})


@app.route("/archiver", methods=["POST"])
@require_auth
def archiver():
    """Génère le PDF, crée le ZIP et enregistre l'archive en DB."""
    payload = request.get_json(silent=True) or {}
    data = payload.get("data")
    cni_images = payload.get("cni_images", [])
    plan_images = payload.get("plan_images", [])

    if not data or not cni_images or not plan_images:
        return jsonify({"erreur": "Données et images manquantes pour l'archivage."}), 400

    try:
        # 1. Nommage de l'archive
        client_nom = (data.get("nom") or "Client").replace(" ", "_").upper()
        compte_type = (data.get("compteTypeLabel") or "Inconnu").replace(" ", "_")
        date_str = datetime.now().strftime("%Y-%m-%d")
        zip_name = f"{client_nom}-{compte_type}-By_{g.user_nom}-{date_str}.zip"

        # 2. Génération PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            pdf_path = tmp_pdf.name

        generate_client_pdf(data, pdf_path)

        # 3. Création ZIP
        zip_full_path = create_client_zip(cni_images, plan_images, pdf_path, zip_name)

        # Nettoyage PDF temp
        os.remove(pdf_path)

        # 4. Enregistrement en DB
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO archives (reference, zip_path, date_archivage, created_by) VALUES (?, ?, ?, ?)",
                (f"{client_nom} - {compte_type}", zip_name, _now_iso(), g.user_nom),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info("Archive créée avec succès : %s [CSO: %s]", zip_name, g.user_nom)
        return jsonify({"succes": True, "zip_name": zip_name})

    except Exception as e:
        logger.error("Erreur archivage : %s\n%s", str(e), traceback.format_exc())
        raise e


@app.route("/archives", methods=["GET"])
@require_auth
def list_archives():
    """Liste toutes les archives."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM archives ORDER BY date_archivage DESC").fetchall()
        return jsonify({
            "succes": True,
            "archives": [dict(row) for row in rows]
        })
    finally:
        conn.close()


@app.route("/download-archive/<filename>", methods=["GET"])
@require_auth
def download_archive(filename):
    """Sert le fichier ZIP de l'archive."""
    from flask import send_from_directory
    archive_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archives")
    return send_from_directory(archive_dir, filename)


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
@require_auth
def extraire_tout():
    """
    Endpoint principal : extrait la CNI (Qwen/Groq) et le plan (Gemini).
    Attend un ou plusieurs fichiers pour 'cni' et un fichier pour 'plan'.
    Protégé : nécessite un token de session valide (CSO connecté).
    """
    if "cni" not in request.files or "plan" not in request.files:
        return jsonify({"erreur": "Les fichiers 'cni' et 'plan' sont requis"}), 400

    fichiers_cni = request.files.getlist("cni")
    fichiers_plan = request.files.getlist("plan")

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

        # 2. Sauvegarde des images de la fiche client (1 = recto seul/recto+verso réunis, 2 = recto+verso séparés)
        plan_paths = []
        for f in fichiers_plan:
            suffix = os.path.splitext(f.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                f.save(tmp.name)
                plan_paths.append(tmp.name)
                temp_paths.append(tmp.name)

        # A. Extraction CNI (Qwen/Groq)
        logger.info("Extraction CNI (%s image(s)) via Qwen/Groq... [CSO: %s]", len(cni_paths), g.user_nom)
        cni_result = extract_cni(cni_paths)

        # B. Extraction de la fiche client (Gemini)
        logger.info("Extraction de la fiche client (%s image(s)) via Gemini...", len(plan_paths))
        plan_data = plan_processor.extract_plan_data(plan_paths)

        # Normalisation en majuscules et conversion du salaire
        processed_plan_data = {}
        for k, v in plan_data.items():
            val = str(v).upper() if v else ""
            processed_plan_data[k] = val

        # Conversion salaire chiffres -> lettres
        salaire_val = plan_data.get("salaire", "").strip()
        if salaire_val and salaire_val.isdigit():
            try:
                processed_plan_data["salaireLettres"] = num2words.num2words(int(salaire_val), lang='fr').capitalize()
            except Exception as e:
                logger.error("Erreur conversion salaire en lettres : %s", e)
                processed_plan_data["salaireLettres"] = ""
        else:
            processed_plan_data["salaireLettres"] = ""

        final_data = {**_cni_keys_to_camel_case(cni_result["data"]), **processed_plan_data}

        # Anti-False Positive Validation: Check for mandatory identity fields
        mandatory_fields = ["nom", "prenom", "numeroCNI"]
        is_valid = all(final_data.get(field) and str(final_data.get(field)).strip() for field in mandatory_fields)

        if not is_valid:
            return jsonify({"erreur": "L'image de la CNI est illisible ou incomplète. Veuillez fournir une image plus claire."}), 422

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
        # We raise the exception to let the global @app.errorhandler handle it and mask it
        raise e

    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except Exception:
                pass


@app.route("/debug", methods=["POST"])
@require_auth
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
        logger.error("Erreur debug OCR : %s", e)
        raise e
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    logger.info("AccountOCR Professional API starting...")

    # On récupère le port de Railway, sinon 5000
    port = int(os.environ.get("PORT", 5000))

    # Sur Railway, on désactive le mode debug pour éviter les conflits de proxy
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") is not None
    debug_mode = False if is_production else True

    logger.info("Server starting on host 0.0.0.0, port %s (Debug: %s)", port, debug_mode)

    try:
        app.run(host="0.0.0.0", port=port, debug=debug_mode)
    except Exception as e:
        logger.error("CRITICAL ERROR during server startup: %s", e)
        traceback.print_exc()