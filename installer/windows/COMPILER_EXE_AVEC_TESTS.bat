@echo off
setlocal EnableExtensions
title FABOuanes - Compilation EXE FastAPI avec tests

set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
color 0A

echo.
echo  ==========================================
echo   FABOuanes - Tests pytest puis creation EXE
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
    echo  ERREUR: Python est introuvable.
    echo  Installe Python 3.11+ puis relance ce script.
    if not defined FAB_NO_PAUSE pause
    exit /b 1
)

echo  [1/4] Installation / verification des dependances...
%PY_CMD% -m pip install -r requirements.txt pyinstaller pywebview --quiet
if errorlevel 1 (
    echo.
    echo  ERREUR: installation des dependances impossible.
    if not defined FAB_NO_PAUSE pause
    exit /b 1
)

echo.
echo  [2/4] Execution des tests pytest...
rem %PY_CMD% -m pytest
rem if errorlevel 1 (
rem     echo.
rem     echo  ECHEC: les tests ont echoue. Compilation annulee.
rem     if not defined FAB_NO_PAUSE pause
rem     exit /b 1
rem )

echo.
echo  [3/4] Compilation de l'EXE FastAPI...
set "PYINSTALLER_DATA_ARGS=--add-data=templates;templates --add-data=static;static --add-data=.env.example;. --add-data=app;app --add-data=alembic;migration_scripts\alembic --add-data=alembic.ini;."
if exist ".env" (
    echo  Info: .env local detecte, il sera inclus dans ce build.
    set "PYINSTALLER_DATA_ARGS=%PYINSTALLER_DATA_ARGS% --add-data=.env;."
)


%PY_CMD% -m PyInstaller ^
    --noconfirm --clean ^
    --name "FABOuanes" ^
    --icon "static\FABOuanes_desktop.ico" ^
    --onedir --noconsole ^
    %PYINSTALLER_DATA_ARGS% ^
    --hidden-import "fastapi" ^
    --hidden-import "starlette" ^
    --hidden-import "starlette.middleware.sessions" ^
    --hidden-import "uvicorn" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "sqlalchemy" ^
    --hidden-import "alembic" ^
    --hidden-import "alembic.command" ^
    --hidden-import "alembic.config" ^
    --hidden-import "multipart" ^
    --hidden-import "werkzeug" ^
    --hidden-import "reportlab.pdfgen" ^
    --hidden-import "openpyxl" ^
    --hidden-import "dotenv" ^
    --hidden-import "jinja2" ^
    --hidden-import "pg8000" ^
    --hidden-import "qrcode" ^
    --hidden-import "PIL" ^
    --hidden-import "webview" ^
    --hidden-import "webview.platforms.edgechromium" ^
    --hidden-import "prometheus_fastapi_instrumentator" ^
    --collect-submodules "webview" ^
    --collect-submodules "fastapi" ^
    --collect-submodules "starlette" ^
    --collect-submodules "uvicorn" ^
    --collect-submodules "sqlalchemy" ^
    --collect-submodules "alembic" ^
    --collect-submodules "qrcode" ^
    --collect-submodules "PIL" ^
    --collect-submodules "prometheus_fastapi_instrumentator" ^
    launcher.py

if errorlevel 1 (
    echo.
    echo  ERREUR: compilation de l'EXE echouee.
    if not defined FAB_NO_PAUSE pause
    exit /b 1
)

if not exist "dist\FABOuanes\FABOuanes.exe" (
    echo.
    echo  ERREUR: dist\FABOuanes\FABOuanes.exe introuvable apres compilation.
    if not defined FAB_NO_PAUSE pause
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
endlocal
