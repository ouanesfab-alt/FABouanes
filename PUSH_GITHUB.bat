@echo off
REM ==========================================
REM  FABOuanes - Push vers GitHub
REM ==========================================

REM Verifier que Git est installe
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Git n'est pas installe!
    pause
    exit /b 1
)

cls
echo.
echo ========================================
echo   FABOuanes - Synchronisation GitHub
echo ========================================
echo.

REM Ajouter tous les fichiers
git add .

REM Afficher le statut
git status

echo.
echo Entrez le message de commit (ou laissez vide pour annuler):
set /p "message="

if "%message%"=="" (
    echo Annulation.
    pause
    exit /b 0
)

REM Committer
git commit -m "%message%"

REM Pusher
git push

echo.
echo ✅ Synchronisation completee!
pause
