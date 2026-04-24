@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Double clic

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "FAB_HOST=0.0.0.0"
set "FAB_PORT=5000"
set "HOST=%FAB_HOST%"
set "PORT=%FAB_PORT%"

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
  )
)

cls
echo.
echo ========================================
echo   FABOuanes - Lancement automatique
echo ========================================
echo.
echo Etape 1/2 - Reinitialisation admin...
"%PYTHON_EXE%" reset_admin_password.py 0000 admin
if errorlevel 1 (
  echo ATTENTION: reset admin non confirme.
  echo Verifie DATABASE_URL dans .env
  echo.
) else (
  echo OK: identifiants de secours
  echo    Utilisateur: admin
  echo    Mot de passe: 0000
  echo.
)

echo Etape 2/2 - Demarrage application...
echo URL locale: http://127.0.0.1:%FAB_PORT%
echo Mode reseau: actif (%FAB_HOST%)
start "" "http://127.0.0.1:5000"
echo.
echo Appuie sur Ctrl+C pour arreter.
echo ========================================
echo.

"%PYTHON_EXE%" run_prod.py

echo.
echo Application arretee.
pause
