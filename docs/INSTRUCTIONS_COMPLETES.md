# FABOuanes - Guide rapide

## Prerequis
1. Installe Python 3 depuis `python.org/downloads`.
2. Prepare une base PostgreSQL accessible depuis la machine.
3. Copie `.env.example` vers `.env` et renseigne `DATABASE_URL`.

## Lancer l'application
1. Double-clique sur `LANCER.bat`.
2. Le script redirige vers `DOUBLE_CLIC_LANCER_TOUT.bat`.
3. Le lanceur remet `admin / 0000`, puis demarre FastAPI/Uvicorn.

## Lancer FABOuanes en mode reseau Android
1. Double-clique sur `DOUBLE_CLIC_LANCER_TOUT.bat`.
2. Le serveur demarre en `FAB_HOST=0.0.0.0`.
3. L'URL locale reste `http://127.0.0.1:5000` et la connexion mobile utilise l'IP LAN detectee.

## Lancer les tests
1. Definis `TEST_DATABASE_URL` vers une base PostgreSQL de test dediee.
2. Lance `LANCER_TESTS.bat` ou `python -m unittest discover -s tests -v`.

## Creer l'EXE Windows
1. Double-clique sur `deploy\windows\COMPILER_EXE_AVEC_TESTS.bat`.
2. Les tests sont lances avant la compilation.
3. Si tout est bon, l'EXE est genere dans `dist\FABOuanes\FABOuanes.exe`.

## Docker
- Un environnement PostgreSQL pret a l'emploi est fourni dans `deploy\docker\docker-compose.yml`.
- L'URL par defaut cote application est `postgresql://fabouanes:fabouanes_change_me@postgres:5432/fabouanes`.

## Donnees
- Les donnees applicatives vivent desormais dans PostgreSQL.
- Le projet n'embarque plus de base SQLite `database.db`.
- Si une ancienne base SQLite `database.db` existe encore dans le dossier applicatif local ou a la racine du projet, elle est importee automatiquement au premier demarrage sur PostgreSQL.
- Les sauvegardes applicatives PostgreSQL sont stockees dans `C:\Users\NOM\AppData\Local\FABOuanes\backups\local\`.

## Nettoyage
- Lance `NETTOYAGE_GENERAL.bat` pour supprimer les logs, `__pycache__` et caches de tests.

## Organisation du projet
- `fabouanes\` contient le code Python principal.
- `templates\` et `static\` contiennent l'interface web.
- `android_wrapper\` contient le client Android Capacitor.
- `deploy\windows\` contient les scripts de build Windows et Inno Setup.
- `deploy\docker\` contient les fichiers Docker.
- `docs\` contient la documentation.
