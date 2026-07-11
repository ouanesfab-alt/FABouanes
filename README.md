# FABOuanes

FABOuanes est une solution de gestion commerciale et de bureau pensée pour la facturation, le suivi client, l'inventaire et l'assistance métier. Le projet combine une application FastAPI, une interface web moderne et un assistant nommé Sabrina pour accompagner les utilisateurs dans leurs tâches quotidiennes.

## Fonctionnalités principales

- Gestion commerciale et facturation
- Suivi des clients, fournisseurs et opérations
- Interface web et bureau avec FastAPI
- Assistant Sabrina intégré à l'expérience utilisateur
- Déploiement local et conteneurisé

## Démarrage rapide

### Prérequis

- Python 3.11+
- PostgreSQL
- Docker Compose (optionnel)

### Lancement local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### Lancement bureau

```powershell
python launcher.py
```

### Avec Docker

```powershell
docker compose up --build
```

## Structure du projet

- app/ : application principale FastAPI
- templates/ : pages HTML et vues
- static/ : fichiers CSS, JavaScript et assets
- tests/ : tests automatisés
- deploy/ : fichiers de déploiement
- installer/ : scripts d'installation et packaging

## Dépôt GitHub

- https://github.com/ouanesfab-alt/FABouanes

## Notes

Ce projet est en évolution continue. Les instructions de démarrage et les dépendances peuvent évoluer selon les versions locales et les environnements de déploiement.
