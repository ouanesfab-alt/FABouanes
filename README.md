<p align="center">
  <img src="static/FABOuanes_desktop.ico" alt="FABOuanes" width="72" />
</p>

<h1 align="center">FABOuanes</h1>
<p align="center"><strong>ERP de Gestion Commerciale, Production & Comptabilité SCF</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.5-blue.svg?style=flat-square" alt="v2.0.5" />
  <img src="https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/framework-FastAPI-009688.svg?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/database-PostgreSQL%2018-336791.svg?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/tests-251%20passed-brightgreen.svg?style=flat-square&logo=pytest&logoColor=white" alt="251 tests" />
  <img src="https://img.shields.io/badge/coverage-≥85%25-brightgreen.svg?style=flat-square" alt="Coverage ≥ 85%" />
  <img src="https://img.shields.io/badge/license-Proprietary-lightgrey.svg?style=flat-square" alt="License" />
</p>

---

**FABOuanes** est un ERP complet destiné aux PME algériennes. Il couvre la facturation, la gestion des stocks et de la production, la comptabilité conforme au Système Comptable Financier (SCF), et intègre un assistant IA conversationnel (**Sabrina**) capable d'exécuter des requêtes métier en langage naturel.

Le projet se déploie en **trois modes** : application desktop Windows autonome (installateur `.exe` avec PostgreSQL embarqué), serveur réseau Linux/Termux pour accès multi-appareils, ou conteneur Docker Compose.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Stack Technique](#stack-technique)
- [Installation](#installation)
  - [Windows Desktop (.exe)](#1-windows-desktop-exe)
  - [Développement Python](#2-développement-python)
  - [Termux / Android](#3-termux--android)
  - [Docker Compose](#4-docker-compose)
- [Configuration](#configuration)
- [Arborescence](#arborescence)
- [Modules Métier](#modules-métier)
- [Tests & Qualité](#tests--qualité)
- [Sécurité & Audit](#sécurité--audit)
- [Licence](#licence)

---

## Fonctionnalités

| Domaine | Description |
|---|---|
| **Gestion commerciale** | Ventes cash ou à crédit, achats fournisseurs, facturation proforma et définitive, acomptes, créances et règlements |
| **Stocks & Production** | Suivi matières premières / produits finis, coût moyen pondéré (CMP), alertes seuil critique, ordres de fabrication |
| **Comptabilité SCF** | Plan comptable algérien, écritures automatiques, journal centralisateur, bilans |
| **Assistant IA (Sabrina)** | Requêtes en langage naturel, exécution d'actions métier sécurisées, mémoire de conversation, garde-fou SQL (AST `sqlglot`) |
| **PWA multi-plateforme** | Interface installable sans store, synchronisation hors-ligne (IndexedDB + Service Workers), API REST JWT |
| **Desktop Windows** | Installateur `.exe` tout-en-un (Inno Setup 6 + PyInstaller + PostgreSQL 18 silencieux) |
| **Serveur Termux** | Déploiement sur smartphone Android avec auto-heal PostgreSQL et Wake-Lock CPU |
| **Sécurité** | Audit trail asynchrone, CSRF tokens, CSP nonces dynamiques, rate limiting, RBAC |

---

## Architecture

```mermaid
flowchart TB
    subgraph UI["Interfaces"]
        WEB["Navigateur Web<br/>PWA Offline"]
        DESK["Desktop Windows<br/>pywebview"]
        API["API Mobile<br/>REST + JWT"]
    end

    subgraph CORE["FastAPI Core"]
        SEC["Sécurité<br/>CSRF · CSP · Rate Limit"]
        REG["Registre Modulaire<br/>ModuleDescriptor"]
    end

    subgraph BIZ["Modules Métier"]
        MOD["Sales · Purchases · Catalog<br/>Clients · Payments · Expenses<br/>Production · Accounting · Reports"]
    end

    subgraph IA["Assistant Sabrina"]
        NLP["Intent Parser · RAG<br/>SQLGuard · Gemini / Ollama"]
    end

    subgraph DATA["Persistance"]
        DB[("PostgreSQL 18<br/>SQLAlchemy 2 Async")]
        EVT["Audit Trail<br/>Event Bus"]
    end

    UI --> SEC --> REG --> MOD
    UI --> IA --> MOD
    MOD --> DB
    SEC --> EVT
```

> **Extensibilité** — Chaque domaine métier fournit un `ModuleDescriptor` auto-enregistré. Le cœur applicatif est totalement découplé de la logique métier.

---

## Stack Technique

| Couche | Technologies |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| **Base de données** | PostgreSQL 18/16, SQLAlchemy 2.0 Async, Alembic (38 migrations) |
| **Frontend** | HTML5, Vanilla CSS, Bootstrap 5, ES6 Modules, Chart.js |
| **PWA** | Service Workers, Web App Manifest, IndexedDB |
| **Desktop** | Inno Setup 6, PyInstaller, pywebview |
| **IA** | Google Gemini API (cloud) · Ollama `qwen2.5:7b` (local) |
| **Sécurité** | PyJWT, CSRF Guard, CSP Nonces, RateLimitStore (mémoire / Redis / DB) |
| **Tests** | Pytest (251 tests), Coverage.py (≥ 85%), Ruff linter |

---

## Installation

### 1. Windows Desktop (`.exe`)

1. Téléchargez et exécutez **`installer_output/FABOuanes_Setup.exe`**.
2. L'installateur gère automatiquement :
   - Installation silencieuse de PostgreSQL 18
   - Création de la base de données et migrations Alembic
   - Configuration du pare-feu Windows (port `5000`)
   - Raccourci bureau et démarrage de l'application

Pour re-compiler l'installateur :

```cmd
installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat
```

### 2. Développement Python

```bash
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes

python -m venv .venv
# Windows : .venv\Scripts\Activate.ps1
# Linux   : source .venv/bin/activate

pip install -r requirements.txt
python launcher.py --server
```

L'application est disponible sur **`http://localhost:5000`**.

### 3. Termux / Android

Installation en une commande :

```bash
curl -fsSL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh | bash
```

Le script `setup_termux.sh` installe Python, PostgreSQL, les dépendances, et génère un lanceur `~/start_fab.sh` qui :
- Active le **Wake-Lock** pour empêcher le sommeil CPU Android
- Nettoie les verrous PostgreSQL orphelins (`postmaster.pid`)
- Démarre le serveur accessible depuis tout appareil sur le même réseau Wi-Fi

### 4. Docker Compose

```bash
docker compose up --build -d
```

Démarre l'infrastructure complète : application FastAPI + PostgreSQL 18 + pgAdmin.

---

## Configuration

Variables d'environnement dans le fichier **`.env`** :

| Variable | Description | Défaut |
|---|---|---|
| `DATABASE_URL` | Connexion PostgreSQL | `postgresql://postgres:postgres@127.0.0.1:5432/fabouanes` |
| `SECRET_KEY` | Clé JWT et sessions | Générée aléatoirement |
| `FAB_HOST` | Adresse d'écoute | `0.0.0.0` |
| `FAB_PORT` | Port TCP | `5000` |
| `GEMINI_API_KEY` | Clé API Sabrina (Gemini) | — |
| `OLLAMA_BASE_URL` | URL Ollama locale | `http://127.0.0.1:11434` |
| `FAB_HTTPS` | Activer HTTPS auto-signé | `0` |
| `FAB_SLOW_SQL_MS` | Seuil requêtes SQL lentes (ms) | `100` |

---

## Arborescence

```
FABouanes/
├── app/
│   ├── api/              # API REST v1 (JWT Bearer)
│   ├── core/             # DB async, sécurité, audit, permissions, config
│   ├── modules/          # Domaines métier découplés
│   │   ├── accounting/   # Comptabilité SCF
│   │   ├── assistant/    # Sabrina IA (RAG, SQLGuard, mémoire)
│   │   ├── catalog/      # Catalogue produits & matières
│   │   ├── clients/      # Gestion des clients
│   │   ├── expenses/     # Charges opérationnelles
│   │   ├── payments/     # Encaissements & décaissements
│   │   ├── production/   # Ordres de fabrication
│   │   ├── purchases/    # Achats fournisseurs
│   │   ├── reports/      # Tableaux de bord & exports
│   │   ├── sales/        # Ventes & facturation
│   │   └── users/        # Authentification & rôles
│   └── web/              # Contrôleurs Jinja2
├── alembic/              # 38 migrations de schéma
├── installer/            # Scripts Inno Setup 6
├── static/               # CSS, JS ES6, PWA, Service Worker
├── templates/            # Gabarits HTML Jinja2
├── tests/                # 251 tests Pytest
├── tests_frontend/       # Tests JS Node.js
├── setup_termux.sh       # Installateur automatique Termux
├── launcher.py           # Point d'entrée CLI & GUI
├── LANCER.bat            # Lanceur serveur Windows simplifié
└── docker-compose.yml    # Déploiement conteneurisé
```

---

## Modules Métier

| Module | Responsabilité |
|---|---|
| `sales` | Ventes, articles vendus, devis proforma, facturation |
| `purchases` | Commandes fournisseurs, réception matières premières |
| `catalog` | Produits finis, articles personnalisés, matières premières |
| `clients` | Annuaire clients, créances, relevés de compte |
| `payments` | Encaissements, décaissements, versements |
| `expenses` | Charges opérationnelles et frais généraux |
| `production` | Ordres de fabrication, transformation MP → PF |
| `accounting` | Plan comptable SCF, écritures, journaux, bilans |
| `reports` | Synthèses financières, exports CSV/JSON |
| `assistant` | Sabrina IA — requêtes NL, actions métier, mémoire |

---

## Tests & Qualité

```bash
# Suite complète backend (251 tests, couverture ≥ 85%)
python -m pytest tests/ -q

# Tests frontend JavaScript
node --test tests_frontend/test_js_modules.test.js

# Analyse statique
python -m ruff check app/
```

| Métrique | Valeur |
|---|---|
| Tests automatisés | **251** |
| Taux de réussite | **100%** |
| Couverture Python Core | **≥ 85%** (seuil CI enforced) |
| Statements couverts | 4 875 / 5 735 |
| Linter | Ruff (zéro warning) |

---

## Sécurité & Audit

- **Audit Trail** — Enregistrement asynchrone des modifications avec états avant/après, auteur et horodatage IP.
- **SQLGuard** — Analyse AST via `sqlglot` bloquant les instructions destructrices (`DROP`, `TRUNCATE`, `DELETE` de masse) dans le contexte de l'assistant IA.
- **Protection Web** — CSRF tokens, nonces CSP dynamiques, en-têtes HTTP sécurisés (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`).
- **Rate Limiting** — Triple backend (mémoire, Redis, DB) avec backoff exponentiel et lockout automatique.
- **RBAC** — Contrôle d'accès basé sur les rôles avec permissions granulaires par module.

---

## Licence

**Propriétaire** — Tous droits réservés.

Dépôt : [github.com/ouanesfab-alt/FABouanes](https://github.com/ouanesfab-alt/FABouanes)
