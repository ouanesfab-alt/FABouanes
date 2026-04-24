@echo off
title FABOuanes - Compilation EXE avec tests
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
color 0A

echo.
echo  ==========================================
echo   FABOuanes - Tests puis creation du .EXE
echo  ==========================================
echo.

set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo  ERREUR: Python manquant.
    echo  Telecharge Python sur https://www.python.org/downloads/
    echo  IMPORTANT: coche "Add Python to PATH" pendant l'installation.
    echo  Installe Python puis relance ce script.
    pause
    exit /b 1
)

echo  [1/4] Installation / verification des dependances...
%PY_CMD% -m pip install -r requirements.txt pyinstaller pywebview --quiet
if errorlevel 1 (
    echo.
    echo  ERREUR: installation des dependances impossible.
    pause
    exit /b 1
)

echo.
echo  [2/4] Execution des tests...
%PY_CMD% -u -m unittest discover -s tests -v
if errorlevel 1 (
    echo.
    echo  ECHEC: les tests ont echoue. Compilation annulee.
    pause
    exit /b 1
)

echo.
echo  [3/4] Compilation de l'EXE (3-5 minutes)...
%PY_CMD% -m PyInstaller ^
    --noconfirm --clean ^
    --name "FABOuanes" ^
    --icon "static\FABOuanes_desktop.ico" ^
    --onedir --noconsole ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data ".env.example;." ^
    --hidden-import "fastapi" ^
    --hidden-import "starlette" ^
    --hidden-import "uvicorn" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "python_multipart" ^
    --hidden-import "itsdangerous" ^
    --hidden-import "anyio" ^
    --hidden-import "requests" ^
    --hidden-import "requests.adapters" ^
    --hidden-import "reportlab.pdfgen" ^
    --hidden-import "reportlab.lib" ^
    --hidden-import "reportlab.lib.pagesizes" ^
    --hidden-import "reportlab.lib.styles" ^
    --hidden-import "reportlab.lib.units" ^
    --hidden-import "openpyxl" ^
    --hidden-import "dotenv" ^
    --hidden-import "jinja2" ^
    --hidden-import "jinja2.ext" ^
    --hidden-import "pg8000.dbapi" ^
    --hidden-import "werkzeug" ^
    --hidden-import "werkzeug.serving" ^
    --hidden-import "webview" ^
    --hidden-import "webview.platforms.edgechromium" ^
    --collect-submodules "webview" ^
    run_prod.py

if errorlevel 1 (
    echo.
    echo  ERREUR: compilation de l'EXE echouee.
    pause
    exit /b 1
)

echo.
echo  [4/4] Nettoyage...
if exist build rmdir /s /q build 2>nul
if exist FABOuanes.spec del FABOuanes.spec 2>nul

echo.
echo  ==========================================
echo   SUCCES !  dist\FABOuanes\FABOuanes.exe
echo  ==========================================
echo.
if not defined FAB_NO_PAUSE pause
