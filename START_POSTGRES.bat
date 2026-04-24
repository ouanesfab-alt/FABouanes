@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Start PostgreSQL Docker
set "COMPOSE_FILE=deploy\docker\docker-compose.yml"

echo.
echo ========================================
echo   FABOuanes - Start PostgreSQL (Docker)
echo ========================================
echo.

if not exist "%COMPOSE_FILE%" (
  echo ERREUR: fichier %COMPOSE_FILE% introuvable.
  pause
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  set "DOCKER_COMPOSE_CMD=docker-compose"
) else (
  set "DOCKER_COMPOSE_CMD=docker compose"
)

%DOCKER_COMPOSE_CMD% -f "%COMPOSE_FILE%" up -d postgres redis
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo ERREUR: impossible de demarrer PostgreSQL/Redis.
  pause
  exit /b %EXIT_CODE%
)

echo Services demarres:
%DOCKER_COMPOSE_CMD% -f "%COMPOSE_FILE%" ps
echo.
echo DATABASE_URL exemple:
echo postgresql://fabouanes:fabouanes_change_me@localhost:5432/fabouanes
echo.
pause
exit /b 0
