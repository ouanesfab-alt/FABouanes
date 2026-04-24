@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Double clic

set "FAB_HOST=0.0.0.0"
set "FAB_PORT=5000"
set "HOST=%FAB_HOST%"
set "PORT=%FAB_PORT%"
set "PYTHON_EXE=.venv\Scripts\python.exe"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_WARN_SCRIPT_LOCATION=0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Creation de l'environnement Python (.venv)...
  py -3 -m venv .venv >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv >nul 2>nul
  )
)

cls
echo.
echo ========================================
echo   FABOuanes - Lancement automatique reseau
echo ========================================
echo.

if not exist "%PYTHON_EXE%" (
  echo ERREUR: impossible de preparer Python dans .venv.
  echo Verifie l'installation de Python 3 puis relance ce script.
  echo.
  pause
  exit /b 1
)

echo [2/5] Installation / verification des dependances Python...
"%PYTHON_EXE%" -m pip install --upgrade pip >nul
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERREUR: installation des dependances impossible.
  echo Verifie ta connexion internet puis relance le script.
  echo.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo.
    echo [3/5] Fichier .env cree depuis .env.example.
    echo ACTION REQUISE: configure DATABASE_URL dans .env avant de continuer.
    echo Exemple: postgresql://postgres:motdepasse@localhost:5432/fabouanes
    echo.
    pause
    exit /b 1
  ) else (
    echo.
    echo ERREUR: .env et .env.example introuvables.
    echo.
    pause
    exit /b 1
  )
)

findstr /B /C:"DATABASE_URL=" ".env" >nul
if errorlevel 1 (
  echo.
  echo ERREUR: DATABASE_URL absent dans .env.
  echo Ajoute DATABASE_URL puis relance.
  echo.
  pause
  exit /b 1
)

echo [4/5] Verification configuration reseau...
echo HOST: %FAB_HOST%
echo PORT: %FAB_PORT%
echo.

echo [5/5] Demarrage application...
echo URL locale: http://127.0.0.1:%FAB_PORT%
echo Mode reseau: actif (%FAB_HOST%)
echo.
start "" "http://127.0.0.1:%FAB_PORT%"
echo Appuie sur Ctrl+C pour arreter.
echo ========================================
echo.

"%PYTHON_EXE%" run_prod.py

set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Application arretee.
) else (
  echo Application arretee avec erreur (code %EXIT_CODE%).
  echo Consulte les logs console ci-dessus.
  pause
)
exit /b %EXIT_CODE%
