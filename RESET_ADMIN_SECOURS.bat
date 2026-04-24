@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Reset admin secours
set "PYTHON_EXE=.venv\Scripts\python.exe"

echo.
echo ========================================
echo   FABOuanes - Reset admin secours
echo ========================================
echo.
echo Ce script est manuel. Il n'est jamais lance automatiquement.
echo.

if not exist "%PYTHON_EXE%" (
  echo Environnement .venv introuvable, preparation...
  py -3 -m venv .venv >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv >nul 2>nul
  )
)

if not exist "%PYTHON_EXE%" (
  echo ERREUR: Python non disponible.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo Le fichier .env a ete cree.
    echo Configure DATABASE_URL puis relance ce script.
    pause
    exit /b 1
  )
)

set "RESET_USER="
set "RESET_PASS="
set /p RESET_USER=Nom utilisateur admin [admin]:
if "%RESET_USER%"=="" set "RESET_USER=admin"
set /p RESET_PASS=Mot de passe de secours [0000]:
if "%RESET_PASS%"=="" set "RESET_PASS=0000"

echo.
"%PYTHON_EXE%" reset_admin_password.py "%RESET_PASS%" "%RESET_USER%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Reset admin termine.
) else (
  echo Echec du reset admin.
)
pause
exit /b %EXIT_CODE%
