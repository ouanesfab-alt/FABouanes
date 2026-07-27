# FABOuanes — ERP Mobile & Desktop (PostgreSQL 18 & HTTPS)

**FABOuanes** est une solution ERP de gestion commerciale ultra-rapide et sécurisée conçue pour les PME et commerces : facturation, ventes cash/crédit, suivi des stocks, comptabilité et assistant métier IA. Le projet combine un serveur **FastAPI** (PostgreSQL 18 + HTTPS automatique), une interface Web/PWA responsive et un assistant IA nommé **Sabrina** (Google Gemini & Ollama local).

![Version](https://img.shields.io/badge/version-2.0.5-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Database](https://img.shields.io/badge/database-PostgreSQL%2018-blue)
![Security](https://img.shields.io/badge/security-HTTPS%20SSL%2010yr-brightgreen)
![Tests](https://img.shields.io/badge/tests-541%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-78%25-green)

---

## ⚡ Démarrage Rapide

### 📱 1. Sur Smartphone Android (Termux Mobile)

Copiez-collez cette **seule commande** dans Termux pour tout installer et lancer automatiquement en mode 100 % hors-ligne (2 secondes chrono) :

```bash
pkg update && pkg upgrade -y && pkg install git -y && git clone https://github.com/ouanesfab-alt/FABouanes.git && cd FABouanes && bash setup_termux.sh
```

#### 👑 Commandes Raccourcis Universelles dans Termux :

| Commande | Action |
| :--- | :--- |
| **`fab`** | Lancer le serveur HTTPS mobile (`https://localhost:5000`) |
| **`fab-qr`** | **Afficher le QR Code Wi-Fi scannable** pour connecter d'autres smartphones |
| **`fab-backup`** | **Sauvegarder la base de données PostgreSQL** dans vos Téléchargements |
| **`fab-update`** | **Mettre à jour l'application en 1-clic** depuis GitHub |
| **`fab-stop`** | Arrêter proprement le serveur et PostgreSQL |
| **`fab-pin`** | Afficher votre Code PIN Administrateur |
| **`fab-status`** | Vérifier l'état du serveur et de la base de données |

---

### 💻 2. Sur PC Windows (Serveur Desktop)

Double-cliquez simplement sur **`LANCER.bat`** à la racine du projet.

- Démarre automatiquement le service **PostgreSQL**.
- Vérifie les dépendances pré-compilées (dossier `./wheels`).
- Génère le certificat SSL et lance l'application sécurisée en **`HTTPS`**.
- Pour afficher le QR Code Wi-Fi sur PC : `LANCER.bat --qr`

---

## 🔒 Sécurité HTTPS (SSL) Native & Automatique

- **Certificat SSL 10 ans auto-généré** : L'application crée automatiquement ses clés SSL (`cert.pem` et `key.pem`) dans le dossier de données sans nécessiter d'installation externe d'OpenSSL.
- **Accès Sécurisé** :
  - **PC / Smartphone Local** : `https://localhost:5000`
  - **Réseau Wi-Fi LAN** : `https://192.168.x.x:5000`

---

## 🐘 Architecture 100 % PostgreSQL 18 Exclusive

- **0 SQLite / Zero divergence** : Une architecture de base de données unifiée et robuste.
- **Reconnexion Automatique** : Le pool de connexions (`pool_pre_ping=True`, `pool_recycle=1800`) se rétablit automatiquement sans perte de session en cas de micro-coupure réseau.
- **Transactions Financières Atomiques** : Tous les règlements, ventes et écritures comptables utilisent le décorateur `db_transaction()`.
- **Migrations Alembic à Chaud** : Les schémas de base de données et les vues sont mis à jour automatiquement au démarrage via `bootstrap_and_migrate()`.

---

## 🤖 Assistant Virtuel Sabrina (IA Métier)

L'assistant IA **Sabrina** est directement connecté à la base de données et aux fonctionnalités de l'entreprise :

- **KPIs en Temps Réel** : Ingestion directe du contexte commercial (chiffre d'affaires du jour, total créances clients, alertes de stock bas).
- **Chaîne de Fallback Automatique** : Bascule de modèle fluide en cas de quota dépassé :
  `gemini-2.5-flash` ➔ `gemini-1.5-flash` ➔ `gemini-2.5-pro` ➔ `gemini-3.1-flash-lite` ➔ `gemini-3.5-flash`.
- **Support des Notes Vocales** : Transcription et exécution des commandes vocales.
- **Mode 100 % Local (Ollama)** : Fonctionne en local même sans connexion Internet.

---

## 🎨 Design System & Ergonomie UI

- **Chiffres Tabulaires Alignés (`tabular-nums`)** : Alignement vertical parfait de tous les montants et prix.
- **Feedback Tactile (`scale(0.985)`)** : Sensation d'application native au toucher sur mobile.
- **Zones Tactiles Ergonomiques** : Boutons et champs de saisie calibrés pour les écrans tactiles (`min-height: 42px`).
- **Scrollbars Fines et Épurées** : Barres de défilement discrètes et élégantes.

---

## 🗂️ Structure du Projet

```text
FABouanes/
├── app/                      # Application backend FastAPI
│   ├── api/                  # Endpoints REST (v1)
│   ├── core/                 # Configuration, base de données (db_helpers), sécurité, SSL
│   ├── modules/              # Modules métier (sales, purchases, catalog, clients, assistant)
│   └── web/                  # Vues HTML Jinja2 (rendu serveur)
├── static/                   # Assets Web (CSS, JS, images, icônes PWA)
├── templates/                # Gabarits HTML Jinja2
├── wheels/                   # Cache de 81 roues Python pré-compilées (mode 100% offline)
├── setup_termux.sh           # Script d'installation & configuration 1-clic Android (Termux)
├── LANCER.bat                # Lanceur 1-clic Windows Desktop & Serveur Réseau (HTTPS)
├── launcher.py               # Moteur de lancement universel (Desktop/Server/SSL/QR)
└── requirements.txt          # Dépendances Python requises
```

---

## 📄 Licence & Support

Projet propriétaire **FABOuanes**. Tous droits réservés.
