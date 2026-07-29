@echo off
setlocal enabledelayedexpansion
title FABOuanes
cd /d %~dp0
echo.
echo  Demarrage de FABOuanes...
echo  AZUL ...
echo  (Accessible localement et sur le reseau Wi-Fi local pour l'application Android)
echo.

REM --- Detecter Python ---
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

REM --- Verification des dependances ---
echo  Verification des dependances...
%PY_CMD% -c "import fastapi, uvicorn, sqlalchemy, alembic, pg8000" >nul 2>&1
if errorlevel 1 (
    echo  Installation/verification des dependances - connexion requise...
    %PY_CMD% -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo  ATTENTION: impossible d'installer les dependances de requirements.txt.
        echo  Tentative de lancement de l'application quand meme...
    )
)

REM --- Auto-demarrage PostgreSQL ---
set "PG_SVC="
for /f "usebackq tokens=*" %%s in (`powershell -Command "Get-Service -Name 'postgresql*' | Select-Object -ExpandProperty Name" 2^>nul`) do (
    set "PG_SVC=%%s"
)

if not defined PG_SVC (
    echo  [INFO] Aucun service PostgreSQL detecte via Windows Services.
    goto :launch
)

echo  Service PostgreSQL detecte : !PG_SVC!

REM Verifier l'etat du service (Status == Running)
set "PG_RUNNING=0"
for /f "usebackq tokens=*" %%s in (`powershell -Command "(Get-Service -Name '!PG_SVC!').Status" 2^>nul`) do (
    if /i "%%s"=="Running" set "PG_RUNNING=1"
)

if "!PG_RUNNING!"=="1" (
    echo  PostgreSQL est deja en cours d'execution.
    goto :launch
)

echo  PostgreSQL est arrete. Demarrage du service !PG_SVC!...

REM Tenter le demarrage direct
net start "!PG_SVC!" >nul 2>&1
if not errorlevel 1 (
    echo  PostgreSQL demarre avec succes.
    goto :pg_wait
)

REM Si pas admin ou si timeout -w, corriger le binPath sans -w et demarrer via UAC
echo  Demande d'autorisation Administrateur (UAC) pour corriger et demarrer PostgreSQL...
powershell -Command "Start-Process cmd.exe -ArgumentList '/c sc config `"!PG_SVC!`" binPath= `\`"C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe`\`" runservice -N `\`"!PG_SVC!`\`" -D `\`"C:\Program Files\PostgreSQL\18\data`\`" ^& net start `"!PG_SVC!`"' -Verb RunAs -Wait" >nul 2>&1

:pg_wait
echo  Attente que PostgreSQL soit pret à recevoir des connexions...
set "PG_READY=0"
for /l %%i in (1,1,25) do (
    if "!PG_READY!"=="0" (
        powershell -Command "Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -InformationLevel Quiet" 2>nul | findstr /i "True" >nul
        if not errorlevel 1 (
            set "PG_READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)

if "!PG_READY!"=="1" (
    echo  PostgreSQL est pret sur 127.0.0.1:5432 !
) else (
    echo  [WARN] PostgreSQL est en cours de demarrage...
)

:launch
set FAB_HOST=0.0.0.0
set SESSION_COOKIE_SECURE=0
%PY_CMD% launcher.py --server
pause
