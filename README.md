# FABOuanes v2 - FastAPI + PostgreSQL (Version Pro Reseau)

Application de gestion commerciale FABOuanes avec:
- backend Python FastAPI/Uvicorn
- base PostgreSQL
- API REST `/api/v1/...`
- interface web existante (UI/UX conservee)
- wrapper Android Capacitor (WebView mobile)

## 1. Prerequis

- Python 3.11+ (3.12 recommande)
- PostgreSQL 16+ ou Docker Desktop
- Node.js uniquement si build Android/Capacitor

## 2. Demarrage rapide Windows (double-clic)

1. Double-clique `START_POSTGRES.bat` (si tu utilises Docker).
2. Double-clique `DOUBLE_CLIC_LANCER_TOUT.bat`.
3. Si `.env` n'existe pas, il est cree depuis `.env.example` puis le script s'arrete pour te laisser configurer `DATABASE_URL`.
4. Ouvre ensuite `http://127.0.0.1:5000`.

Le lanceur:
- cree automatiquement `.venv` si absent
- installe `requirements.txt`
- lance le serveur en mode reseau (`0.0.0.0:5000`)
- ouvre le navigateur automatiquement
- ne reset plus l'admin automatiquement

## 3. PostgreSQL (Docker)

### Lancer PostgreSQL/Redis
- `START_POSTGRES.bat`

### Arreter PostgreSQL/Redis
- `STOP_POSTGRES.bat`

Le compose utilise `deploy/docker/docker-compose.yml`.

## 4. Configuration `.env`

Copie `.env.example` vers `.env` (fait automatiquement si absent), puis configure:

```env
DATABASE_URL=postgresql://fabouanes:password@localhost:5432/fabouanes
SECRET_KEY=change_me
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=ChangeMe!234
```

Variables utiles:
- `FAB_HOST` et `FAB_PORT` (lanceur par defaut: `0.0.0.0:5000`)
- `DB_POOL_SIZE`, `DB_POOL_TIMEOUT_SECONDS`
- `REDIS_URL` (cache Redis optionnel)
- `API_DOCS_ENABLED`, `API_DOCS_PATH`, `API_OPENAPI_PATH`
- `CORS_ALLOW_ALL`, `CORS_ALLOW_ORIGINS`
- `LOG_LEVEL`

## 5. Base de donnees et migrations

- Les tables sont creees automatiquement au premier lancement.
- Les migrations SQL internes sont executees automatiquement.
- Compatibilite import SQLite conservee:
  - base locale applicative `database.db`
  - `database.db` deposee manuellement a la racine
- Avant import, l'application conserve une sauvegarde PostgreSQL JSON.
- Les seeds demo sont optionnels: `SEED_DEMO.bat`.

## 6. Identifiants admin

- L'admin par defaut est cree seulement s'il n'existe pas deja.
- Le reset de secours est manuel uniquement:
  - `RESET_ADMIN_SECOURS.bat`
- Changement de mot de passe depuis l'interface: menu utilisateur > changer mot de passe.

## 7. API / Swagger

- API: `/api/v1/...`
- Swagger UI: `/api/docs`
- OpenAPI JSON: `/api/openapi.json`
- ReDoc: `/api/redoc`
- erreurs API standardisees (`internal_error`, `validation_error`, etc.) avec `request_id`
- logs HTTP structures JSON (method, path, status, duration, request_id)

## 8. Acces multi-postes et mobile

Pour un poste client/mobile:
1. PC serveur et client sur le meme reseau Wi-Fi/LAN.
2. Lancer FABOuanes sur le PC serveur.
3. Utiliser l'IP locale du PC serveur:
   - exemple `http://192.168.1.X:5000`
4. Verifier le pare-feu Windows.

Android Capacitor:
- c'est un client WebView (pas une app native 100% offline)
- configuration URL serveur + scan QR conserves

## 9. Sauvegarde / restauration

Format sauvegarde PostgreSQL: `.json` (pas `.db`).

Depuis l'interface:
- Outils/Administration pour sauvegarder
- restauration depuis un backup JSON valide

## 10. Tests

Tests complets:
```powershell
python -m unittest discover -s tests -v
```

Couverture:
```powershell
coverage run -m unittest discover -s tests -v
coverage report
coverage xml
```
ou `COVERAGE_TESTS.bat`.

Qualite code:
```powershell
ruff check fabouanes/fastapi_compat.py fabouanes/presentation/api_validation.py fabouanes/routes/route_utils.py
black --check fabouanes/fastapi_compat.py fabouanes/presentation/api_validation.py fabouanes/routes/route_utils.py app.py run_prod.py
mypy
```
ou `QUALITE_CODE.bat`.

Tests d'integration:
- definir `TEST_DATABASE_URL` vers une base PostgreSQL de test dediee

CI/CD:
- pipeline GitHub Actions: `.github/workflows/ci.yml`
- lint + format check + mypy + tests + coverage xml

## 11. Generer un ZIP livrable propre

Utilise:
- `GENERER_ZIP_LIVRABLE.bat`

Le ZIP exclut:
- `.venv/`
- `.git/`
- `.env` reel
- `__pycache__/`, `.pytest_cache/`
- `build/`, `dist/`
- logs temporaires

## 12. Depannage rapide

Erreur connexion DB:
- verifier `DATABASE_URL`
- verifier que PostgreSQL est demarre
- verifier que la base existe

Mode reseau indisponible:
- lancer avec `DOUBLE_CLIC_LANCER_TOUT.bat`
- verifier pare-feu Windows
- verifier IP locale du serveur

Login admin perdu:
- lancer `RESET_ADMIN_SECOURS.bat`

Swagger indisponible:
- verifier `API_DOCS_ENABLED=1`
- verifier URL `/api/docs`
