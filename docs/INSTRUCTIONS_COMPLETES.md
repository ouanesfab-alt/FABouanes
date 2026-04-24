# FABOuanes - Instructions Completes (Reseau)

## Prerequis

- Python 3.11+
- PostgreSQL (local ou Docker)
- Docker Desktop (option recommandee)

## Scripts principaux

- `DOUBLE_CLIC_LANCER_TOUT.bat` -> lancement serveur web complet
- `START_POSTGRES.bat` -> start PostgreSQL + Redis Docker
- `STOP_POSTGRES.bat` -> stop PostgreSQL + Redis Docker
- `RESET_ADMIN_SECOURS.bat` -> reset admin manuel uniquement
- `SEED_DEMO.bat` -> donnees demo optionnelles
- `GENERER_ZIP_LIVRABLE.bat` -> ZIP propre pour partage

## PostgreSQL Docker

Le compose source est:
- `deploy/docker/docker-compose.yml`

URL applicative typique:
```env
DATABASE_URL=postgresql://fabouanes:fabouanes_change_me@localhost:5432/fabouanes
```

## Base de donnees

- Creation des tables automatique au premier demarrage
- Migrations SQL appliquees automatiquement
- Import SQLite historique toujours supporte si un ancien `database.db` est present

## API

- `GET /api/v1`
- `GET /api/v1/ping`
- `GET /api/v1/dashboard/summary`
- Swagger: `GET /api/docs`

## Reseau multi-postes

- Lancer serveur sur PC principal
- Verifier pare-feu Windows
- Acceder depuis les postes clients via `http://IP_PC_SERVEUR:5000`

## Android wrapper

- Client WebView Capacitor
- Configuration URL serveur + QR conservee
- Utilisation uniquement sur meme reseau local pour acces direct

## Tests

```powershell
python -m unittest discover -s tests -v
```

Integration tests:
- definir `TEST_DATABASE_URL` (base PostgreSQL de test dediee)
