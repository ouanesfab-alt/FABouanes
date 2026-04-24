@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Stop PostgreSQL Docker
set "COMPOSE_FILE=deploy\docker\docker-compose.yml"

echo.
echo ========================================
echo   FABOuanes - Stop PostgreSQL (Docker)
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

%DOCKER_COMPOSE_CMD% -f "%COMPOSE_FILE%" stop postgres redis
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo ERREUR: arret des services impossible.
  pause
  exit /b %EXIT_CODE%
)

echo Services arretes.
echo.
pause
exit /b 0
