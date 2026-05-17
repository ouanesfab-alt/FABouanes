@echo off
setlocal EnableExtensions
title FABOuanes - Push GitHub

cd /d "%~dp0"
color 0A

where git >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Git est introuvable dans le PATH.
    pause
    exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo ERREUR: ce dossier n'est pas un depot Git.
    pause
    exit /b 1
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH (
    echo ERREUR: impossible de detecter la branche courante.
    pause
    exit /b 1
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo ERREUR: aucun remote GitHub "origin" n'est configure.
    pause
    exit /b 1
)

echo.
echo  Branche courante: %BRANCH%
echo.
echo  Changements detectes:
git status --short
echo.

set /p COMMIT_MSG=Message du commit: 
if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Update FABOuanes"

echo.
echo  Ajout des fichiers...
git add -A
if errorlevel 1 (
    echo ERREUR: git add a echoue.
    pause
    exit /b 1
)

git diff --cached --quiet
if errorlevel 1 (
    echo.
    echo  Creation du commit...
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 (
        echo ERREUR: git commit a echoue.
        pause
        exit /b 1
    )
) else (
    echo.
    echo  Aucun changement a committer.
)

echo.
echo  Synchronisation avec origin/%BRANCH%...
git pull --rebase origin "%BRANCH%"
if errorlevel 1 (
    echo.
    echo  ERREUR: git pull --rebase a echoue. Resous les conflits puis relance le script.
    pause
    exit /b 1
)

echo.
echo  Push vers GitHub...
git push -u origin "%BRANCH%"
if errorlevel 1 (
    echo.
    echo  ERREUR: git push a echoue.
    pause
    exit /b 1
)

echo.
echo  SUCCES: branche %BRANCH% poussee sur GitHub.
pause
endlocal
