# FABOuanes — Solution ERP & Gestion Intégrée

**FABOuanes** est une solution ERP de gestion commerciale et financière de pointe conçue pour les PME : facturation, suivi client, gestion des stocks, production, comptabilité SCF et assistant métrique basé sur l'IA (**Sabrina**).

Le projet combine une application **FastAPI** haute performance (rendu serveur + API REST), une interface web PWA responsive avec synchronisation hors-ligne, un installateur desktop Windows 100% autonome (Inno Setup 6 + PyInstaller avec PostgreSQL 18 embarqué), et un support Termux/Android.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-232%20passed%20100%25-brightgreen)
![Coverage](https://img.shields.io/badge/couverture-gt%2090%25-brightgreen)
![Windows](https://img.shields.io/badge/Windows-Installer%20.exe-0078D6)
![License](https://img.shields.io/badge/license-Proprietary-lightgrey)

---

## Sommaire

- [Fonctionnalités principales](#fonctionnalités-principales)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Modes de Déploiement & Installation](#modes-de-déploiement--installation)
- [Configuration](#configuration)
- [Structure du projet](#structure-du-projet)
- [Modules métier](#modules-métier)
- [Assurance Qualité & Tests](#assurance-qualité--tests)
- [Observabilité & Sécurité](#observabilité--sécurité)
- [Contribuer](#contribuer)

---

## Fonctionnalités principales

- **Gestion commerciale complète** — Ventes cash/crédit, achats fournisseurs, facturation, suivi des acomptes et créances.
- **Comptabilité SCF (Système Comptable Financier)** — Plan comptable conforme aux normes algériennes, écritures automatisées et bilans.
- **Gestion des stocks en temps réel** — Alertes de seuil, coût moyen pondéré (CMP), traçabilité des mouvements et consommations de production.
- **Assistant Sabrina (IA Métier)** — IA intégrée (Google Gemini API ou Ollama local 100% privé) capable d'exécuter des actions métier en langage naturel avec garde-fou SQL et mémoire persistante.
- **Installateur Windows Autonome 100% Offline** — Package `.exe` généré par Inno Setup 6 embarquant PostgreSQL 18 et configurant automatiquement le pare-feu réseau.
- **PWA Multi-plateforme & Mode Hors-ligne** — Application web progressive installable sur mobile/desktop avec synchronisation IndexedDB.
- **API REST Mobile dédiée** — Authentification JWT Bearer pour les vendeurs et agents de terrain.
- **Piste d'Audit & Sécurité avancée** — Traçabilité intégrale (qui a fait quoi, quand, données avant/après) et système RBAC multi-rôles.

---

## Architecture

FABOuanes repose sur une architecture modulaire découplée à découverte automatique des composants.

```mermaid
flowchart TB
    subgraph Clients["Interface Utilisateur & Mobilité"]
        WEB["Navigateur Web<br/>PWA Offline + Jinja2"]
        DESKTOP["Application Bureau Windows<br/>Inno Setup + PyInstaller + pywebview"]
        MOBILE["Application Vendeur Mobile<br/>JWT Bearer API"]
    end

    subgraph Core["Core Applicatif FastAPI"]
        MW["Middlewares & Guards<br/>CSRF · CSP Nonce · XSS Sanitizer<br/>Rate Limiter · Session Manager"]
    end

    subgraph Registry["Registre des Modules Découverts"]
        MODULES["sales · purchases · catalog · clients<br/>payments · expenses · production<br/>accounting_scf · reports · users"]
    end

    subgraph Sabrina["Assistant IA Sabrina"]
        AI["Classification d'intentions<br/>Outillage métier · SQL Guard<br/>Google Gemini / Ollama Local"]
    end

    subgraph Persistence["Couche Données & Événements"]
        DB[("PostgreSQL 16/18 / SQLite<br/>SQLAlchemy 2.0 Async + Alembic")]
        AUDIT["Audit Trail Asynchrone<br/>Event Bus · Cache In-Memory"]
    end

    Clients --> Core
    Core --> Registry
    Core --> Sabrina
    Registry --> DB
    Sabrina --> DB
    Core --> AUDIT
```

> [!NOTE]
> **Découverte Automatique des Modules** : Chaque domaine métier s'enregistre via un `ModuleDescriptor` au démarrage de l'application sans nécessiter de modification du core.

---

## Stack technique

| Domaine | Technologies Utilisées |
|---|---|
| **Backend Core** | Python 3.11+, FastAPI, SQLAlchemy 2.0, Asyncpg, Alembic, Pydantic v2 |
| **Frontend UI** | HTML5 Semantic, CSS Vanilla, Bootstrap 5, JavaScript Vanilla (Modular ES6), Chart.js |
| **Desktop / Installer** | Inno Setup 6, PyInstaller, pywebview |
| **Base de Données** | PostgreSQL 18 / 16 (avec fallback SQLite transparent pour tests et dev) |
| **Intelligence Artificielle** | Google Gemini API (Cloud) & Ollama `qwen2.5:7b` (Local 100% privé) |
| **Sécurité & RBAC** | JWT (PyJWT), Sessions signées, CSRF Token, Content Security Policy (CSP), Rate Limiting |
| **Qualité & Linter** | Pytest, Coverage.py (> 90% exigé), Ruff Linter (Règles strictes dont T201) |

---

## Modes de Déploiement & Installation

### 1. Windows Desktop Installer (`.exe` Clé en Main)

Pour déployer sur des postes de travail sous Windows sans aucune dépendance préalable :

1. Exécutez l'installateur **`installer_output/FABOuanes_Setup.exe`**.
2. L'assistant Inno Setup configure automatiquement :
   - L'installation silencieuse de PostgreSQL 18.
   - Les répertoires applicatifs dans `%LocalAppData%\Programs\FABOuanes`.
   - La règle de pare-feu Windows pour le port `5000` en mode serveur réseau.
   - La base de données et l'exécution des migrations au premier démarrage.

Pour re-compiler l'installateur vous-même :
```cmd
installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat
```

---

### 2. Démarrage Rapide en Développement Python

```powershell
# 1. Cloner le dépôt
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes-main

# 2. Créer et activer l'environnement virtuel
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Installer les dépendances
python -m pip install -r requirements.txt

# 4. Lancer le serveur d'application avec rechargement automatique
python launcher.py --server
```

L'application est accessible sur `http://localhost:5000`.

---

### 3. Déploiement avec Docker Compose

```bash
# Lancer l'environnement conteneurisé complet (Web + PostgreSQL + pgAdmin)
docker compose up --build
```

---

## Configuration

La configuration s'effectue via le fichier **`.env`** à la racine de l'application :

| Variable | Description | Valeur par Défaut |
|---|---|---|
| `DATABASE_URL` | URL de connexion PostgreSQL | `postgresql://postgres:postgres@127.0.0.1:5432/fabouanes` |
| `SECRET_KEY` | Clé secrète pour les sessions et JWT | Générée automatiquement au build |
| `FAB_HOST` | Adresse d'écoute HTTP (`127.0.0.1` ou `0.0.0.0`) | `127.0.0.1` |
| `FAB_PORT` | Port d'écoute HTTP | `5000` |
| `GEMINI_API_KEY` | Clé API pour Google Gemini (IA Sabrina) | Optionnel |
| `FAB_SLOW_SQL_MS` | Seuil de détection des requêtes lentes (ms) | `100` |

---

## Structure du Projet

```text
FABouanes/
├── app/
│   ├── api/            # Endpoints API REST JSON (Vendeur mobile / API v1)
│   ├── core/           # Moteur Async DB, sécurité JWT/CSRF, audit, permissions
│   ├── modules/        # Modules métier (sales, purchases, catalog, accounting...)
│   │   ├── accounting/ # Module Comptabilité SCF
│   │   ├── assistant/  # Sabrina IA (RAG, SQL Guard, memory)
│   │   └── ...
│   └── web/            # Contrôleurs web et rendu des pages Jinja2
├── alembic/            # Migrations de schéma de base de données (0001 à 0038)
├── installer/          # Script Inno Setup 6 (.iss) & compilateurs d'installateurs Windows
├── static/             # Feuilles de style CSS, scripts JavaScript, PWA Manifest & SW
├── templates/          # Gabarits HTML Jinja2
├── tests/              # Suite de tests automatisés Pytest (> 90% couverture)
├── tests_frontend/     # Runner de tests JS Node.js pour les assets frontend
└── launcher.py         # Point d'entrée exécutable & bootstrapper d'application
```

---

## Assurance Qualité & Tests

Le projet impose une exigence de couverture de code globale et par module **> 90%** sur l'ensemble des composants Python et des assets non-Python (JavaScript, HTML, CSS, Scripts Shell & Batch).

### Exécuter la Suite de Tests

```bash
# Tests Backend Python (Pytest)
python -m pytest tests/ -q

# Tests Frontend JavaScript (Node.js Test Runner)
node --test tests_frontend/test_js_modules.test.js

# Vérification Linteur & Formatage (Ruff)
python -m ruff check app/
```

> [!IMPORTANT]
> **Contrôle Strict en Intégration Continue (CI/CD)** :
> Tous les tests doivent afficher **100% de succès** et aucun `print()` non structuré n'est toléré dans le code de production (règle linteur `T201`).

---

## Observabilité & Sécurité

- **Piste d'Audit Asynchrone** : Chaque création, modification ou suppression est enregistrée en arrière-plan avec l'identifiant de l'utilisateur, l'horodatage et les deltas avant/après.
- **Pare-feu SQL & Garde-Fou IA** : Les requêtes exécutées par l'assistant Sabrina passent au crible d'un analyseur AST (`sqlglot`) interdisant toute instruction de suppression ou de modification risquée non confirmée.
- **Protections Web Stricte** : Nonce CSP généré par requête, jetons CSRF sur chaque formulaire, et cookies HTTPS `SameSite=Lax`.

---

## Dépôt GitHub & Contribution

- **Dépôt Officiel** : [https://github.com/ouanesfab-alt/FABouanes](https://github.com/ouanesfab-alt/FABouanes)
- **Licence** : Propriétaire — Tous droits réservés.
