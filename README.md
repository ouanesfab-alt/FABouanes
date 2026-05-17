# FABOuanes FastAPI

FABOuanes est maintenant expose par une entree **FastAPI** tout en preservant:

- les templates et le rendu UI existants,
- les workflows metier,
- la base PostgreSQL existante,
- la compatibilite mobile `/api/v1`,
- le packaging desktop Windows.

La migration FastAPI est maintenant la source principale:

- `app/` contient la plateforme, le metier et la persistence,
- l'ancien paquet Flask `fabouanes/` a ete retire,
- les proxys de transition ont ete remplaces par des routes FastAPI natives.

## Structure principale

```text
app/
  main.py
  core/
  api/
  web/
  services/
  repositories/
  utils/
templates/
static/
tests/
launcher/
installer/windows/
alembic/
```

## Prerequis

- Python 3.11+
- Windows 10/11 pour le packaging desktop
- Inno Setup 6 pour produire l'installateur

## Installation locale

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuration

Copier `.env.example` en `.env` si besoin, puis ajuster:

- `SECRET_KEY`
- `DATABASE_URL` pour PostgreSQL local, avec les identifiants du poste
- `FAB_HOST`
- `FAB_PORT`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`

La configuration serveur exige PostgreSQL local. La valeur de `DATABASE_URL` n'est pas universelle: chaque poste doit utiliser l'utilisateur, le mot de passe, l'hote et le port PostgreSQL configures localement.

Exemple pour ce poste:

```env
DATABASE_URL=postgresql://postgres:0000@127.0.0.1:5432/fabouanes
```

Exemple avec un utilisateur PostgreSQL dedie:

```env
DATABASE_URL=postgresql://fabouanes:mot_de_passe@127.0.0.1:5432/fabouanes
```

### PostgreSQL sur une nouvelle machine

Sur une nouvelle installation, installer PostgreSQL, puis creer la base et l'utilisateur dedie:

```sql
CREATE USER fabouanes WITH PASSWORD 'mot_de_passe_a_choisir';
CREATE DATABASE fabouanes OWNER fabouanes;
GRANT ALL PRIVILEGES ON DATABASE fabouanes TO fabouanes;

\c fabouanes

GRANT ALL ON SCHEMA public TO fabouanes;
ALTER SCHEMA public OWNER TO fabouanes;
```

Ensuite copier `.env.example` en `.env`, puis adapter `DATABASE_URL` avec le mot de passe choisi sur cette machine:

```env
DATABASE_URL=postgresql://fabouanes:mot_de_passe_a_choisir@127.0.0.1:5432/fabouanes
```

Si l'installation utilise l'utilisateur PostgreSQL `postgres` au lieu de l'utilisateur dedie, remplacer seulement l'utilisateur et le mot de passe:

```env
DATABASE_URL=postgresql://postgres:MOT_DE_PASSE_DU_POSTE@127.0.0.1:5432/fabouanes
```

Sur ce poste, l'exemple local est `postgres:0000`, mais sur une autre machine il faut mettre le mot de passe PostgreSQL de cette machine. L'application cree/migre les tables au premier demarrage.

En mode serveur (`FAB_DESKTOP=0`), une `DATABASE_URL` manquante arrete le demarrage avec une erreur explicite.

## Lancer le serveur FastAPI

### Developpement

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### Serveur simple

```powershell
python -m launcher.run_server
```

Le serveur ecoute par defaut sur `0.0.0.0:5000` pour le mode reseau. `0.0.0.0` est l'adresse d'ecoute du serveur, pas l'URL a ouvrir dans le navigateur.

URLs a utiliser:

- sur la machine serveur: `http://127.0.0.1:5000`
- sur une machine cliente du meme reseau: `http://IP_DU_SERVEUR:5000` par exemple `http://192.168.1.32:5000`
- dans les logs techniques: `0.0.0.0:5000` signifie seulement que le serveur accepte les connexions reseau

La fenetre console doit rester ouverte en mode serveur. Utiliser `Ctrl+C` pour arreter le serveur.
Le runtime in-process actuel impose `WEB_CONCURRENCY=1`: le cache et le scheduler de sauvegarde ne doivent pas tourner avec plusieurs workers sans cache/scheduler externe.

Depuis Windows, `LANCER.bat` lance aussi ce mode serveur reseau par defaut. La commande equivalente est:

```powershell
python launcher.py --server
```

## Lancer le client desktop

```powershell
python launcher.py
```

Le lanceur:

- prepare les dossiers runtime,
- initialise/migre la base PostgreSQL par defaut,
- demarre Uvicorn en mode reseau sur `0.0.0.0`,
- ouvre l'UI dans WebView,
- conserve la compatibilite avec le QR mobile.

Le client desktop reste disponible avec `python launcher.py`; il ouvre la WebView locale mais garde l'acces reseau actif. Les autres machines du meme reseau utilisent l'adresse affichee au lancement, par exemple `http://192.168.1.32:5000`.

Garder la fenetre FABOuanes ouverte sur la machine serveur pour laisser les autres machines connectees. Si une machine cliente ne se connecte pas, autoriser Python/FABOuanes dans le pare-feu Windows sur le reseau prive.



## Espace bons

Le menu `Outils > Espace bons` remplace l'ancien lecteur PDF. Il permet de chercher et lire:

- les bons d'achat,
- les bons de vente,
- les bons de versement et d'avance,
- les bons de production,
- les historiques client,
- les PDF externes importes manuellement.

## Tests

La nouvelle base de tests utilise `pytest`.

```powershell
python -m pytest
```

En local hors CI, les tests utilisent la base PostgreSQL configuree (via le cluster temporaire instancie automatiquement pour les tests).

Les tests FastAPI sont organises par domaine:

- `tests/web/`
- `tests/api/`
- `tests/services/`
- `tests/printing/`

## Push GitHub

Depuis la racine, le script `PUSH_GITHUB.bat` ajoute les changements, cree un commit, fait un `pull --rebase`, puis pousse la branche courante vers `origin`.

## Base de donnees et migrations

La migration preserve le schema existant.

- bootstrap schema: `app.core.schema.init_db()`
- moteur SQLAlchemy Core: `app/core/database.py`
- revisionning: `alembic/`

Au demarrage:

1. les dossiers runtime sont assures,
3. le schema applicatif est bootstrappe,
4. Alembic fait `stamp base` uniquement si `alembic_version` n'existe pas, puis `upgrade head`.

Regle transactionnelle: toute operation metier multi-etapes doit etre enveloppee dans `db_transaction()` pour garantir un seul commit atomique sur PostgreSQL.

## Packaging Windows

### Construire l'EXE

```powershell
installer\windows\COMPILER_EXE_AVEC_TESTS.bat
```

### Construire l'installateur

```powershell
installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat
```

Raccourci depuis la racine:

```powershell
CREER_INSTALLATEUR_WINDOWS.bat
```

Artefacts attendus:

- `dist\FABOuanes\FABOuanes.exe`
- `installer_output\FABOuanes_Setup.exe`

Les scripts sous `deploy\windows\` sont de simples wrappers de compatibilite vers `installer\windows\`.

## Points de transition importants

- `app/main.py` est maintenant l'entree ASGI principale.
- `app.py` et `wsgi.py` sont des shims de compatibilite.
- `app/core/`, `app/services/` et `app/repositories/` portent maintenant la logique auparavant dupliquee.
- le montage WSGI global Flask et les proxys de transition ont ete retires.

## Fichiers utiles

- `app/main.py`
- `app/web/`
- `app/api/v1/`
- `app/core/database.py`
- `launcher.py`
- `launcher/run_server.py`
- `installer/windows/FABOuanes_Setup.iss`
- `MIGRATION_REPORT.md`
