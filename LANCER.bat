@echo off
setlocal EnableExtensions
title FABOuanes ERP - Windows Server
cd /d "%~dp0"
color 0A

echo.
echo  ===========================================================
echo         FABOUANES ERP - DEMARRAGE DU SERVEUR WINDOWS
echo  ===========================================================
echo  Accès local et réseau Wi-Fi sécurisé
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

rem Verification et installation automatique du fichier .env
if not exist ".env" (
    echo [INFO] Génération du fichier de configuration .env...
    %PY_CMD% -c "import secrets,random; pin=f'{random.randint(1000,9999):04d}'; print('FASTAPI_ENV=production\nDATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/fabouanes\nSECRET_KEY=' + secrets.token_hex(32) + '\nFAB_HOST=0.0.0.0\nFAB_PORT=5000\nFAB_HTTPS=0\nDEFAULT_ADMIN_USERNAME=admin\nDEFAULT_ADMIN_PASSWORD=' + pin + '\nFAB_PASSWORD_MODE=pin')" > .env
    for /f "tokens=2 delims==" %%A in ('findstr "DEFAULT_ADMIN_PASSWORD" .env') do echo [IMPORTANT] Code PIN admin genere: %%A
)

echo [1/3] Vérification des dépendances Python...
%PY_CMD% -c "import fastapi, uvicorn, sqlalchemy, alembic, cryptography, qrcode" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation des dépendances requises...
    %PY_CMD% -m pip install -r requirements.txt --quiet
)

echo [2/3] Vérification du service PostgreSQL...
%PY_CMD% -c "from launcher import ensure_postgres_running; ensure_postgres_running()"

echo [3/3] Lancement du serveur d'application...
set FAB_HOST=0.0.0.0
set SESSION_COOKIE_SECURE=0
%PY_CMD% launcher.py --server
pause
endlocal
