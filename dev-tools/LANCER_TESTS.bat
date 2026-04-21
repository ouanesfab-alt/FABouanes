@echo off
title FABOuanes - Tests
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo.
echo  Lancement des tests FABOuanes...
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
    echo  Telecharge Python sur https://www.python.org/downloads/
    echo  IMPORTANT: coche "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)

echo  Installation / verification des dependances...
%PY_CMD% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo  ERREUR: impossible d'installer les dependances.
    pause
    exit /b 1
)

echo.
echo  Execution des tests...
%PY_CMD% -u -m unittest discover -s tests -v
if errorlevel 1 (
    echo.
    echo  ECHEC: au moins un test a echoue.
    pause
    exit /b 1
)

echo.
echo  SUCCES: tous les tests sont passes.
pause
