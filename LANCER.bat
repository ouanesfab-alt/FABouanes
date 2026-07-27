@echo off
title FABOuanes Desktop & Network Server (HTTPS)
cd /d %~dp0
echo.
echo ===================================================
echo   🚀 FABOuanes — Serveur Desktop & Reseau (HTTPS)
echo ===================================================
echo.

set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo  ❌ ERREUR: Python non installe sur ce PC.
    echo  Telechargez Python sur https://www.python.org/downloads/
    echo  IMPORTANT: Cochez "Add Python to PATH" pendant l'installation.
    echo.
    pause & exit /b 1
)

echo 📦 Verification des dependances Python...
%PY_CMD% -c "import fastapi, uvicorn, sqlalchemy, alembic, pg8000" >nul 2>&1
if errorlevel 1 (
    echo ⚡ Installation ultra-rapide des dependances...
    if exist "wheels" (
        %PY_CMD% -m pip install --prefer-binary --no-index --find-links=./wheels -r requirements.txt --quiet 2>nul || %PY_CMD% -m pip install --prefer-binary -r requirements.txt --quiet
    ) else (
        %PY_CMD% -m pip install --prefer-binary -r requirements.txt --quiet
    )
)

echo 🗄️ Verification des services de Base de Donnees PostgreSQL...
net start | findstr /i "postgresql" >nul 2>&1
if errorlevel 1 (
    net start postgresql-x64-18 >nul 2>&1 || net start postgresql-x64-16 >nul 2>&1 || net start postgresql >nul 2>&1
)

set FAB_HOST=0.0.0.0
set FAB_SSL=1

if "%~1"=="--qr" (
    %PY_CMD% launcher.py --qr
    pause & exit /b 0
)

if "%~1"=="--pin" (
    %PY_CMD% launcher.py --pin
    pause & exit /b 0
)

%PY_CMD% launcher.py --server %*
pause
