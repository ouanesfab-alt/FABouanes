@echo off
SETLOCAL EnableDelayedExpansion

echo ============================================================
echo   FABouanes - Script de deploiement de production (Docker)
echo ============================================================
echo.

:: 1. Verifier le fichier .env
if not exist ".env" (
    echo [ATTENTION] Aucun fichier .env trouve dans le repertoire de deploiement.
    echo Creation d'un fichier .env a partir de env.prod.example...
    copy env.prod.example .env
    echo [IMPORTANT] Veuillez editer le fichier .env et renseigner les mots de passe avant de continuer.
    pause
    exit /b 1
)

:: 2. Construire l'image Docker
echo.
echo [1/4] Construction des images Docker...
docker compose -f docker-compose.prod.yml build
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] La construction de l'image a echoue.
    pause
    exit /b %ERRORLEVEL%
)

:: 3. Demarrer la base de donnees et attendre la sante
echo.
echo [2/4] Demarrage de la base de donnees PostgreSQL...
docker compose -f docker-compose.prod.yml up -d db
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] Impossible de demarrer le conteneur de base de donnees.
    pause
    exit /b %ERRORLEVEL%
)

echo Attente de l'initialisation de la base de donnees...
:check_db
docker compose -f docker-compose.prod.yml exec -T db pg_isready -U fabouanes -d fabouanes >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 2 /nobreak >nul
    goto check_db
)
echo Base de donnees prete et connectee !

:: 4. Lancer les migrations Alembic
echo.
echo [3/4] Execution des migrations de base de donnees...
docker compose -f docker-compose.prod.yml run --rm web alembic upgrade head
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] L'execution des migrations Alembic a echoue.
    pause
    exit /b %ERRORLEVEL%
)

:: 5. Demarrer toute la stack
echo.
echo [4/4] Lancement final de l'application et de Prometheus...
docker compose -f docker-compose.prod.yml up -d
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] Le demarrage des services a echoue.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo   Deploiement effectue avec succes !
echo ============================================================
echo   - Application accessible sur : http://localhost:8000
echo   - Supervision Prometheus sur : http://localhost:9090
echo ============================================================
pause
