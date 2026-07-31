# FABOuanes — Solution ERP & Gestion Intégrée

**FABOuanes** est une solution ERP moderne de gestion commerciale, de production et financière conçue pour les PME. Elle rassemble la facturation, le suivi client, la gestion des stocks, la comptabilité selon le Système Comptable Financier (SCF) algérien, ainsi qu'un assistant métier basé sur l'IA (**Sabrina**).

Le projet combine une application **FastAPI** haute performance (rendu serveur + API REST JSON), une interface web PWA responsive avec synchronisation hors-ligne, un installateur desktop Windows 100% autonome (Inno Setup 6 + PyInstaller avec PostgreSQL 18 embarqué), et un support pour environnement Termux/Android.

---

<p align="center">
  <img src="https://img.shields.io/badge/version-2.1.0-blue.svg?style=for-the-badge" alt="Version 2.1.0" />
  <img src="https://img.shields.io/badge/python-3.11%2B-0078D6.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/tests-253%20passed%20100%25-brightgreen.svg?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests 253 passing" />
  <img src="https://img.shields.io/badge/couverture-%3E%2085%25-brightgreen.svg?style=for-the-badge" alt="Coverage > 85%" />
  <img src="https://img.shields.io/badge/Windows-Installer%20.exe-0078D6.svg?style=for-the-badge&logo=windows&logoColor=white" alt="Windows Installer" />
  <img src="https://img.shields.io/badge/license-Proprietary-lightgrey.svg?style=for-the-badge" alt="License" />
</p>

---

## 📌 Sommaire

- [Fonctionnalités Principales](#-fonctionnalités-principales)
- [Architecture Systèmes](#-architecture-systèmes)
- [Stack Technique](#-stack-technique)
- [Modes de Déploiement & Installation](#-modes-de-déploiement--installation)
  - [1. Windows Desktop Installer (.exe autonome)](#1-windows-desktop-installer-exe-autonome)
  - [2. Démarrage en Développement Python](#2-démarrage-en-développement-python)
  - [3. Déploiement Docker Compose](#3-déploiement-docker-compose)
- [Configuration (.env)](#-configuration-env)
- [Arborescence du Projet](#-arborescence-du-projet)
- [Modules Métier](#-modules-métier)
- [Assurance Qualité & Tests](#-assurance-qualité--tests)
- [Observabilité, Sécurité & Audit](#-observabilité-sécurité--audit)
- [Dépôt & Licence](#-dépôt--licence)

---

## ✨ Fonctionnalités Principales

- **🛒 Gestion Commerciale Complexe** : Ventes au comptant (cash) ou à crédit, achats auprès des fournisseurs, facturation proforma et définitive, gestion des acomptes, créances et règlements.
- **📊 Comptabilité SCF Conforme** : Plan comptable général conforme aux normes SCF algériennes, génération automatique d'écritures comptables, journal centralisateur et bilans.
- **📦 Stocks & Production en Temps Réel** : Suivi des matières premières et produits finis, coût moyen unitaire pondéré (CMP), alertes de seuil critique et consommation automatique lors de la production.
- **🤖 Assistant IA Métier (Sabrina)** : Assistant intelligent capable de comprendre des requêtes en langage naturel, d'exécuter des actions sécurisées (achats, ventes, rapports, exports) avec mémoire de conversation et garde-fou SQL (AST analysis).
- **🖥️ Installateur Windows 100% Offline** : Paquet d'installation `.exe` généré avec Inno Setup 6, incluant PostgreSQL 18 en mode d'installation silencieuse et la création automatique des règles de pare-feu Windows pour le port `5000`.
- **📱 PWA Multi-plateforme & API Mobile** : Interface web progressive optimisée pour mobile et tablette, installable sans store, synchronisation hors-ligne avec IndexedDB et API REST JWT Bearer dédiée.
- **🔒 Sécurité & Piste d'Audit Intégrale** : Journalisation d'audit asynchrone (deltas avant/après, auteur, horodatage IP), CSRF tokens, CSP nonces dynamiques, protection XSS et contrôle d'accès fondé sur les rôles (RBAC).

---

## 🏗️ Architecture Systèmes

FABOuanes s'appuie sur une **architecture modulaire événementielle et découplée**, utilisant un système de découverte automatique des modules (`ModuleDescriptor`) au démarrage.

```mermaid
flowchart TB
    subgraph Clients["Interface Utilisateur & Mobilité"]
        WEB["Navigateur Web<br/>PWA Offline + HTML/CSS/JS"]
        DESKTOP["App Bureau Windows<br/>Inno Setup 6 + PyInstaller + pywebview"]
        MOBILE["API Vendeur Mobile<br/>REST JSON + JWT Bearer"]
    end

    subgraph Core["Core Applicatif FastAPI"]
        MW["Middlewares & Sécurité<br/>CSRF Guard · CSP Nonce · XSS Sanitizer<br/>Rate Limiter · Session Manager"]
        DESCR["Système de Registre Modulaire<br/>Découverte automatique via ModuleDescriptor"]
    end

    subgraph Registry["Modules Métier Interconnectés"]
        MODULES["Sales · Purchases · Catalog · Clients<br/>Payments · Expenses · Production<br/>Accounting SCF · Reports · Users"]
    end

    subgraph Sabrina["Assistant IA Sabrina"]
        AI["Parseur d'Intentions & NLP<br/>Garde-fou SQLGuard (AST sqlglot)<br/>Google Gemini / Ollama Local"]
    end

    subgraph Persistence["Couche Données & Événements"]
        DB[("PostgreSQL 18 / 16<br/>SQLAlchemy 2.0 Async + Alembic")]
        AUDIT["Piste d'Audit Asynchrone<br/>Event Bus Interne · Cache In-Memory"]
    end

    Clients --> MW
    MW --> DESCR
    DESCR --> MODULES
    Clients --> Sabrina
    Sabrina --> MODULES
    MODULES --> DB
    MW --> AUDIT
```

> [!NOTE]
> **Extensibilité Sans Friction** : Chaque nouveau domaine métier fournit son propre descripteur et ses scripts de schéma. Le cœur applicatif s'abstrait de la logique métier spécifique.

---

## 🛠️ Stack Technique

| Composant | Technologie | Rôle / Description |
|---|---|---|
| **Backend Core** | Python 3.11+, FastAPI, Pydantic v2 | API REST asynchrone, micro-framework web ultra rapide |
| **Base de Données** | PostgreSQL 18 / 16, SQLAlchemy 2.0 Async, Alembic | Persistence relationnelle async, ORM typé et migrations |
| **Frontend UI** | HTML5, Vanilla CSS, Bootstrap 5, ES6 Modules, Chart.js | Interface responsive, légère, dynamique et moderne |
| **PWA & Offline** | Service Workers, Manifest V2, IndexedDB | Application installable sur mobile & fonctionnement hors-ligne |
| **Desktop Package** | Inno Setup 6, PyInstaller, pywebview | Packaging Windows natif autonome 100% hors-ligne |
| **IA & NLP** | Google Gemini API (Cloud) / Ollama `qwen2.5:7b` (Local) | Traitement automatique des demandes métier en langage naturel |
| **Sécurité** | PyJWT, CSRF Guard, CSP Nonces, RateLimitStore | Protection renforcée OWASP Top 10 |
| **Qualité Code** | Pytest (253 tests verts), Coverage.py (> 85%), Ruff Linter | Suite de tests automatisée et validation statique rigoureuse |

---

## 🚀 Modes de Déploiement & Installation

### 1. Windows Desktop Installer (`.exe` autonome)

Pour installer et exécuter l'application sur un poste Windows sans prérequis technique :

1. Téléchargez et lancez **`installer_output/FABOuanes_Setup.exe`**.
2. L'assistant d'installation gère automatiquement :
   - L'installation et l'initialisation silencieuse du serveur **PostgreSQL 18**.
   - Le déploiement du binaire dans `%LocalAppData%\Programs\FABOuanes`.
   - L'ouverture du port `5000` sur le pare-feu réseau Windows (pour l'accès multi-postes).
   - La création de la base de données et le passage des migrations Alembic.

Pour re-compiler le binaire `.exe` et l'installateur :
```cmd
installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat
```

---

### 2. Démarrage en Développement Python

```powershell
# 1. Cloner le dépôt git
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes-main

# 2. Initialiser l'environnement virtuel Python
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Installer les dépendances du projet
python -m pip install -r requirements.txt

# 4. Lancer l'application en mode serveur de développement
python launcher.py --server
```

L'application est disponible à l'adresse : **`http://localhost:5000`**

---

### 3. Déploiement Docker Compose

```bash
# Lancer l'infrastructure complète (App FastAPI + PostgreSQL 18 + pgAdmin)
docker compose up --build -d
```

---

## ⚙️ Configuration (`.env`)

La configuration est gérée via les variables d'environnement définies dans le fichier **`.env`** :

| Variable | Description | Valeur par Défaut |
|---|---|---|
| `DATABASE_URL` | Chaine de connexion PostgreSQL (ou SQLite) | `postgresql://postgres:postgres@127.0.0.1:5432/fabouanes` |
| `SECRET_KEY` | Clé secrète pour les jetons JWT et sessions | Clé aléatoire sécurisée |
| `FAB_HOST` | Adresse d'écoute HTTP du serveur | `127.0.0.1` (ou `0.0.0.0` pour le réseau) |
| `FAB_PORT` | Port TCP d'écoute HTTP | `5000` |
| `GEMINI_API_KEY` | Clé API pour l'IA Sabrina (Google Gemini) | Optionnel |
| `OLLAMA_BASE_URL` | URL de l'instance Ollama locale | `http://127.0.0.1:11434` |
| `FAB_SLOW_SQL_MS` | Seuil d'alerte des requêtes SQL lentes (ms) | `100` |

---

## 📂 Arborescence du Projet

```text
FABouanes/
├── app/
│   ├── api/            # API REST v1 JSON (Authentification JWT Bearer & Vendeurs)
│   ├── core/           # Moteur Async DB, sécurité JWT/CSRF, audit, permissions, config
│   ├── modules/        # Domaines métier découplés (sales, purchases, catalog, accounting...)
│   │   ├── accounting/ # Module Comptabilité SCF (Plan comptable & bilans)
│   │   ├── assistant/  # Sabrina IA (Parser d'intentions, RAG, SQLGuard, mémoire)
│   │   └── ...
│   └── web/            # Contrôleurs web et rendu des templates Jinja2
├── alembic/            # Migrations de schéma de base de données (0001 à 0038)
├── installer/          # Scripts Inno Setup 6 (.iss) & compilateur d'installateur Windows
├── static/             # Assets CSS, JavaScript ES6, PWA Manifest & Service Worker
├── templates/          # Gabarits HTML Jinja2 (Rendu serveur)
├── tests/              # Suite complète de 253 tests unitaires et d'intégration Pytest
├── tests_frontend/     # Runner de tests JS Node.js pour la validation des modules frontend
└── launcher.py         # Point d'entrée principal (CLI & GUI Desktop Launcher)
```

---

## 💼 Modules Métier

- **`sales`** : Enregistrement des ventes, gestion des articles vendus, devis proforma, facturation.
- **`purchases`** : Commandes et achats auprès des fournisseurs, réception de matières premières.
- **`catalog`** : Catalogue des produits finis, articles personnalisés et matières premières avec unités.
- **`clients`** & **`suppliers`** : Annuaire des contacts, suivi des créances, historique et relevés de compte.
- **`payments`** & **`expenses`** : Encaissements, décaissements, versemens et charges opérationnelles.
- **`production`** : Ordres de fabrication, transformation de matières premières en produits finis.
- **`accounting_scf`** : Gestion du plan comptable algérien (SCF), écritures comptables et journaux.
- **`reports`** : Tableaux de bord financiers, synthèses d'activité et exports CSV/JSON.

---

## 🧪 Assurance Qualité & Tests

Le projet intègre une démarche de qualité stricte soutenue par **253 tests automatisés** et un contrôle de couverture continue (**> 85% exigeant** sur tout le socle Python Core).

### Commandes de Verification

```bash
# 1. Exécuter la suite complète des tests backend Python
python -m pytest tests/ -q

# 2. Exécuter les tests unitaires frontend JavaScript
node --test tests_frontend/test_js_modules.test.js

# 3. Analyser la conformité du code avec le linter Ruff
python -m ruff check app/
```

> [!IMPORTANT]
> **Contrôle Qualité en CI/CD** : Tous les tests unitaires s'exécutent avec **100% de succès**. Aucune instruction `print()` non contrôlée n'est admise dans le code de production (règle linter `T201`).

---

## 🔒 Observabilité, Sécurité & Audit

1. **Piste d'Audit Complète** : Enregistrement asynchrone en arrière-plan des modifications de données avec capture des états avant/après (`before` / `after`).
2. **Garde-Fou IA (SQLGuard)** : Analyse syntaxique AST avec `sqlglot` interdisant l'exécution non sollicitée d'instructions de suppression (`DROP`, `TRUNCATE`, `DELETE` de masse).
3. **Sécurité Web Avancée** : Jetons CSRF obligatoires sur les formulaires, nonces dynamiques CSP, en-têtes de sécurité HTTP (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`).

---

## 📜 Dépôt & Licence

- **Dépôt GitHub** : [https://github.com/ouanesfab-alt/FABouanes](https://github.com/ouanesfab-alt/FABouanes)
- **Licence** : Propriétaire — Tous droits réservés.
