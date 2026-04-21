# FABOuanes - Guide rapide

## Prerequis
1. Installe Python 3 depuis `python.org/downloads`.
2. Pendant l'installation, coche `Add Python to PATH`.
3. Sous Windows, les scripts privilegient `py -3` puis basculent sur `python` si besoin.

## Lancer l'application
1. Double-clique sur `LANCER.bat`.
2. Le script installe les dependances depuis `requirements.txt`.
3. L'application desktop demarre ensuite via `launcher.py`.

## Lancer FABOuanes en mode reseau Android
1. Double-clique sur `LANCER_ANDROID_RESEAU.bat`.
2. Le script installe les dependances depuis `requirements.txt`.
3. Le serveur demarre sur le reseau local pour l'application Android.

## Lancer les tests
1. Double-clique sur `LANCER_TESTS.bat`.
2. Le script verifie `requirements.txt` puis execute `python -m unittest discover -s tests -v`.

## Creer l'EXE Windows
1. Double-clique sur `COMPILER_EXE_AVEC_TESTS.bat`.
2. Les tests sont lances avant la compilation.
3. Si tout est bon, l'EXE est genere dans `dist\FABOuanes\FABOuanes.exe`.

## Android
- Le wrapper Android sert a configurer l'URL du serveur, scanner un QR et ouvrir l'application web complete.
- L'APK debug se construit avec `deploy\android\BUILD_APK_DEBUG.bat`.
- L'APK attendu est `android_wrapper\android\app\build\outputs\apk\debug\app-debug.apk`.

## Organisation du projet
- `fabouanes\` contient le code Python principal.
- `templates\` et `static\` contiennent l'interface web.
- `android_wrapper\` contient le client Android Capacitor.
- `deploy\windows\` contient les scripts de build Windows et Inno Setup.
- `deploy\docker\` contient les fichiers Docker.
- `docs\` contient la documentation.

## Donnees locales
- Les donnees utilisateur sont stockees dans `C:\Users\NOM\AppData\Local\FABOuanes\`.
- Si tu reutilises une ancienne base, conserve simplement le fichier `database.db`.
- Les dossiers generes (`dist`, `installer_output`, `node_modules`, builds Android) sont des artefacts et ne doivent pas servir de source de verite.
