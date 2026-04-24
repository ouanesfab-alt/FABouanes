@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Seed demo optionnel
set "PYTHON_EXE=.venv\Scripts\python.exe"

echo.
echo ========================================
echo   FABOuanes - Seed demo (optionnel)
echo ========================================
echo.
echo Ce script n'ecrase pas les donnees existantes.
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

"%PYTHON_EXE%" -m pip install -r requirements.txt >nul
"%PYTHON_EXE%" seed_demo.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
