@echo off
setlocal EnableExtensions
title FABOuanes - Création Installateur Windows
cd /d "%~dp0..\.."
color 0A

echo.
echo  ===========================================================
echo         FABOUANES ERP - CREATION INSTALLATEUR WINDOWS
echo  ===========================================================
echo.

set "PY_CMD=python"
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

rem 1. Auto-génération du fichier .env de production si absent
if not exist ".env" (
    echo  [1/3] Génération automatique de la configuration .env...
    %PY_CMD% -c "import secrets; print('FASTAPI_ENV=production\nDATABASE_URL=postgresql://postgres:0000@127.0.0.1:5432/fabouanes\nSECRET_KEY=' + secrets.token_hex(32) + '\nFAB_HOST=0.0.0.0\nFAB_PORT=5000\nFAB_HTTPS=1\nDEFAULT_ADMIN_USERNAME=admin\nDEFAULT_ADMIN_PASSWORD=7508\nFAB_PASSWORD_MODE=pin')" > .env
    echo        [OK] Fichier .env créé.
)

rem 2. Autocréation du raccourci Bureau Windows
echo.
echo  [2/3] Création du raccourci officiel sur le Bureau Windows...
powershell -Command "`$w = New-Object -ComObject WScript.Shell; `$s = `$w.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'FABOuanes.lnk')); `$s.TargetPath = '%cd%\LANCER.bat'; `$s.WorkingDirectory = '%cd%'; `$s.IconLocation = '%cd%\static\FABOuanes_desktop.ico'; `$s.Save()"
if not errorlevel 1 (
    echo        [OK] Raccourci 'FABOuanes' créé sur le Bureau Windows.
) else (
    echo        [WARN] Impossible de créer le raccourci Bureau.
)

rem 3. Compilation du package exécutable & installateur Inno Setup
echo.
echo  [3/3] Compilation du package exécutable / installateur...
set "FAB_NO_PAUSE=1"
call "%~dp0BUILD_INSTALLATEUR_DESKTOP.bat"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo  ===========================================================
    echo    SUCCÈS COMPLET : Installateur autonome généré dans :
    echo    installer_output\FABOuanes_Setup.exe
    echo  ===========================================================
) else (
    echo  ===========================================================
    echo    [INFO] Le raccourci Bureau 'FABOuanes' est actif et prêt !
    echo    (Pour générer l'installateur autonome .exe redistribuable,
    echo     installez Inno Setup 6 : https://jrsoftware.org/isinfo.php)
    echo  ===========================================================
)

echo.
pause
endlocal
