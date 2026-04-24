@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Coverage tests
set "PYTHON_EXE=.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
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
"%PYTHON_EXE%" -m coverage run -m unittest discover -s tests -v
if errorlevel 1 (
  echo.
  echo Echec tests/coverage.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -m coverage report
"%PYTHON_EXE%" -m coverage xml
echo.
echo Coverage XML genere: coverage.xml
pause
exit /b 0
