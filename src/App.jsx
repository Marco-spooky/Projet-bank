import { useState, useRef, useEffect, createContext, useContext } from "react";

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
    imprimer: "Imprimer la fiche client",
    choixCompte: "Choix du compte →", choixCompteTitre: "Choix du Compte",
    selectionnerCompte: "Sélectionnez le type de compte",
    voirServices: "Voir les services →",
    erreurServeur: "Serveur OCR non connecté. Lancez server.py.",
    erreurExtraction: "Erreur lors de l'extraction.",
    champsObl: "Champ obligatoire",
    infosCSOManuelles: "Informations complémentaires",
    infosCSOManuelleSub: "Ces informations sont à collecter auprès du client.",
    retour: "←", etape1: "Compte", etape2: "Extraction",
    etape3: "Services", etape4: "Récapitulatif",
    nonRenseigne: "Non renseigné", importerFichiers: "Importez les 2 fichiers d'abord",
    verifierChamps: "Vérifiez et corrigez si nécessaire",
    serveurOK: "Serveur connecté", serveurKO: "Serveur déconnecté",
    // Nouveau : catégorie / type / sous-type / services
    categorieTitre: "Type de Clientèle",
    selectionnerCategorie: "Sélectionnez le type de clientèle",
    particulierBtn: "Comptes Particuliers",
    particulierDesc: "Personnes physiques",
    entrepriseBtn: "Comptes Entreprises",
    entrepriseDesc: "Personnes morales",
    typeCompteTitre: "Type de Compte",
    selectionnerType: "Sélectionnez le type de compte",
    sousTypeTitre: "Formule",
    selectionnerSousType: "Sélectionnez la formule",
    servicesTitre: "Services & Produits",
    compteSouscrit: "Compte souscrit",
    servicesObligatoiresLabel: "Services obligatoires (inclus automatiquement)",
    servicesFacultatifsLabel: "Services facultatifs — à proposer au client",
    aucunFacultatif: "Aucun service facultatif sélectionné",
    terminerBtn: "Terminer ✅",
    voirRecap: "Voir le récapitulatif →",
    // Authentification
    loginTitre: "Connexion",
    nomComplet: "Nom complet",
    motDePasse: "Mot de passe",
    motDePasseConfirmer: "Confirmer le mot de passe",
    seConnecter: "Se connecter",
    sInscrire: "S'inscrire",
    pasDeCompte: "Pas encore de compte ? S'inscrire",
    dejaCompte: "Déjà un compte ? Se connecter",
    motDePasseMinLength: "Le mot de passe doit contenir au moins 6 caractères.",
    motDePasseNonIdentiques: "Les mots de passe ne correspondent pas.",
    champsRequis: "Merci de remplir tous les champs.",
    connexionEnCours: "Connexion...",
    inscriptionEnCours: "Inscription...",
    deconnecter: "Déconnexion",
    verificationSession: "Vérification de la session...",
    bienvenueConnexion: "Connectez-vous pour accéder à AccountOCR",
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
    retour: "←", etape1: "Account", etape2: "Extraction",
    etape3: "Services", etape4: "Summary",
    nonRenseigne: "Not provided", importerFichiers: "Import both files first",
    verifierChamps: "Check and correct if needed",
    serveurOK: "Server connected", serveurKO: "Server disconnected",
    categorieTitre: "Client Type",
    selectionnerCategorie: "Select the client type",
    particulierBtn: "Individual Accounts",
    particulierDesc: "Individuals",
    entrepriseBtn: "Business Accounts",
    entrepriseDesc: "Legal entities",
    typeCompteTitre: "Account Type",
    selectionnerType: "Select the account type",
    sousTypeTitre: "Formula",
    selectionnerSousType: "Select the formula",
    servicesTitre: "Services & Products",
    compteSouscrit: "Selected account",
    servicesObligatoiresLabel: "Mandatory services (included automatically)",
    servicesFacultatifsLabel: "Optional services — to offer the client",
    aucunFacultatif: "No optional service selected",
    terminerBtn: "Finish ✅",
    voirRecap: "See summary →",
    // Authentication
    loginTitre: "Login",
    nomComplet: "Full name",
    motDePasse: "Password",
    motDePasseConfirmer: "Confirm password",
    seConnecter: "Log in",
    sInscrire: "Sign up",
    pasDeCompte: "No account yet? Sign up",
    dejaCompte: "Already have an account? Log in",
    motDePasseMinLength: "Password must be at least 6 characters.",
    motDePasseNonIdentiques: "Passwords do not match.",
    champsRequis: "Please fill in all fields.",
    connexionEnCours: "Logging in...",
    inscriptionEnCours: "Signing up...",
    deconnecter: "Log out",
    verificationSession: "Checking session...",
    bienvenueConnexion: "Log in to access AccountOCR",
  },
};

// ============================================================
// ICÔNES PERSONNALISÉES (remplacent les emojis)
// ============================================================
const ICON_PATHS = {
  particulier: <><circle cx="12" cy="8" r="3.4" /><path d="M4.5 20c0-4 3.4-6.8 7.5-6.8s7.5 2.8 7.5 6.8" /></>,
  entreprise: <><rect x="4" y="9" width="6" height="11" /><rect x="13" y="4" width="7" height="16" /><path d="M6 12v.01M6 15v.01M6 18v.01M16 7v.01M16 10v.01M16 13v.01M16 16v.01" /></>,
  carte: <><rect x="2.5" y="6" width="19" height="13" rx="2.2" /><path d="M2.5 10.2h19" /><path d="M6 14.6h4.5" /></>,
  cartePrivilege: <><rect x="2.5" y="6.5" width="19" height="13" rx="2.2" /><path d="M2.5 10.7h19" /><path d="M6 15.1h3.5" /><path d="M17.2 4.4l.7 1.5 1.6.2-1.2 1.1.3 1.6-1.4-.8-1.4.8.3-1.6-1.2-1.1 1.6-.2z" strokeLinejoin="round" /></>,
  piggy: <><path d="M4.5 12.2c0-3 2.7-5.2 6.4-5.2h3.6c1 0 1.9.3 2.6.8l1.6-.8.7.9-1.3 1.2c.5.8.7 1.7.6 2.6-.2 2.7-3 4.6-6.4 4.6H11c-3.6 0-6.5-2.2-6.5-4.1z" /><circle cx="15.3" cy="10.6" r=".6" fill="white" stroke="none" /><path d="M8 16.5v2M13.2 16.5v2" /><path d="M4.6 11.3l-2-.9" /></>,
  gift: <><rect x="3.5" y="10" width="17" height="10" rx="1.2" /><path d="M3.5 13.6h17" /><path d="M12 10v10" /><path d="M12 10c-1.3-3-5-3.6-5-1.3 0 1 1 1.3 1.9 1.3m3.1 0c1.3-3 5-3.6 5-1.3 0 1-1 1.3-1.9 1.3" /></>,
  crown: <><path d="M4 18.5h16l-1.1-8.3-4 3.2-2.9-6.3-2.9 6.3-4-3.2z" strokeLinejoin="round" /><path d="M4 18.5h16v1.6H4z" /></>,
  globe: <><circle cx="12" cy="12" r="8.2" /><path d="M3.8 12h16.4" /><path d="M12 3.8c2.6 2.6 2.6 13.8 0 16.4M12 3.8c-2.6 2.6-2.6 13.8 0 16.4" /></>,
  graduation: <><path d="M2 9.3L12 5l10 4.3-10 4.3-10-4.3z" strokeLinejoin="round" /><path d="M6.2 11.3v4.6c0 1.6 2.9 3 5.8 3s5.8-1.4 5.8-3v-4.6" /><path d="M21.5 9.3v6" /></>,
  shield: <path d="M12 3.2l7.3 3.1v5.6c0 5-3.1 8.2-7.3 9.1-4.2-.9-7.3-4.1-7.3-9.1V6.3z" strokeLinejoin="round" />,
  briefcase: <><rect x="3" y="8.2" width="18" height="11" rx="1.4" /><path d="M3 12.6h18" /><path d="M9 8.2V6.4c0-.5.4-.9.9-.9h4.2c.5 0 .9.4.9.9v1.8" /></>,
};

function IconBadge({ name, size = 52, dark }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%", flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg,#3B0764,#6B21A8)",
      boxShadow: dark ? "0 0 0 1px rgba(168,85,247,0.25)" : "0 2px 6px rgba(59,7,100,0.25)",
    }}>
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        {ICON_PATHS[name] || ICON_PATHS.carte}
      </svg>
    </div>
  );
}

// ============================================================
// STRUCTURE DES COMPTES / SERVICES
// ============================================================
const ACCOUNT_STRUCTURE = {
  particulier: {
    label: { fr: "Comptes Particuliers", en: "Individual Accounts" },
    types: [
      {
        key: "compte_courant",
        label: { fr: "Compte Courant", en: "Current Account" },
        icon: "carte",
        hasSubtypes: true,
        subtypes: [
          {
            key: "basic", label: { fr: "Basic", en: "Basic" }, icon: "carte",
            obligatoires: ["Carte GIMAC Équilibre", "C-Online (E-banking)", "C-Mobile (Alerte SMS)", "B2W (Bank to Wallet)"],
            facultatifs: ["Carnet de chèques supplémentaires", "Assurance moyens de paiement"],
          },
          {
            key: "confort", label: { fr: "Confort", en: "Confort" }, icon: "carte",
            obligatoires: ["Carte GIMAC Cauris", "C-Online (E-banking)", "C-Mobile (Alerte SMS)", "B2W (Bank to Wallet)"],
            facultatifs: ["Assurance découverts / Crédit scolaire", "Services de virement permanent"],
          },
          {
            key: "serenite", label: { fr: "Sérénité", en: "Serenity" }, icon: "carte",
            obligatoires: ["Carte GIMAC Équilibre / Cauris", "C-Online", "C-Mobile", "Moving Money / B2W"],
            facultatifs: ["Carte Visa supplémentaire", "Bancassurance étendue"],
          },
          {
            key: "privilege", label: { fr: "Privilège", en: "Privilege" }, icon: "cartePrivilege",
            obligatoires: ["Carte Visa Classic (ou GIMAC)", "C-Online", "C-Mobile / C-Alert", "B2W & Services prioritaires"],
            facultatifs: ["Carte Visa Gold/Prestige", "Services de gestion de patrimoine"],
          },
        ],
      },
      {
        key: "epargne_classique",
        label: { fr: "Compte Épargne Classique", en: "Classic Savings Account" },
        icon: "piggy",
        hasSubtypes: false,
        obligatoires: ["Livret d'épargne", "Rémunération des intérêts (2.45% à 2.75%)"],
        facultatifs: ["Carte de retrait GIMAC", "Accès C-Online / C-Mobile", "Prélèvements automatiques"],
      },
      {
        key: "packs_specifiques",
        label: { fr: "Packs Spécifiques", en: "Specific Packs" },
        icon: "gift",
        hasSubtypes: true,
        subtypes: [
          {
            key: "first_lady", label: { fr: "First Lady (Femmes & Entrepreneures)", en: "First Lady (Women & Entrepreneurs)" }, icon: "crown",
            obligatoires: ["Chéquier / Livret d'épargne gratuit", "Carte Débit First Lady Club", "Pack Digital (C-Online + C-Mobile + B2W)", "Adhésion au CCA First Ladies' Club"],
            facultatifs: ["Micro-Assurance Santé Maternelle", "Crédit/Accompagnement Entrepreneuriat Féminin", "Cartes Visa Classic / Gold"],
          },
          {
            key: "diaspo", label: { fr: "Diaspo (Camerounais de l'étranger)", en: "Diaspo (Cameroonians abroad)" }, icon: "globe",
            obligatoires: ["Compte Courant ou Épargne souscrit à distance", "Carte Visa Classic / Platinum (obligatoire — paiements internationaux)", "Pack Digital complet (C-Online, B2W)"],
            facultatifs: ["Service de Conciergerie VIP", "Prêt Immobilier / Projet d'investissement au pays", "Transfert de fonds automatique à la famille"],
          },
          {
            key: "junior_starter", label: { fr: "Junior / Starter (Étudiants & Jeunes)", en: "Junior / Starter (Students & Youth)" }, icon: "graduation",
            obligatoires: ["Ouverture dès 1 000 FCFA", "Carte de Débit GIMAC / Visa Starter", "Accès aux canaux digitaux C-Mobile / B2W"],
            facultatifs: ["Option Épargne projet / Micro-crédit d'études", "Relevés 100% dématérialisés"],
          },
          {
            key: "veteran", label: { fr: "Veteran (Retraités & Seniors)", en: "Veteran (Retirees & Seniors)" }, icon: "shield",
            obligatoires: ["Gestion de pension de retraite", "Carte GIMAC Équilibre / Visa", "Service d'alerte virement pension (C-Mobile)"],
            facultatifs: ["Assurance Décès / Obsèques", "Avance sur pension de retraite"],
          },
        ],
      },
    ],
  },
  entreprise: {
    label: { fr: "Comptes Entreprises", en: "Business Accounts" },
    types: [
      {
        key: "compte_courant_entreprise",
        label: { fr: "Compte Courant Commercial / Entreprise", en: "Commercial / Business Current Account" },
        icon: "entreprise",
        hasSubtypes: true,
        subtypes: [
          {
            key: "pme", label: { fr: "PME", en: "SME" }, icon: "entreprise",
            obligatoires: ["Attestation de domiciliation bancaire", "Chéquier Commercial", "Tenue de compte Entreprise"],
            facultatifs: ["Plateforme C-Cash (Gestion de trésorerie / Paie des salaires)", "E-Banking Entreprise (C-Online / C-Mobile)", "Carte Visa Corporate / Prestige", "Terminal de Paiement Électronique (TPE)", "Services de virement en masse & Télécompensation", "Engagements par signature (Garanties bancaires, Cautionnements)"],
          },
          {
            key: "pmi", label: { fr: "PMI", en: "SMI" }, icon: "entreprise",
            obligatoires: ["Attestation de domiciliation bancaire", "Chéquier Commercial", "Tenue de compte Entreprise"],
            facultatifs: ["Plateforme C-Cash (Gestion de trésorerie / Paie des salaires)", "E-Banking Entreprise (C-Online / C-Mobile)", "Carte Visa Corporate / Prestige", "Terminal de Paiement Électronique (TPE)", "Services de virement en masse & Télécompensation", "Engagements par signature (Garanties bancaires, Cautionnements)"],
          },
          {
            key: "ge", label: { fr: "Grande Entreprise (GE)", en: "Large Enterprise" }, icon: "entreprise",
            obligatoires: ["Attestation de domiciliation bancaire", "Chéquier Commercial", "Tenue de compte Entreprise"],
            facultatifs: ["Plateforme C-Cash (Gestion de trésorerie / Paie des salaires)", "E-Banking Entreprise (C-Online / C-Mobile)", "Carte Visa Corporate / Prestige", "Terminal de Paiement Électronique (TPE)", "Services de virement en masse & Télécompensation", "Engagements par signature (Garanties bancaires, Cautionnements)"],
          },
        ],
      },
      {
        key: "pack_first_lady_business",
        label: { fr: "Pack First Lady Business / Établissement / Starter Business", en: "First Lady Business / Establishment / Starter Business Pack" },
        icon: "briefcase",
        hasSubtypes: true,
        subtypes: [
          {
            key: "first_lady_business", label: { fr: "First Lady Business", en: "First Lady Business" }, icon: "crown",
            obligatoires: ["Carnet de chèques", "Carte GIMAC / Visa Business", "Service C-Online"],
            facultatifs: ["Service C-Mobile (SMS)", "Solutions de paiement Mobile B2W", "Crédit / Avance sur facture"],
          },
          {
            key: "etablissement", label: { fr: "Établissement", en: "Establishment" }, icon: "entreprise",
            obligatoires: ["Carnet de chèques", "Carte GIMAC / Visa Business", "Service C-Online"],
            facultatifs: ["Service C-Mobile (SMS)", "Solutions de paiement Mobile B2W", "Crédit / Avance sur facture"],
          },
          {
            key: "starter_business", label: { fr: "Starter Business", en: "Starter Business" }, icon: "graduation",
            obligatoires: ["Carnet de chèques", "Carte GIMAC / Visa Business", "Service C-Online"],
            facultatifs: ["Service C-Mobile (SMS)", "Solutions de paiement Mobile B2W", "Crédit / Avance sur facture"],
          },
        ],
      },
    ],
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

// Champs complémentaires (texte libre) — extraits par Gemini depuis la fiche client
const CHAMPS_COMPL_TEXTE = [
  { key: "nomEntreprise", label: "Nom de l'entreprise (si applicable)" },
  { key: "nomEmployeur", label: "Nom de l'employeur (si applicable)" },
  { key: "dateEmbauche", label: "Date d'embauche / début d'activité" },
  { key: "salaire", label: "Salaire (FCFA)" },
  { key: "nomEpoux", label: "Nom de l'époux/épouse" },
  { key: "personnesCharge", label: "Nombre de personnes à charge" },
  { key: "agenceBase", label: "Agence de base" },
];

const CHAMPS_COMPL_COMPTES = [
  { key: "compte1Numero", label: "Compte 1 — N°" },
  { key: "compte1Intitule", label: "Compte 1 — Intitulé" },
  { key: "compte2Numero", label: "Compte 2 — N°" },
  { key: "compte2Intitule", label: "Compte 2 — Intitulé" },
];

// Champs complémentaires (cases à cocher) — extraits par Gemini depuis la fiche client
const CHOIX_COMPL = [
  { key: "periodiciteRevenu", label: "Périodicité de revenu", options: ["MENSUEL", "TRIMESTRIEL", "SEMESTRIEL", "ANNUEL"] },
  { key: "situationMatrimoniale", label: "Situation matrimoniale", options: ["CÉLIBATAIRE", "MARIÉ(E)", "DIVORCÉ(E)", "VEUF(VE)"] },
  { key: "regimeMatrimonial", label: "Régime matrimonial", options: ["MONOGAMIE", "POLYGAMIE", "NON CONCERNÉ"] },
  { key: "communauteBiens", label: "Communauté de biens", options: ["BIENS COMMUNS", "BIENS SÉPARÉS"] },
  { key: "situationImmobiliere", label: "Situation immobilière", options: ["LOCATAIRE", "PROPRIÉTAIRE", "FAMILLE D'ACCUEIL"] },
  { key: "autreCompteCCA", label: "Avez-vous un autre compte au CCA ?", options: ["OUI", "NON"] },
];

// ============================================================
// LOCALSTORAGE
// ============================================================
const LS_DONNEES = "accountocr_donnees";
const LS_PAGE = "accountocr_page";
const LS_COMPTES_JOUR = "accountocr_comptes_jour";
const LS_DATE = "accountocr_date";
const LS_TOKEN = "accountocr_token";
const LS_NOM = "accountocr_nom";
const API_URL = import.meta.env.VITE_API_URL || "https://projet-bank-production.up.railway.app";

function sauvegarder(donnees, page) {
  try { localStorage.setItem(LS_DONNEES, JSON.stringify(donnees)); localStorage.setItem(LS_PAGE, page); } catch (e) { console.error("AccountOCR: échec sauvegarde localStorage", e); }
}
function charger() {
  try {
    const d = localStorage.getItem(LS_DONNEES);
    const p = localStorage.getItem(LS_PAGE);
    return { donnees: d ? JSON.parse(d) : {}, page: p || "dashboard" };
  } catch (e) { console.error("AccountOCR: échec lecture localStorage", e); return { donnees: {}, page: "dashboard" }; }
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
  } catch (e) { console.error("AccountOCR: échec lecture compteur", e); return 0; }
}
function incrementerComptesJour() {
  try {
    const n = getComptesJour() + 1;
    localStorage.setItem(LS_COMPTES_JOUR, String(n));
    return n;
  } catch (e) { console.error("AccountOCR: échec incrémentation compteur", e); return 0; }
}

// ============================================================
// CONTEXT AUTHENTIFICATION
// ============================================================
const AuthContext = createContext({ csoNom: "", token: null, deconnexion: () => { } });

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
      style={{ height: 56, objectFit: "contain" }}
    />
  );
}

// ============================================================
// HEADER
// ============================================================
function Header({ titre, onRetour, dark, setDark, langue, setLangue, t, serveurOK }) {
  const { csoNom, deconnexion } = useContext(AuthContext);
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
          {/* CSO connecté */}
          {csoNom && (
            <div className="flex items-center gap-1.5">
              <div className="hidden sm:flex items-center gap-2 bg-white/10 px-3 py-1.5 rounded-lg">
                <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                <span className="text-xs font-bold text-white truncate max-w-[120px]">{csoNom}</span>
              </div>
              <button onClick={deconnexion} title={t.deconnecter}
                className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/10 hover:bg-white/25 text-white transition-all flex-shrink-0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3v8" />
                  <path d="M6.5 6.5a8 8 0 1 0 11 0" />
                </svg>
              </button>
            </div>
          )}

          {/* Indicateur serveur */}
          <div className={`hidden sm:flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${serveurOK ? "bg-green-500/25 text-green-300" : "bg-red-500/25 text-red-300"
            }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${serveurOK ? "bg-green-400" : "bg-red-400"}`} />
            {serveurOK ? t.serveurOK : t.serveurKO}
          </div>

          {/* Langue */}
          <button onClick={() => setLangue(langue === "fr" ? "en" : "fr")}
            className="text-xs font-bold text-purple-200 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-all">
            {langue === "fr" ? "🇬🇧 EN" : "🇫🇷 FR"}
          </button>

          {/* Dark/Light */}
          <button onClick={() => setDark(!dark)}
            className="text-xs font-bold text-purple-200 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-all">
            {dark ? "☀️" : "🌙"}
          </button>

          {/* Logo CCA BANK à droite en gros */}
          <LogoCCABank />
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
// PAGE LOGIN / INSCRIPTION
// ============================================================
function PageLogin({ onConnecte, dark, setDark, langue, setLangue, t }) {
  const [mode, setMode] = useState("connexion"); // "connexion" | "inscription"
  const [nom, setNom] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [motDePasseConfirm, setMotDePasseConfirm] = useState("");
  const [erreur, setErreur] = useState("");
  const [enCours, setEnCours] = useState(false);

  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const inputCls = `w-full px-4 py-3 rounded-xl border-2 text-sm outline-none transition-all ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`;

  const soumettre = async (e) => {
    e.preventDefault();
    setErreur("");

    if (!nom.trim() || !motDePasse) {
      setErreur(t.champsRequis);
      return;
    }
    if (motDePasse.length < 6) {
      setErreur(t.motDePasseMinLength);
      return;
    }
    if (mode === "inscription" && motDePasse !== motDePasseConfirm) {
      setErreur(t.motDePasseNonIdentiques);
      return;
    }

    setEnCours(true);
    try {
      const route = mode === "inscription" ? "/inscription" : "/connexion";
      const res = await fetch(`${API_URL}${route}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nom: nom.trim(), motDePasse }),
      });
      const data = await res.json();
      if (!res.ok || !data.succes) {
        throw new Error(data.erreur || t.erreurServeur);
      }
      onConnecte(data.token, data.nom);
    } catch (err) {
      setErreur(err.message?.includes("fetch") || err.message?.includes("Failed") ? t.erreurServeur : err.message);
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <div className="sticky top-0 z-20" style={{ background: dark ? "linear-gradient(90deg,#1a0533,#2d0a5e)" : "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
        <div className="flex items-center justify-between gap-3 px-5 h-14 max-w-md mx-auto">
          <div className="flex items-center gap-2">
            <LogoAccountOCR />
            <div className="text-white font-black text-base leading-none">{t.appName}</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setLangue(langue === "fr" ? "en" : "fr")}
              className="text-xs font-bold text-purple-200 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-all">
              {langue === "fr" ? "🇬🇧 EN" : "🇫🇷 FR"}
            </button>
            <button onClick={() => setDark(!dark)}
              className="text-xs font-bold text-purple-200 hover:text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-all">
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-5">
        <div className={`w-full max-w-md rounded-2xl shadow-sm border p-6 ${card}`}>
          <div className="flex flex-col items-center gap-3 mb-6">
            <LogoAccountOCR />
            <div className="text-center">
              <h1 className={`text-lg font-black ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.loginTitre}</h1>
              <p className={`text-xs mt-1 ${dark ? "text-gray-400" : "text-gray-500"}`}>{t.bienvenueConnexion}</p>
            </div>
          </div>

          {/* Onglets */}
          <div className={`flex rounded-xl p-1 mb-5 ${dark ? "bg-gray-800" : "bg-purple-50"}`}>
            {["connexion", "inscription"].map(m => (
              <button key={m} type="button" onClick={() => { setMode(m); setErreur(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-bold transition-all ${mode === m ? "text-white" : dark ? "text-gray-400" : "text-purple-400"}`}
                style={mode === m ? { background: "linear-gradient(90deg,#3B0764,#6B21A8)" } : {}}>
                {m === "connexion" ? t.seConnecter : t.sInscrire}
              </button>
            ))}
          </div>

          <form onSubmit={soumettre}>
            <div className="mb-4">
              <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>{t.nomComplet}</label>
              <input value={nom} onChange={e => setNom(e.target.value)} placeholder className={inputCls} autoComplete="name" />
            </div>

            <div className="mb-4">
              <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>{t.motDePasse}</label>
              <input type="password" value={motDePasse} onChange={e => setMotDePasse(e.target.value)} placeholder="••••••" className={inputCls}
                autoComplete={mode === "inscription" ? "new-password" : "current-password"} />
            </div>

            {mode === "inscription" && (
              <div className="mb-4">
                <label className={`block text-xs font-bold uppercase tracking-wide mb-1.5 ${dark ? "text-gray-400" : "text-gray-600"}`}>{t.motDePasseConfirmer}</label>
                <input type="password" value={motDePasseConfirm} onChange={e => setMotDePasseConfirm(e.target.value)} placeholder="••••••" className={inputCls} autoComplete="new-password" />
              </div>
            )}

            {erreur && <div className="bg-red-50 border border-red-200 rounded-xl p-3 mb-4 text-xs text-red-700 font-semibold">⚠️ {erreur}</div>}

            <button type="submit" disabled={enCours}
              className="w-full py-3 rounded-xl font-bold text-white text-sm transition-all"
              style={{ background: enCours ? (dark ? "#1f0a3d" : "#D1D5DB") : "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
              {enCours ? (mode === "inscription" ? t.inscriptionEnCours : t.connexionEnCours) : (mode === "inscription" ? t.sInscrire : t.seConnecter)}
            </button>
          </form>

          <button onClick={() => { setMode(mode === "connexion" ? "inscription" : "connexion"); setErreur(""); }}
            className={`w-full text-center text-xs font-semibold mt-4 ${dark ? "text-purple-400 hover:text-purple-300" : "text-purple-600 hover:text-purple-800"}`}>
            {mode === "connexion" ? t.pasDeCompte : t.dejaCompte}
          </button>
        </div>
      </div>
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
// PAGE CATÉGORIE (Particulier / Entreprise)
// ============================================================
function PageCategorie({ onRetour, onSelect, dark, setDark, langue, setLangue, t, serveurOK }) {
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const categories = [
    { key: "particulier", label: t.particulierBtn, desc: t.particulierDesc, icon: "particulier" },
    { key: "entreprise", label: t.entrepriseBtn, desc: t.entrepriseDesc, icon: "entreprise" },
  ];
  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.categorieTitre} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={1} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.selectionnerCategorie}</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-400"}`}>Cliquez sur la catégorie souhaitée.</p>
          <div className="grid grid-cols-2 gap-3">
            {categories.map(c => (
              <button key={c.key} onClick={() => onSelect(c.key)}
                className={`flex flex-col items-center gap-3 p-6 rounded-xl border-2 font-bold text-sm transition-all ${dark ? "border-gray-700 bg-gray-800 text-purple-300 hover:border-purple-600" : "border-purple-100 bg-white text-purple-800 hover:border-purple-500"}`}>
                <IconBadge name={c.icon} size={56} dark={dark} />
                <span>{c.label}</span>
                <span className={`text-xs font-normal ${dark ? "text-gray-500" : "text-gray-400"}`}>{c.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// PAGE TYPE DE COMPTE (selon la catégorie)
// ============================================================
function PageTypeCompte({ categorie, onRetour, onSelectType, dark, setDark, langue, setLangue, t, serveurOK, langueActuelle }) {
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const groupe = ACCOUNT_STRUCTURE[categorie];
  if (!groupe) return null;
  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={groupe.label[langueActuelle]} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={1} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.selectionnerType}</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-400"}`}>{groupe.label[langueActuelle]}</p>
          <div className="grid grid-cols-1 gap-3">
            {groupe.types.map(type => (
              <button key={type.key} onClick={() => onSelectType(type)}
                className={`flex items-center gap-3 p-4 rounded-xl border-2 font-bold text-sm text-left transition-all ${dark ? "border-gray-700 bg-gray-800 text-purple-300 hover:border-purple-600" : "border-purple-100 bg-white text-purple-800 hover:border-purple-500"}`}>
                <IconBadge name={type.icon} size={44} dark={dark} />
                <span className="flex-1">{type.label[langueActuelle]}</span>
                <span className={dark ? "text-gray-600" : "text-gray-300"}>→</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// PAGE SOUS-TYPE (formule / pack)
// ============================================================
function PageSousType({ categorie, typeKey, onRetour, onSelectSubtype, dark, setDark, langue, setLangue, t, serveurOK, langueActuelle }) {
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const groupe = ACCOUNT_STRUCTURE[categorie];
  const type = groupe?.types.find(ty => ty.key === typeKey);
  if (!type) return null;
  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={type.label[langueActuelle]} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={1} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.selectionnerSousType}</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-400"}`}>{type.label[langueActuelle]}</p>
          <div className="grid grid-cols-1 gap-3">
            {type.subtypes.map(sub => (
              <button key={sub.key} onClick={() => onSelectSubtype(sub)}
                className={`flex items-center gap-3 p-4 rounded-xl border-2 font-bold text-sm text-left transition-all ${dark ? "border-gray-700 bg-gray-800 text-purple-300 hover:border-purple-600" : "border-purple-100 bg-white text-purple-800 hover:border-purple-500"}`}>
                <IconBadge name={sub.icon} size={44} dark={dark} />
                <span className="flex-1">{sub.label[langueActuelle]}</span>
                <span className={dark ? "text-gray-600" : "text-gray-300"}>→</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// PAGE EXTRACTION
// ============================================================
function PageExtraction({ onRetour, onContinuer, dark, setDark, langue, setLangue, t, serveurOK, donneesInitiales }) {
  const { token, deconnexion } = useContext(AuthContext);
  const [fichiersCNI, setFichiersCNI] = useState([]);
  const [fichiersPlan, setFichiersPlan] = useState([]);
  const [enCours, setEnCours] = useState(false);
  const [progression, setProgression] = useState(0);
  const [etape, setEtape] = useState("");
  const [termine, setTermine] = useState(false);
  const [donnees, setDonnees] = useState(donneesInitiales || {});
  const [erreur, setErreur] = useState("");

  const estIncertain = (val) => !val || val.trim() === "" || val.toLowerCase().includes("[illisible]");

  const refCNI = useRef();
  const refPlan = useRef();
  const peutExtraire = fichiersCNI.length > 0 && fichiersPlan.length > 0 && !enCours && !termine && serveurOK;
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";

  // Empêche une fermeture/actualisation accidentelle qui tuerait la requête en cours
  useEffect(() => {
    if (!enCours) return;
    const avertir = (e) => { e.preventDefault(); e.returnValue = ""; return ""; };
    window.addEventListener("beforeunload", avertir);
    return () => window.removeEventListener("beforeunload", avertir);
  }, [enCours]);


  const lancerExtraction = async () => {
    setEnCours(true); setErreur(""); setProgression(0); setTermine(false);
    try {
      setEtape("envoi"); setProgression(15);
      const formData = new FormData();
      fichiersCNI.forEach(file => formData.append("cni", file));
      fichiersPlan.forEach(file => formData.append("plan", file));
      setEtape("traitement"); setProgression(40);
      const response = await fetch(`${API_URL}/extraire-tout`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });
      setProgression(85);
      if (response.status === 401) {
        deconnexion();
        throw new Error("Session expirée, merci de vous reconnecter.");
      }
      if (!response.ok) throw new Error(`Erreur serveur: ${response.status}`);
      const data = await response.json();
      setProgression(100);
      if (data.succes && data.champs) {
        const fusion = { ...donnees, ...data.champs };
        setDonnees(fusion);
        sauvegarder(fusion, "extraction");
        setTermine(true);
      } else throw new Error(data.erreur || t.erreurExtraction);
    } catch (e) {
      setErreur(e.message.includes("fetch") || e.message.includes("Failed") ? t.erreurServeur : e.message);
    } finally { setEnCours(false); setEtape(""); }
  };

  const msgEtape = etape === "envoi" ? "📤 Envoi des fichiers..." : "🔍 Analyse en cours...";

  const MAX_IMAGES_PAR_DOCUMENT = 2;

  const ajouterFichiers = (nouveauxFichiers, fichiersActuels, setFichiers, keyStorage) => {
    if (!nouveauxFichiers.length) return; // sélection annulée par le CSO
    const fusion = [...fichiersActuels, ...nouveauxFichiers].slice(0, MAX_IMAGES_PAR_DOCUMENT);
    setFichiers(fusion);
    setTermine(false); setErreur("");
    fileToBase64(fusion[0]).then(b64 => localStorage.setItem(keyStorage, b64)).catch(err => console.error("Erreur storage", err));
  };

  const zoneImport = (fichiers, label, onClic, onEffacer) => {
    const hasFiles = Array.isArray(fichiers) ? fichiers.length > 0 : !!fichiers;
    const atteintMax = Array.isArray(fichiers) && fichiers.length >= MAX_IMAGES_PAR_DOCUMENT;
    const displayText = Array.isArray(fichiers)
      ? (fichiers.length > 1 ? `${fichiers.length} fichiers sélectionnés (${fichiers.map(f => f.name).join(", ")})` : (fichiers[0]?.name || "Aucun fichier"))
      : (fichiers ? fichiers.name : `Cliquer pour importer ${label === "CNI" ? "la CNI" : "le plan de localisation"}`);

    return (
      <div className="mb-3">
        <div onClick={!enCours && !atteintMax ? onClic : undefined}
          className={`rounded-xl border-2 border-dashed p-5 flex flex-col items-center justify-center transition-all ${(enCours || atteintMax) ? "cursor-not-allowed" : "cursor-pointer"} ${enCours ? "opacity-60" : ""} ${hasFiles ? dark ? "border-purple-600 bg-purple-950" : "border-purple-600 bg-purple-50" :
            dark ? "border-gray-700 bg-gray-800 hover:border-purple-600" : "border-purple-200 bg-purple-50 hover:border-purple-500"
            }`}>
          <span className="text-3xl mb-2">{hasFiles ? "✅" : label === "CNI" ? "🪪" : "📍"}</span>
          <span className={`text-sm font-bold text-center px-2 ${dark ? hasFiles ? "text-purple-300" : "text-purple-500" : hasFiles ? "text-purple-800" : "text-purple-400"}`}>
            {displayText}
          </span>
          {!hasFiles && <span className={`text-xs mt-1 ${dark ? "text-gray-500" : "text-gray-400"}`}>{t.importFormats}</span>}
          {hasFiles && !atteintMax && <span className={`text-xs mt-1 ${dark ? "text-gray-500" : "text-gray-400"}`}>Cliquer pour ajouter l'autre face (recto/verso)</span>}
        </div>
        {hasFiles && !enCours && (
          <button type="button" onClick={onEffacer} className={`text-xs font-semibold mt-1.5 ${dark ? "text-red-400 hover:text-red-300" : "text-red-500 hover:text-red-700"}`}>
            ✕ Effacer la sélection
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.extraction} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={2} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <h3 className={`font-bold mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>Importer les documents</h3>
          <p className={`text-xs mb-4 ${dark ? "text-gray-400" : "text-gray-500"}`}>JPG, PNG ou PDF — EasyOCR + IA analysent automatiquement. 1 image (recto+verso réunis) ou 2 images (recto puis verso séparément).</p>
          <input ref={refCNI} type="file" accept="image/*,.pdf" multiple className="hidden" onChange={e => {
            ajouterFichiers(Array.from(e.target.files), fichiersCNI, setFichiersCNI, "accountocr_img_cni");
            e.target.value = "";
          }} />
          {zoneImport(fichiersCNI, "CNI", () => refCNI.current.click(), () => { setFichiersCNI([]); setTermine(false); })}
          <input ref={refPlan} type="file" accept="image/*,.pdf" multiple className="hidden" onChange={e => {
            ajouterFichiers(Array.from(e.target.files), fichiersPlan, setFichiersPlan, "accountocr_img_plan");
            e.target.value = "";
          }} />
          {zoneImport(fichiersPlan, "Plan", () => refPlan.current.click(), () => { setFichiersPlan([]); setTermine(false); })}


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
              {!fichiersCNI.length || !fichiersPlan.length ? t.importerFichiers : !serveurOK ? t.serveurKO : t.lancerExtraction}
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

            <p className={`text-xs font-black uppercase tracking-widest mb-2 mt-4 ${dark ? "text-purple-500" : "text-purple-500"}`}>{t.infosCSO}</p>
            {CHAMPS_COMPL_TEXTE.map(c => (
              <div key={c.key} className="mb-2">
                <label className={`block text-xs font-bold uppercase tracking-wide mb-1 ${dark ? "text-purple-400" : "text-purple-600"}`}>{c.label}</label>
                <input value={donnees[c.key] || ""} onChange={e => setDonnees({ ...donnees, [c.key]: e.target.value })}
                  className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`} />
              </div>
            ))}

            {CHOIX_COMPL.map(c => (
              <GroupeChoix key={c.key} label={c.label} options={c.options}
                valeur={donnees[c.key]} onChange={v => setDonnees({ ...donnees, [c.key]: v })} dark={dark} />
            ))}

            {donnees.autreCompteCCA === "OUI" && (
              <div className={`rounded-xl p-4 mb-4 border ${dark ? "border-gray-700 bg-gray-800" : "border-purple-100 bg-purple-50"}`}>
                <p className={`text-xs font-bold mb-3 ${dark ? "text-purple-400" : "text-purple-700"}`}>Si OUI, le(s) quel(s) :</p>
                <div className="grid grid-cols-2 gap-2">
                  {CHAMPS_COMPL_COMPTES.map(c => (
                    <div key={c.key}>
                      <label className={`block text-xs font-bold mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>{c.label}</label>
                      <input value={donnees[c.key] || ""} onChange={e => setDonnees({ ...donnees, [c.key]: e.target.value })}
                        className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${dark ? "bg-gray-800 border-gray-700 text-gray-200 focus:border-purple-600" : "bg-purple-50 border-purple-100 text-gray-800 focus:border-purple-600"}`} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button onClick={() => onContinuer(donnees)}
              className="w-full mt-4 py-3 rounded-xl font-bold text-white text-sm"
              style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
              {t.continuer} → {t.etape3}
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
// PAGE SERVICES & PRODUITS
// ============================================================
function PageServices({ donnees, onRetour, onContinuer, dark, setDark, langue, setLangue, t, serveurOK, langueActuelle }) {
  const [choisis, setChoisis] = useState(donnees.servicesFacultatifsChoisis || []);
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";
  const obligatoires = donnees.servicesObligatoires || [];
  const facultatifs = donnees.servicesFacultatifsDisponibles || [];

  const toggle = (service) => {
    setChoisis(prev => prev.includes(service) ? prev.filter(s => s !== service) : [...prev, service]);
  };

  const nomCompte = [donnees.compteTypeLabel, donnees.compteSousTypeLabel].filter(Boolean).join(" — ");

  return (
    <div className="min-h-screen" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
      <Header titre={t.servicesTitre} onRetour={onRetour} dark={dark} setDark={setDark} langue={langue} setLangue={setLangue} t={t} serveurOK={serveurOK} />
      <EtapeIndicateur etape={3} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <p className={`text-xs font-bold uppercase tracking-wide mb-1 ${dark ? "text-purple-400" : "text-purple-500"}`}>{t.compteSouscrit}</p>
          <h3 className={`font-black text-lg ${dark ? "text-purple-300" : "text-purple-900"}`}>{nomCompte}</h3>
        </div>

        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <h3 className={`font-bold text-sm mb-3 ${dark ? "text-purple-300" : "text-purple-900"}`}>✅ {t.servicesObligatoiresLabel}</h3>
          <div className="flex flex-col gap-2">
            {obligatoires.map(s => (
              <div key={s} className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border ${dark ? "border-green-800 bg-green-900/20" : "border-green-200 bg-green-50"}`}>
                <span className="w-5 h-5 rounded-md bg-green-500 flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-xs font-black">✓</span>
                </span>
                <span className={`text-sm font-semibold ${dark ? "text-green-300" : "text-green-800"}`}>{s}</span>
              </div>
            ))}
          </div>
        </div>

        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <h3 className={`font-bold text-sm mb-1 ${dark ? "text-purple-300" : "text-purple-900"}`}>☑️ {t.servicesFacultatifsLabel}</h3>
          <p className={`text-xs mb-3 ${dark ? "text-gray-500" : "text-gray-400"}`}>Demandez l'avis du client avant de cocher.</p>
          <div className="flex flex-col gap-2">
            {facultatifs.map(s => {
              const selectionne = choisis.includes(s);
              return (
                <label key={s} onClick={() => toggle(s)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-all ${selectionne ? "border-purple-600" : dark ? "border-gray-700 bg-gray-800 hover:border-purple-600" : "border-purple-100 bg-purple-50 hover:border-purple-400"}`}
                  style={selectionne ? { background: dark ? "rgba(107,33,168,0.25)" : "#EDE9FF" } : {}}>
                  <span className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 ${selectionne ? "border-purple-600 bg-purple-600" : dark ? "border-gray-500" : "border-purple-300"}`}>
                    {selectionne && <span className="text-white text-xs font-black">✓</span>}
                  </span>
                  <span className={`text-sm font-semibold ${dark ? "text-gray-200" : "text-gray-800"}`}>{s}</span>
                </label>
              );
            })}
          </div>
          {choisis.length === 0 && <p className={`text-xs mt-3 italic ${dark ? "text-gray-600" : "text-gray-400"}`}>{t.aucunFacultatif}</p>}
        </div>

        <button onClick={() => onContinuer({ ...donnees, servicesFacultatifsChoisis: choisis })}
          className="w-full py-3.5 rounded-xl font-bold text-white text-sm shadow-lg"
          style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
          {t.voirRecap}
        </button>
      </div>
    </div>
  );
}

// ============================================================
// PAGE RÉCAPITULATIF + IMPRESSION
// ============================================================
function PageRecapitulatif({ onRetour, onTerminer, donnees, dark, setDark, langue, setLangue, t, serveurOK }) {
  const [toutCopie, setToutCopie] = useState(false);
  const imgCni = localStorage.getItem("accountocr_img_cni");
  const imgPlan = localStorage.getItem("accountocr_img_plan");
  const card = dark ? "bg-gray-900 border-gray-800" : "bg-white border-purple-100";

  const nomCompte = [donnees.compteTypeLabel, donnees.compteSousTypeLabel].filter(Boolean).join(" — ");
  const servicesObligatoires = donnees.servicesObligatoires || [];
  const servicesChoisis = donnees.servicesFacultatifsChoisis || [];

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
    lignes.push(`Compte souscrit: ${nomCompte || "—"}`);
    lignes.push(`Services obligatoires: ${servicesObligatoires.join(", ") || "—"}`);
    lignes.push(`Services facultatifs choisis: ${servicesChoisis.join(", ") || "—"}`);
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

        /* Liste de services */
        .service-list { display: flex; flex-direction: column; gap: 4px; }
        .service-item { display: flex; align-items: center; gap: 6px; font-size: 10px; padding: 3px 0; border-bottom: 1px solid #F3F4F6; }
        .service-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
        .service-dot.oblig { background: #059669; }
        .service-dot.fac { background: #6B21A8; }

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

        <div class="footer">RECTO — Page 1/2 — AccountOCR CCA BANK — ${date}</div>
      </div>

      <!-- ============ PAGE VERSO ============ -->
      <div class="page">
        <div class="header">
          <div class="header-left">
            <div class="header-title">📄 FICHE D'OUVERTURE DE COMPTE</div>
            <div class="header-sub">Suite — Compte souscrit & Services</div>
          </div>
          <div class="header-right">
            <div class="header-bank">CCA BANK</div>
            <div>Confidentiel — Usage interne</div>
          </div>
        </div>

        <!-- COMPTE SOUSCRIT -->
        <div class="section">
          <div class="section-title">Compte souscrit</div>
          <div class="champ"><div class="label">Type de compte</div><div class="valeur">${nomCompte || "—"}</div></div>
        </div>

        <!-- SERVICES -->
        <div class="section">
          <div class="section-title">Services obligatoires (inclus)</div>
          <div class="service-list">
            ${servicesObligatoires.length ? servicesObligatoires.map(s => `
              <div class="service-item"><span class="service-dot oblig"></span><span>${s}</span></div>
            `).join("") : `<div class="service-item">—</div>`}
          </div>
        </div>

        <div class="section">
          <div class="section-title">Services facultatifs sélectionnés</div>
          <div class="service-list">
            ${servicesChoisis.length ? servicesChoisis.map(s => `
              <div class="service-item"><span class="service-dot fac"></span><span>${s}</span></div>
            `).join("") : `<div class="service-item">Aucun service facultatif sélectionné</div>`}
          </div>
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
      <EtapeIndicateur etape={4} dark={dark} t={t} />
      <div className="p-5 max-w-2xl mx-auto">
        <div className={`rounded-2xl shadow-sm border p-5 mb-4 ${card}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className={`font-bold ${dark ? "text-purple-300" : "text-purple-900"}`}>{t.toutesInfos}</h3>
            <button onClick={copierTout} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${toutCopie ? "bg-green-500 text-white" :
              dark ? "bg-purple-900 text-purple-300 hover:bg-purple-700 hover:text-white" : "bg-purple-100 text-purple-700 hover:text-white"
              }`}>
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

          {/* Compte & Services */}
          <div className="mb-4">
            <p className={`text-xs font-black uppercase tracking-widest mb-2 ${dark ? "text-purple-500" : "text-purple-500"}`}>{t.compteSouscrit}</p>
            <div className={`rounded-xl p-3 mb-2 border ${dark ? "border-purple-900 bg-gray-800" : "border-purple-100 bg-purple-50"}`}>
              <span className={`text-sm font-bold ${dark ? "text-purple-300" : "text-purple-800"}`}>{nomCompte || t.nonRenseigne}</span>
            </div>
            <p className={`text-xs font-bold mt-3 mb-1 ${dark ? "text-green-400" : "text-green-700"}`}>{t.servicesObligatoiresLabel}</p>
            <div className="flex flex-wrap gap-2 mb-2">
              {servicesObligatoires.map(s => (
                <span key={s} className={`text-xs font-semibold px-2.5 py-1 rounded-full ${dark ? "bg-green-900/30 text-green-300" : "bg-green-100 text-green-700"}`}>{s}</span>
              ))}
            </div>
            <p className={`text-xs font-bold mt-3 mb-1 ${dark ? "text-purple-400" : "text-purple-700"}`}>{t.servicesFacultatifsLabel}</p>
            <div className="flex flex-wrap gap-2">
              {servicesChoisis.length ? servicesChoisis.map(s => (
                <span key={s} className={`text-xs font-semibold px-2.5 py-1 rounded-full ${dark ? "bg-purple-900/40 text-purple-300" : "bg-purple-100 text-purple-700"}`}>{s}</span>
              )) : <span className={`text-xs italic ${dark ? "text-gray-600" : "text-gray-400"}`}>{t.aucunFacultatif}</span>}
            </div>
          </div>

          {sections.map(s => (
            <div key={s.titre} className="mb-4">
              <p className={`text-xs font-black uppercase tracking-widest mb-2 ${dark ? "text-purple-500" : "text-purple-500"}`}>{s.titre}</p>
              {s.champs.map(c => {
                if (c.key === "salaire") {
                  return (
                    <div key={c.key} className="mb-2">
                      <ChampCopie label={c.label} valeur={donnees[c.key]} dark={dark} t={t} />
                      {donnees.salaireLettres && (
                        <div className={`text-[10px] italic pl-3 mb-2 ${dark ? "text-purple-400" : "text-purple-600"}`}>
                          En lettres : {donnees.salaireLettres}
                        </div>
                      )}
                    </div>
                  );
                }
                return <ChampCopie key={c.key} label={c.label} valeur={donnees[c.key]} dark={dark} t={t} />;
              })}
            </div>
          ))}
        </div>

        {/* Bouton imprimer */}
        <button onClick={imprimer}
          className="w-full py-3.5 rounded-xl font-bold text-white text-sm shadow-lg mb-3 flex items-center justify-center gap-2"
          style={{ background: "linear-gradient(90deg,#065F46,#059669)" }}>
          {t.imprimer}
        </button>

        <button onClick={onTerminer}
          className="w-full py-3.5 rounded-xl font-bold text-white text-sm shadow-lg"
          style={{ background: "linear-gradient(90deg,#3B0764,#6B21A8)" }}>
          {t.terminerBtn}
        </button>
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

  // ---- Authentification ----
  const [token, setToken] = useState(() => localStorage.getItem(LS_TOKEN) || null);
  const [csoNom, setCsoNom] = useState(() => localStorage.getItem(LS_NOM) || "");
  const [authChecking, setAuthChecking] = useState(true);

  useEffect(() => {
    console.log(
      "AccountOCR: démarrage — origine =", window.location.origin,
      "| comptesJour localStorage =", localStorage.getItem(LS_COMPTES_JOUR),
      "| date enregistrée =", localStorage.getItem(LS_DATE),
      "| aujourd'hui =", new Date().toDateString()
    );
  }, []);

  useEffect(() => {
    const verifierSession = async () => {
      const savedToken = localStorage.getItem(LS_TOKEN);
      if (!savedToken) { setAuthChecking(false); return; }
      try {
        const res = await fetch(`${API_URL}/verifier-session`, {
          headers: { "Authorization": `Bearer ${savedToken}` },
          signal: AbortSignal.timeout(4000),
        });
        const data = await res.json();
        if (res.ok && data.succes) {
          setToken(savedToken);
          setCsoNom(data.nom);
          localStorage.setItem(LS_NOM, data.nom);
        } else {
          localStorage.removeItem(LS_TOKEN); localStorage.removeItem(LS_NOM);
          setToken(null); setCsoNom("");
        }
      } catch (e) {
        // Serveur injoignable au démarrage : on garde la session locale,
        // elle sera revérifiée dès qu'une action nécessitera le serveur.
      } finally {
        setAuthChecking(false);
      }
    };
    verifierSession();
  }, []);

  const seConnecter = (newToken, nom) => {
    localStorage.setItem(LS_TOKEN, newToken);
    localStorage.setItem(LS_NOM, nom);
    setToken(newToken);
    setCsoNom(nom);
  };

  const deconnexion = () => {
    const savedToken = localStorage.getItem(LS_TOKEN);
    if (savedToken) {
      fetch(`${API_URL}/deconnexion`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${savedToken}` },
      }).catch(() => { });
    }
    localStorage.removeItem(LS_TOKEN); localStorage.removeItem(LS_NOM);
    localStorage.removeItem(LS_DONNEES); localStorage.removeItem(LS_PAGE);
    setToken(null); setCsoNom(""); setDonnees({}); setPage("dashboard");
  };

  useEffect(() => {
    const verifier = async () => {
      try {
        const res = await fetch(`${API_URL}/`, { signal: AbortSignal.timeout(2000) });
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

  const props = { dark, setDark, langue, setLangue, t, serveurOK, langueActuelle: langue };

  // ---- Écran de vérification de session ----
  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: dark ? "#0a0118" : "#F5F0FF" }}>
        <div className="flex flex-col items-center gap-3">
          <LogoAccountOCR />
          <p className={`text-xs font-semibold ${dark ? "text-gray-400" : "text-gray-500"}`}>{t.verificationSession}</p>
        </div>
      </div>
    );
  }

  // ---- Pas connecté : page de login ----
  if (!token) {
    return <PageLogin {...props} onConnecte={seConnecter} />;
  }

  return (
    <AuthContext.Provider value={{ csoNom, token, deconnexion }}>
      {(() => {
        if (page === "dashboard")
          return <PageDashboard {...props} comptesJour={comptesJour} onNouveauDossier={() => allerVers("categorie", {})} />;

        if (page === "categorie")
          return <PageCategorie {...props} onRetour={() => allerVers("dashboard")} onSelect={(cat) => allerVers("type", { ...donnees, compteCategorie: cat })} />;

        if (page === "type")
          return <PageTypeCompte {...props} categorie={donnees.compteCategorie}
            onRetour={() => allerVers("categorie")}
            onSelectType={(typeObj) => {
              if (typeObj.hasSubtypes) {
                allerVers("soustype", { ...donnees, compteType: typeObj.key, compteTypeLabel: typeObj.label[langue] });
              } else {
                allerVers("extraction", {
                  ...donnees,
                  compteType: typeObj.key, compteTypeLabel: typeObj.label[langue],
                  compteSousType: null, compteSousTypeLabel: null,
                  servicesObligatoires: typeObj.obligatoires,
                  servicesFacultatifsDisponibles: typeObj.facultatifs,
                  servicesFacultatifsChoisis: [],
                });
              }
            }} />;

        if (page === "soustype")
          return <PageSousType {...props} categorie={donnees.compteCategorie} typeKey={donnees.compteType}
            onRetour={() => allerVers("type")}
            onSelectSubtype={(sub) => allerVers("extraction", {
              ...donnees,
              compteSousType: sub.key, compteSousTypeLabel: sub.label[langue],
              servicesObligatoires: sub.obligatoires,
              servicesFacultatifsDisponibles: sub.facultatifs,
              servicesFacultatifsChoisis: [],
            })} />;

        if (page === "extraction")
          return <PageExtraction {...props} donneesInitiales={donnees}
            onRetour={() => allerVers(donnees.compteSousType ? "soustype" : "type")}
            onContinuer={d => allerVers("services", d)} />;

        if (page === "services")
          return <PageServices {...props} donnees={donnees} onRetour={() => allerVers("extraction")} onContinuer={d => allerVers("recap", d)} />;

        if (page === "recap")
          return <PageRecapitulatif {...props} donnees={donnees} onRetour={() => allerVers("services")} onTerminer={terminer} />;

        return null;
      })()}
    </AuthContext.Provider>
  );
}