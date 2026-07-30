@echo off
setlocal EnableExtensions
title FABOuanes ERP - Windows Server
cd /d "%~dp0"
color 0A

echo.
echo  ===========================================================
echo         FABOUANES ERP - DEMARRAGE DU SERVEUR WINDOWS
echo  ===========================================================
echo  Accès local et réseau Wi-Fi sécurisé (HTTPS)
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

rem Verification et installation automatique du fichier .env
if not exist ".env" (
    echo [INFO] Génération du fichier de configuration .env...
    %PY_CMD% -c "import secrets; print('FASTAPI_ENV=production\nDATABASE_URL=postgresql://postgres:0000@127.0.0.1:5432/fabouanes\nSECRET_KEY=' + secrets.token_hex(32) + '\nFAB_HOST=0.0.0.0\nFAB_PORT=5000\nFAB_HTTPS=1\nDEFAULT_ADMIN_USERNAME=admin\nDEFAULT_ADMIN_PASSWORD=7508\nFAB_PASSWORD_MODE=pin')" > .env
)

echo [1/3] Vérification des dépendances Python...
%PY_CMD% -c "import fastapi, uvicorn, sqlalchemy, alembic, pg8000, cryptography, qrcode" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation des dépendances requises...
    %PY_CMD% -m pip install -r requirements.txt --quiet
)

echo [2/3] Vérification du service PostgreSQL...
%PY_CMD% -c "from launcher import ensure_postgres_running; ensure_postgres_running()"

echo [3/3] Ouverture automatique du navigateur dans 3 secondes...
powershell -Command "Start-Sleep -Seconds 3; Start-Process 'https://127.0.0.1:5000'" >nul 2>&1 &

set FAB_HOST=0.0.0.0
set FAB_HTTPS=1
set SESSION_COOKIE_SECURE=0
%PY_CMD% launcher.py --server --https
pause
endlocal
