# FABOuanes

**FABOuanes** est une solution ERP de gestion commerciale conçue pour les PME : facturation, suivi client, gestion des stocks, production et assistant métier IA. Le projet combine une application **FastAPI** (rendu serveur + API REST), une interface web moderne (PWA installable en mode hors-ligne) et un assistant IA nommé **Sabrina** qui exécute des actions métier via le langage naturel.

![Version](https://img.shields.io/badge/version-2.0.5-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-541%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-78%25-green)
![License](https://img.shields.io/badge/license-Proprietary-lightgrey)

---

## Sommaire

- [Fonctionnalités principales](#fonctionnalités-principales)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Démarrage rapide](#démarrage-rapide)
- [Configuration](#configuration)
- [Structure du projet](#structure-du-projet)
- [Modules métier](#modules-métier)
- [Tests](#tests)
- [Déploiement](#déploiement)
- [Observabilité](#observabilité)
- [Sécurité](#sécurité)
- [Limitations connues](#limitations-connues)
- [Contribuer](#contribuer)
- [Changelog](#changelog)

---

## Fonctionnalités principales

- **Gestion commerciale complète** — ventes cash/crédit, achats fournisseurs, facturation, production
- **Gestion des stocks en temps réel** — alertes de seuil, traçabilité des mouvements, coût moyen pondéré
- **Suivi clients et fournisseurs** — historique, créances, import en masse via Excel
- **Assistant Sabrina** — IA intégrée (Gemini API ou Ollama local) qui exécute des actions métier via le langage naturel, avec mémoire persistante, garde-fou SQL et gestion des confirmations
- **Interface web + bureau** — rendu serveur Jinja2, PWA installable avec synchronisation hors-ligne, application desktop via `pywebview`
- **API mobile dédiée** — JWT Bearer pour une application vendeur terrain
- **Tableaux de bord et rapports** — KPI temps réel, alertes configurable, export PDF
- **Sauvegardes automatiques** — nightly vers dossier local ou Google Drive, rétention configurable
- **Piste d'audit complète** — qui a fait quoi, quand, avant/après, pour chaque opération
- **Déploiement local ou conteneurisé** — Docker Compose avec PostgreSQL + pgAdmin inclus

---

## Architecture

FABOuanes suit une architecture modulaire à couches, avec découverte automatique des modules métier au démarrage.

```mermaid
flowchart TB
    subgraph Client["Clients"]
        WEB["Navigateur web<br/>SSR Jinja2 + PWA"]
        DESKTOP["App desktop<br/>pywebview"]
        MOBILE["App mobile<br/>JWT Bearer"]
    end

    subgraph Core["FastAPI — app/main.py"]
        MW["Middlewares<br/>Session · CSRF · CSP nonce<br/>Sanitizer XSS · GZip · Rate limit"]
    end

    subgraph Registry["Module Registry"]
        MODULES["catalog · sales · purchases<br/>clients · payments · expenses<br/>production · reports · users"]
    end

    subgraph Assistant["Assistant Sabrina"]
        AI["Intent classifier<br/>Tool actions · SQL guard<br/>Gemini API / Ollama local"]
    end

    subgraph Services["Couche services"]
        SVC["auth · backup · stock · payment<br/>excel_import · print · transactions"]
    end

    subgraph Cross["Transverse"]
        AUDIT["Audit trail async<br/>Event bus · Perf cache<br/>Idempotency · RBAC"]
        OBS["OpenTelemetry · structlog<br/>Prometheus · Health check"]
    end

    DB[("SQLite WAL<br/>SQLAlchemy 2.0 + aiosqlite<br/>Alembic migrations")]

    Client --> Core
    Core --> Registry
    Core --> Assistant
    Registry --> Services
    Assistant --> Services
    Services --> Cross
    Cross --> DB
```

**Principes clés :**

- **Modules auto-découverts** : chaque domaine métier (`app/modules/<nom>/`) s'enregistre lui-même via `ModuleDescriptor` ; ajouter un module ne nécessite aucune modification du core.
- **Worker applicatif unique** : le cache et le scheduler sont in-process ; la coordination autonome s'appuie sur la base SQLite locale.
- **Séparation web/API** : les routes HTML (`app/web/`) et les routes JSON (`app/api/v1/`) partagent les mêmes services métier.
- **Sécurité défensive** : CSRF sur tous les formulaires, nonce CSP par requête, sanitisation XSS automatique, rate limiting configurable.

---

## Stack technique

| Domaine | Technologies |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, aiosqlite, Alembic |
| Frontend | Jinja2, Bootstrap 5, JS modulaire (vanilla), Chart.js, HTMX, AlpineJS |
| Base de données | SQLite (mode WAL, zéro-configuration) |
| Assistant IA | Google Gemini API, Ollama (modèles locaux) |
| Sécurité | JWT (PyJWT), CSRF, CSP, rate limiting (slowapi), RBAC |
| Observabilité | OpenTelemetry, structlog, Prometheus |
| Desktop | pywebview |
| PWA | Service Worker, IndexedDB (mode hors-ligne) |
| Conteneurisation | Docker multi-stage, Docker Compose |
| CI/CD | GitHub Actions (lint ruff/mypy, tests pytest + coverage ≥ 75 %) |

---

## Démarrage rapide

### Prérequis

- Python 3.11+

### Installation locale

```powershell
# 1. Cloner le dépôt
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes

# 2. Créer et activer l'environnement virtuel
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Installer les dépendances
python -m pip install -r requirements.txt

# 4. Configurer l'environnement
copy .env.example .env
# Éditer .env : définir DATABASE_URL, SECRET_KEY, DEFAULT_ADMIN_PASSWORD

# 5. Lancer l'application (migrations appliquées automatiquement au démarrage)
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

L'application est accessible sur `http://localhost:5000`. Le compte admin par défaut est créé au premier lancement — le mot de passe temporaire (PIN à 4 chiffres) est écrit dans le fichier `first_admin_password.txt` dans le dossier de données de l'application.

### Mode bureau (desktop)

```powershell
python launcher.py
```

### Avec Docker Compose

```powershell
copy .env.example .env
# Éditez .env avec vos paramètres

docker compose up --build
```

Services démarrés :
- `web` — application FastAPI sur le port `5000`
- `db` — PostgreSQL 16 sur le port `5432`
- `pgadmin` — interface d'administration PostgreSQL

### Vérifier que tout fonctionne

```bash
curl http://localhost:5000/health
```

Une réponse `{"status": "ok", ...}` confirme que la base de données, le worker de fond et le cache sont opérationnels.

---

## Configuration

Toutes les variables sont documentées dans [`.env.example`](./.env.example). Les plus importantes :

| Variable | Rôle | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé de session — **obligatoire en production** | auto-générée si vide |
| `DATABASE_URL` | Connexion PostgreSQL (`postgresql://user:pass@host/db`) | — |
| `FAB_PASSWORD_MODE` | `0000` (PIN 4 chiffres) ou `password` (8+ car.) | `0000` |
| `DEFAULT_ADMIN_PASSWORD` | Mot de passe admin initial (éviter `1234` ou `admin`) | PIN aléatoire |
| `SESSION_COOKIE_SECURE` | Cookies HTTPS-only | `0` (auto en production) |
| `FAB_MODULES_DISABLED` | Désactiver des modules (`expenses,reports`) | — |
| `WEB_CONCURRENCY` | Nombre de workers uvicorn | `1` |
| `FAB_RATE_LIMIT_BACKEND` | `memory` ou `db` | `memory` |
| `FAB_DISABLE_BACKGROUND_JOBS` | Désactiver le worker de fond (`1`) | `0` |
| `GEMINI_API_KEY` | Clé API Google Gemini pour l'assistant Sabrina | — |

> **Production** : utilisez `FAB_PASSWORD_MODE=password` dès qu'un accès réseau ou multi-utilisateur est activé — le mode PIN est réservé à un usage desktop strictement local.

---

## Structure du projet

```
FABouanes/
├── app/
│   ├── api/            # Routes API REST (JSON) — /api/v1/*
│   ├── core/           # Config, DB, cache, sécurité, audit, event bus
│   ├── modules/        # Modules métier auto-découverts
│   │   ├── assistant/  # Assistant Sabrina (IA)
│   │   ├── catalog/    # Catalogue produits & matières premières
│   │   ├── clients/    # Gestion clients
│   │   ├── expenses/   # Dépenses
│   │   ├── payments/   # Paiements clients/fournisseurs
│   │   ├── production/ # Suivi de production
│   │   ├── purchases/  # Achats fournisseurs
│   │   ├── reports/    # Rapports & tableaux de bord
│   │   ├── sales/      # Ventes & facturation
│   │   └── users/      # Utilisateurs & rôles
│   ├── services/       # Services transverses (auth, backup, stock...)
│   └── web/            # Routes HTML (rendu serveur)
├── alembic/            # Migrations de base de données
├── templates/          # Vues Jinja2
├── static/             # CSS, JS, assets, PWA (manifest, service worker)
├── tests/              # Tests automatisés (pytest, ~540 tests, ≥ 75 % couverture)
├── scripts/            # Scripts utilitaires (import, stress test, rate limit)
├── deploy/             # Fichiers de déploiement
└── installer/          # Scripts d'installation Windows
```

---

## Modules métier

| Module | Rôle |
|---|---|
| `assistant` | Assistant IA Sabrina — classification d'intention, actions outillées, garde-fou SQL, mémoire persistante |
| `catalog` | Gestion du catalogue produits finis et matières premières |
| `clients` | Fiches clients, historique, créances, import en masse |
| `expenses` | Suivi et catégorisation des dépenses |
| `payments` | Paiements clients/fournisseurs avec réconciliation |
| `production` | Suivi de production avec consommation de stock automatique |
| `purchases` | Achats fournisseurs avec mise à jour du stock |
| `reports` | Tableaux de bord, KPI temps réel, alertes, export PDF |
| `sales` | Ventes cash/crédit, facturation, documents de vente |
| `users` | Utilisateurs, rôles et permissions (RBAC à 3 niveaux) |

Chaque module déclare ses routes web/API, son schéma SQL et ses permissions via `ModuleDescriptor` — voir [`app/core/registry.py`](./app/core/registry.py) pour le mécanisme d'enregistrement.

---

## Tests

La suite de tests utilise **pytest** avec SQLite en mémoire (sans dépendance PostgreSQL). La couverture de code est mesurée automatiquement.

```bash
# Lancer la suite complète avec couverture
python -m pytest

# Lancer un fichier de test précis
python -m pytest tests/test_financial_core.py -v

# Voir le rapport de couverture HTML
python -m pytest --cov-report=html
# → Ouvrir htmlcov/index.html
```

**État actuel :**

| Métrique | Valeur |
|---|---|
| Tests | ~540 (541 au dernier run) |
| Couverture globale | ≈ 78 % |
| Seuil CI obligatoire | 75 % (`--cov-fail-under=75`) |
| Temps d'exécution | ~50 secondes |

Modules avec couverture élevée (> 90 %) : `exceptions`, `helpers`, `jwt_auth`, `models`, `schema/*`, `registry`, `runtime_paths`, `assistant/briefing`, `assistant/memory`, `assistant/tool_actions_tools`.

---

## Déploiement

### Image Docker

L'image est construite en deux étapes (builder + production), tourne avec un utilisateur non-root, et embarque un healthcheck :

```bash
docker build -t fabouanes:latest .
docker run -p 5000:5000 --env-file .env fabouanes:latest
```

### Variables d'environnement spécifiques au déploiement

| Variable | Recommandation production |
|---|---|
| `SECRET_KEY` | Chaîne aléatoire de 64+ caractères |
| `FAB_PASSWORD_MODE` | `password` |
| `SESSION_COOKIE_SECURE` | `1` (HTTPS uniquement) |
| `FAB_LOG_JSON` | `1` (logs JSON structurés) |
| `WEB_CONCURRENCY` | `1` (voir Limitations) |

---

## Observabilité

- **Métriques** : Prometheus sur `/metrics`
- **Traces** : OpenTelemetry, exportables vers un collecteur OTLP (`OTEL_EXPORTER_OTLP_ENDPOINT`)
- **Logs** : JSON structuré en production (`FAB_LOG_JSON=1`), texte lisible en développement
- **Health checks** : `/health` (état global) et `/readiness` (DB + scheduler + cache + disque)

---

## Sécurité

- Sessions signées (`itsdangerous`) avec cookie `SameSite=Lax`, HTTPS-only forcé en production
- Protection CSRF sur tous les formulaires, nonce CSP par requête
- Sanitisation XSS automatique des champs de formulaire (middleware transverse)
- RBAC à trois rôles (`admin`, `manager`, `operator`) avec permissions déclaratives par endpoint
- Authentification JWT dédiée pour l'API mobile
- Rate limiting configurable (mémoire ou PostgreSQL)
- Piste d'audit asynchrone (qui a fait quoi, quand, avant/après)
- Validation stricte des identifiants SQL (protection injection)
- Worker de fond démarré **après** bootstrap complet du schéma (évite les erreurs de table manquante)

Pour signaler une vulnérabilité, contactez l'équipe via le dépôt GitHub plutôt que d'ouvrir une issue publique.

---

## Limitations connues

- **Un seul worker applicatif recommandé** (`WEB_CONCURRENCY=1`) : le cache et le scheduler de sauvegarde sont in-process. Le multi-worker peut être activé explicitement (`FAB_ALLOW_MULTI_WORKER=1`) ; la cohérence inter-workers passe alors par une table `pubsub_events` avec une latence de propagation d'environ 1 seconde.
- **PostgreSQL uniquement** : seul moteur de base de données supporté (validation stricte de `DATABASE_URL`). SQLite n'est utilisé qu'en environnement de test.
- **pgvector optionnel** : le RAG sémantique de Sabrina nécessite l'extension `pgvector`. En son absence, un fallback mathématique Python prend le relais automatiquement.

---

## Contribuer

1. Créez une branche depuis `main` : `git checkout -b feature/ma-fonctionnalite`
2. Respectez le style existant (`ruff check app/`, `mypy app/`)
3. Ajoutez des tests pour toute nouvelle logique métier
4. Vérifiez que la suite complète passe : `python -m pytest`
5. Ouvrez une pull request avec une description claire du changement

Les migrations de base de données doivent être ajoutées via Alembic (`alembic revision -m "description"`) et testées avant fusion.

---

## Dépôt GitHub

- https://github.com/ouanesfab-alt/FABouanes

## Changelog

Voir [CHANGELOG.md](./CHANGELOG.md) pour l'historique détaillé des versions.
