# Guide d'Acces - FABOuanes

## Identifiants par defaut

**Username:** `admin`  
**Password:** `1234`

Avec `DOUBLE_CLIC_LANCER_TOUT.bat`, un mot de passe de secours est force a chaque lancement:

**Username:** `admin`  
**Password:** `0000`

## Demarrage local

```powershell
cd "c:\Users\ouane\Documents\FABOuanes_v1"
python run_prod.py
```

Puis ouvre `http://127.0.0.1:5000`.

## Configuration obligatoire

FABOuanes utilise maintenant PostgreSQL. Avant de lancer l'application:

1. Copie `.env.example` vers `.env`.
2. Renseigne `DATABASE_URL`.
3. L'application web est maintenant servie par FastAPI via Uvicorn.

Exemple:

```env
DATABASE_URL=postgresql://fabouanes:password@localhost:5432/fabouanes
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=monNouveauMotDePasse
SECRET_KEY=change_me
```

## Lanceurs disponibles

- `DOUBLE_CLIC_LANCER_TOUT.bat` lance l'application en un double-clic (reset admin + serveur).
- `LANCER.bat` alias du lanceur principal.
- `LANCER_TESTS.bat` lance les tests.
- `NETTOYAGE_GENERAL.bat` nettoie caches/logs locaux.

## Migration automatique

Si une ancienne base SQLite `database.db` existe encore:

- dans le dossier local de l'application
- ou a la racine du projet

elle est importee automatiquement vers PostgreSQL au premier demarrage.
Le projet ne fournit plus de base `database.db` integree.

## Depannage

**Probleme: l'application ne demarre pas**
- Verifie que PostgreSQL est joignable.
- Verifie que `DATABASE_URL` est bien defini.
- Verifie que la base cible existe.

**Probleme: impossible de se connecter**
- Verifie les identifiants `admin / 1234` si c'est un premier demarrage.
- Verifie la console Python pour les erreurs PostgreSQL.

**Probleme: tests d'integration**
- Definis `TEST_DATABASE_URL` vers une base PostgreSQL de test dediee.

## Variables utiles

| Variable | Defaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | requis | URL PostgreSQL |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Username initial |
| `DEFAULT_ADMIN_PASSWORD` | `1234` | Password initial |
| `APP_ENV` | `production` | `development` ou `production` |
| `FAB_HOST` | `0.0.0.0` | Adresse d'ecoute |
| `FAB_PORT` | `5000` | Port d'ecoute |
| `SESSION_COOKIE_SECURE` | `0` | `1` pour HTTPS seulement |
