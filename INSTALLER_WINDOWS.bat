@echo off
setlocal EnableExtensions
title FABOuanes ERP - Installation & Configuration Windows 10/11
cd /d "%~dp0"
color 0B

echo.
echo  ========================================================================
echo         FABOUANES ERP ENTERPRISE - INSTALLATION NATIVE WINDOWS 10/11
echo  ========================================================================
echo  Logiciel de Gestion Commerciale, Stocks, Production & Comptabilité SCF
echo  ========================================================================
echo.

set "PY_CMD=python"
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

rem 1. Vérification de Python 3.10+
echo [1/5] Vérification de l'environnement Python...
%PY_CMD% -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python 3.10 ou supérieur est requis.
    echo Téléchargement recommandé depuis : https://www.python.org/downloads/
    pause
    exit /b 1
)
echo        [OK] Python opérationnel.

rem 2. Génération automatique du fichier de configuration .env si absent
echo [2/5] Configuration du fichier d'environnement .env...
if not exist ".env" (
    %PY_CMD% -c "import secrets,random; pin=f'{random.randint(1000,9999):04d}'; print('FASTAPI_ENV=production\nDATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/fabouanes\nSECRET_KEY=' + secrets.token_hex(32) + '\nFAB_HOST=0.0.0.0\nFAB_PORT=5000\nFAB_HTTPS=0\nDEFAULT_ADMIN_USERNAME=admin\nDEFAULT_ADMIN_PASSWORD=' + pin + '\nFAB_PASSWORD_MODE=pin')" > .env
    for /f "tokens=2 delims==" %%A in ('findstr "DEFAULT_ADMIN_PASSWORD" .env') do (
        echo        [NOTE] Code PIN Administrateur généré : %%A
    )
    echo        [OK] Configuration .env générée avec succès.
) else (
    echo        [OK] Fichier .env déjà présent.
)

rem 3. Installation et vérification des dépendances Python
echo [3/5] Installation et vérification des dépendances système...
%PY_CMD% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ATTENTION] Échec d'installation silencieuse, nouvelle tentative en mode verbeux...
    %PY_CMD% -m pip install -r requirements.txt
)
echo        [OK] Dépendances Python installées.

rem 4. Création automatique du raccourci Bureau & Menu Démarrer Windows 10/11
echo [4/5] Création des raccourcis Windows (Bureau & Menu Démarrer)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $s = $w.CreateShortcut([System.IO.Path]::Combine($desktop, 'FABOuanes ERP.lnk')); $s.TargetPath = '%cd%\LANCER.bat'; $s.WorkingDirectory = '%cd%'; $s.IconLocation = '%cd%\static\FABOuanes_desktop.ico'; $s.Description = 'FABOuanes ERP Enterprise'; $s.Save()" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $programs = [Environment]::GetFolderPath('Programs'); $s = $w.CreateShortcut([System.IO.Path]::Combine($programs, 'FABOuanes ERP.lnk')); $s.TargetPath = '%cd%\LANCER.bat'; $s.WorkingDirectory = '%cd%'; $s.IconLocation = '%cd%\static\FABOuanes_desktop.ico'; $s.Description = 'FABOuanes ERP Enterprise'; $s.Save()" >nul 2>&1
echo        [OK] Raccourcis 'FABOuanes ERP' créés sur le Bureau et le Menu Démarrer.

rem 5. Lancement de l'application en mode Fenêtre Windows Desktop
echo [5/5] Lancement de FABOuanes ERP en mode Fenêtre Desktop...
echo.
echo ========================================================================
echo   INSTALLATION REUSSIE ! L'application de bureau démarre...
echo ========================================================================
echo.

start "" %PY_CMD% launcher.py

endlocal
