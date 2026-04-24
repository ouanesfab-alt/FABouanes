@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Qualite code
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

"%PYTHON_EXE%" -m ruff check fabouanes/fastapi_compat.py fabouanes/presentation/api_validation.py fabouanes/routes/route_utils.py
if errorlevel 1 (
  echo Echec ruff.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -m black --check fabouanes/fastapi_compat.py fabouanes/presentation/api_validation.py fabouanes/routes/route_utils.py app.py run_prod.py
if errorlevel 1 (
  echo Echec black.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -m mypy
if errorlevel 1 (
  echo Echec mypy.
  pause
  exit /b 1
)

echo.
echo Qualite code OK.
pause
exit /b 0
