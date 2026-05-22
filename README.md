# 🖥️ FABOuanes — FastAPI & PyWebView Desktop Platform

[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![UI Style](https://img.shields.io/badge/UI--Style-macOS%20Sequoia-grey?logo=apple&logoColor=white)](https://github.com/ouanesfab-alt/FABouanes)
[![License](https://img.shields.io/badge/License-Proprietary-red)](#)

FABOuanes est une application de bureau et serveur de gestion commerciale haut de gamme conçue pour la facturation, le suivi d'inventaire, le relevé de compte client et l'archivage de documents. Initialement développée sous Flask, la plateforme a été entièrement migrée vers **FastAPI** tout en préservant ses fonctionnalités métiers critiques, ses interfaces utilisateur enrichies et sa compatibilité avec l'écosystème réseau et mobile.

---

## 🏛️ Architecture & Structure du Projet

L'application suit une structure modulaire inspirée du modèle de conception de l'Architecture Propre (Clean Architecture), isolant la persistance, la logique métier et la couche de présentation.

```text
FABouanes/
├── app/                        # Dossier principal de l'application FastAPI
│   ├── main.py                 # Point d'entrée de l'application (ASGI Web & Desktop)
│   ├── api/                    # API Endpoints (v1, routeurs de compatibilité mobile)
│   ├── core/                   # Cœur (configuration, sécurité, base de données, transactions)
│   ├── modules/                # Modules métiers isolés (ex: expenses, reports)
│   ├── repositories/           # Couche d'accès aux données (SQLAlchemy Core queries)
│   ├── schemas/                # Schémas de validation de données (Pydantic models)
│   ├── services/               # Logique applicative et orchestration métier
│   ├── web/                    # Routeurs pour les pages Web rendues via Jinja2
│   └── utils/                  # Fonctions d'aide (pagination, connexion mobile, impression)
├── templates/                  # Fichiers HTML (Jinja2) avec styles embarqués
├── static/                     # Assets statiques (CSS, polices, JS, images)
│   ├── css/
│   │   ├── tokens.css          # Variables CSS du Design System (macOS Sequoia)
│   │   └── components.css      # Composants graphiques et animations
│   └── app.css                 # Feuille de style globale (thèmes clair / sombre / windows-dark)
├── tests/                      # Suite de tests (pytest)
│   ├── api/                    # Tests de validation API
│   ├── web/                    # Tests des pages HTML
│   ├── printing/               # Tests de rendu et d'impression des documents
│   └── conftest.py             # Fixtures pytest et initialisation de base de données de test
├── alembic/                    # Gestion des migrations de base de données relationnelle
├── launcher/                   # Scripts de lancement rapide du serveur
├── installer/                  # Packaging desktop Windows (PyInstaller, Inno Setup)
└── README.md                   # Ce document explicatif
```

---

## 🎨 Design System & Esthétique (Style macOS Sequoia)

L'interface de FABOuanes est construite autour d'une identité visuelle moderne et épurée, s'alignant sur l'esthétique système de **macOS Sequoia** :

*   **Design Visuel** : Coins arrondis prononcés (`border-radius: 12px` / `16px`), glassmorphisme discret, bordures extrêmement fines de couleur ardoise, et ombres douces à niveaux multiples (`box-shadow`).
*   **Thèmes Dynamiques** :
    *   **Thème Clair (Light)** : Couleurs épurées, contrastes précis et fonds blancs/crèmes doux.
    *   **Thème Sombre (Dark)** : Tons profonds basés sur une palette *Slate* (`#0f172a`), évitant le noir pur pour un confort visuel maximal.
    *   **Thème Windows-Dark** : Spécifiquement conçu pour s'intégrer harmonieusement sur les machines Windows avec une adaptation des gris.
*   **Documents Professionnels** : Les factures, bons d'achat et relevés d'historique disposent d'un rendu d'impression A4 précis (`190mm` de largeur de contenu, `10mm` de marges) et sont entièrement isolés des thèmes sombres de l'application. Lors du passage en Dark Mode, les titres de facturation et les observations demeurent parfaitement lisibles en Slate profond (`#0f172a`) sur fond de page blanc à l'écran et lors de l'impression.

---

## ⚙️ Configuration & Prérequis

### Prérequis Système
*   **Python 3.11+**
*   **PostgreSQL** (installé localement sur le serveur)
*   **Windows 10/11** (obligatoire pour construire l'exécutable standalone et l'installateur)
*   **Inno Setup 6** (requis pour compiler l'installateur Windows)

### Variables d'Environnement (.env)
Copiez le fichier `.env.example` sous le nom `.env` à la racine du projet et configurez les variables suivantes :

```env
SECRET_KEY=votre_cle_secrete_fastapi
DATABASE_URL=postgresql://fabouanes:votre_mot_de_passe@127.0.0.1:5432/fabouanes
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=1
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin
```

> [!IMPORTANT]
> Chaque poste de développement ou serveur doit disposer d'un mot de passe PostgreSQL valide défini dans `DATABASE_URL`. Au premier démarrage, l'application se charge automatiquement de provisionner la base de données et de jouer les migrations Alembic.

#### Initialisation PostgreSQL (Nouvelle Machine)
Si vous installez l'application sur un nouveau PC, lancez ces requêtes SQL sous pgAdmin ou psql pour configurer la base de données :

```sql
CREATE USER fabouanes WITH PASSWORD 'mot_de_passe_choisi';
CREATE DATABASE fabouanes OWNER fabouanes;
GRANT ALL PRIVILEGES ON DATABASE fabouanes TO fabouanes;

\c fabouanes

GRANT ALL ON SCHEMA public TO fabouanes;
ALTER SCHEMA public OWNER TO fabouanes;
```

---

## 🚀 Utilisation locale & Démarrage

### 1. Installation de l'environnement virtuel

```powershell
# Création et activation de l'environnement virtuel
python -m venv .venv
.venv\Scripts\Activate.ps1

# Installation des dépendances requises
python -m pip install -r requirements.txt
```

### 2. Lancement en Mode Développement (Web)
Pour travailler sur l'application avec rechargement automatique en cas de modification de code :

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

Accédez à l'application sur :
*   **Localement** : `http://127.0.0.1:5000`
*   **Depuis le réseau** : `http://IP_DE_VOTRE_SERVEUR:5000` (ex: `http://192.168.1.32:5000`)

### 3. Lancement du Client Desktop (WebView)
Pour exécuter l'application sous forme de fenêtre de bureau native (en utilisant le moteur PyWebView local, idéal pour le poste principal de facturation) :

```powershell
python launcher.py
```

Le lanceur va automatiquement :
1. Vérifier l'accès et créer le dossier d'application utilisateur.
2. Initialiser/Migrer le schéma PostgreSQL local.
3. Démarrer le serveur FastAPI Uvicorn en tâche de fond.
4. Ouvrir l'application dans une interface de bureau fluide et compacte.

---

## 💾 Gestion de la Base de Données & Migrations

La persistance repose sur SQLAlchemy Core associé à **Alembic** pour la gestion des versions du schéma de données. 

### Créer une nouvelle migration
Si vous modifiez la structure des tables dans `app/core/schema.py`, générez une nouvelle révision Alembic :

```powershell
python -m alembic revision -m "description_de_la_modification"
```

### Appliquer les migrations manuellement
```powershell
python -m alembic upgrade head
```

> [!NOTE]
> **Règle transactionnelle** : Pour garantir l'intégrité des opérations d'écriture de données sur PostgreSQL, toute logique d'écriture multi-requête doit être enveloppée dans le décorateur de transaction `db_transaction()`.

### Multi-workers & Tâches Planifiées (Scheduler)
En cas de déploiement multi-workers (par exemple sous Gunicorn avec plusieurs processus actifs et la variable `FAB_ALLOW_MULTI_WORKER=1`), les planifications d'alertes quotidiennes via APScheduler risquent de se déclencher simultanément sur chaque worker.
Pour prévenir les doublons d'alertes, un mécanisme de verrou consultatif transactionnel PostgreSQL (`pg_try_advisory_xact_lock`) est utilisé. Seul le premier worker à acquérir le verrou exécute la diffusion, les autres workers ignorant la tâche de façon transparente.


---

## 🧪 Suite de Tests Unitaires & Couverture

L'application intègre une suite de tests automatisés complète basée sur **pytest**. 

```powershell
# Exécuter tous les tests unitaires
python -m pytest
```

### Détails du Framework de Test
*   Les tests provisionnent automatiquement un cluster PostgreSQL de test temporaire sur un port dédié afin de ne pas impacter votre base de données de production.
*   **Couverture de code (Coverage)** : La configuration minimale exige un taux de couverture de 50% sur l'ensemble de l'application pour valider le pipeline d'intégration.
*   Les tests sont répartis dans le dossier `/tests` :
    *   `tests/web/` : Validation du rendu des vues web (dashboard, fiches clients, formulaires).
    *   `tests/api/` : Validation de la conformité des réponses JSON et de l'accès sécurisé.
    *   `tests/printing/` : Validation du rendu des templates PDF et des impressions papier en mode A4.

---

## 📦 Packaging & Déploiement Windows

Des scripts Windows automatisés (`.bat`) sont fournis à la racine pour compiler et distribuer l'application.

### 1. Construire l'Exécutable Standalone (.exe)
Ce script utilise **PyInstaller** pour regrouper le code Python, l'interpréteur, FastAPI et PyWebView dans un seul dossier distribuable :

```powershell
installer\windows\COMPILER_EXE_AVEC_TESTS.bat
```

### 2. Produire l'Installateur Final (.exe Setup)
Ce script fait appel à **Inno Setup** (via le fichier de script `installer/windows/FABOuanes_Setup.iss`) pour créer un assistant d'installation classique avec raccourcis bureau et initialisation automatique du runtime :

```powershell
CREER_INSTALLATEUR_WINDOWS.bat
```

*   **Résultat compilé** : `dist\FABOuanes\FABOuanes.exe`
*   **Installateur généré** : `installer_output\FABOuanes_Setup.exe`

---

## 📤 Processus de Livraison GitHub
Pour pousser proprement vos développements locaux sur GitHub :
Exécutez la commande d'automatisation suivante à la racine :

```powershell
PUSH_GITHUB.bat
```

Ce script va automatiquement :
1. Détecter la branche Git courante.
2. Vous demander de saisir un message de commit explicite.
3. Ajouter tous les fichiers modifiés (`git add -A`).
4. Créer un commit local.
5. Effectuer une réorganisation propre (`git pull --rebase origin <branche>`).
6. Envoyer le code vers le dépôt GitHub distant.
