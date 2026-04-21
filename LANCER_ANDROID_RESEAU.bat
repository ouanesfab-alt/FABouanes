@echo off
title FABOuanes - Reseau Android
cd /d %~dp0
echo.
echo  Demarrage de FABOuanes en mode reseau...
echo  Le serveur sera accessible depuis le telephone Android sur le meme Wi-Fi.
echo.

set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo  ERREUR: Python non installe.
    echo  Telecharge sur https://www.python.org/downloads/
    echo  IMPORTANT: coche "Add Python to PATH" pendant l'installation.
    pause & exit /b 1
)

echo  Installation / verification des dependances...
%PY_CMD% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo  ERREUR: impossible d'installer les dependances de requirements.txt.
    pause & exit /b 1
)

set FAB_HOST=0.0.0.0
%PY_CMD% launcher.py
pause
