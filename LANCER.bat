@echo off
title FABOuanes ERP
cd /d "%~dp0"
echo.
echo ===========================================================
echo        FABOUANES ERP - DEMARRAGE DU SERVEUR WINDOWS
echo ===========================================================
echo AZUL
echo Accessible localement et sur le reseau Wi-Fi local
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

echo Verification des dependances...
%PY_CMD% -c "import fastapi, uvicorn, sqlalchemy, alembic, pg8000, cryptography, qrcode" >nul 2>&1
if errorlevel 1 (
    echo Installation des dependances requises...
    %PY_CMD% -m pip install -r requirements.txt --quiet
)

echo Verification du service PostgreSQL...
%PY_CMD% -c "from launcher import ensure_postgres_running; ensure_postgres_running()"

set FAB_HOST=0.0.0.0
set FAB_HTTPS=1
set SESSION_COOKIE_SECURE=0
%PY_CMD% launcher.py --server --https
pause
