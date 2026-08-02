@echo off
setlocal EnableExtensions
title FABOuanes ERP - Application Desktop Windows
cd /d "%~dp0"
color 0B

echo.
echo  ===========================================================
echo         FABOUANES ERP - APPLICATION DESKTOP WINDOWS
echo  ===========================================================
echo  Lancement de l'environnement natif Windows 10 / 11...
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

rem Auto-génération du fichier .env si absent
if not exist ".env" (
    echo [INFO] Génération automatique de la configuration .env...
    %PY_CMD% -c "import secrets,random; pin=f'{random.randint(1000,9999):04d}'; print('FASTAPI_ENV=production\nDATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/fabouanes\nSECRET_KEY=' + secrets.token_hex(32) + '\nFAB_HOST=0.0.0.0\nFAB_PORT=5000\nFAB_HTTPS=0\nDEFAULT_ADMIN_USERNAME=admin\nDEFAULT_ADMIN_PASSWORD=' + pin + '\nFAB_PASSWORD_MODE=pin')" > .env
)

rem Lancement en mode Fenêtre Desktop Windows
%PY_CMD% launcher.py %*

endlocal
