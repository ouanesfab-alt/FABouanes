@echo off
setlocal enabledelayedexpansion
REM Script pour initialiser et pousser le projet sur GitHub
REM À exécuter APRÈS avoir installé Git

echo.
echo ========================================
echo  FABOuanes - Push vers GitHub
echo ========================================
echo.

REM Vérifier que git est installé
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERREUR: Git n'est pas installé!
    echo.
    echo Téléchargez et installez Git depuis: https://git-scm.com/download/win
    echo Puis relancez ce script.
    echo.
    pause
    exit /b 1
)

REM URL du dépôt
set REPO_URL=https://github.com/ouanesfab-alt/FABouanes.git
set USERNAME=ouanesfab-alt

echo Git trouvé! Version:
git --version
echo.

REM Vérifier si .git existe déjà
if exist ".git" (
    echo Le dépôt local existe déjà.
    echo.
    set /p CONTINUE="Voulez-vous pousser les changements existants? (o/n): "
    if /i "!CONTINUE!"=="n" exit /b 0
    echo.
    echo ========================================
    echo  AUTHENTIFICATION REQUISE
    echo ========================================
    echo.
    echo Username: %USERNAME%
    echo.
    echo Pour le PASSWORD/Token:
    echo - Générez un token sur: https://github.com/settings/tokens
    echo - Utilisez "Generate new token (classic)"
    echo - Scope: repo (complet)
    echo - Collez le token quand demandé (ne pas coller votre mot de passe)
    echo.
    echo ========================================
    echo.
    
    echo Push en cours...
    git push -u origin main
    if %errorlevel% equ 0 (
        echo.
        echo ========================================
        echo  Push terminé avec succès!
        echo ========================================
        echo Dépôt: %REPO_URL%
    ) else (
        echo.
        echo ERREUR lors du push!
        echo Vérifiez:
        echo - Votre token GitHub (scope repo)
        echo - La connexion Internet
        echo - L'URL du dépôt
    )
    echo.
    pause
    exit /b 0
)

echo Initialisation du dépôt local...
git init

echo.
echo Configuration initiale...
git config user.name "Ouanes FAB"
git config user.email "dev@fabouanes.local"

echo.
echo Ajout de tous les fichiers...
git add .

echo.
echo Création du commit initial...
git commit -m "Initial commit: FABOuanes - Inventory Management System"

echo.
echo Ajout de la télécommande GitHub...
git remote add origin "%REPO_URL%"

echo.
echo ========================================
echo  AUTHENTIFICATION REQUISE
echo ========================================
echo.
echo Username: %USERNAME%
echo.
echo Pour le PASSWORD/Token:
echo - Générez un token sur: https://github.com/settings/tokens
echo - Utilisez "Generate new token (classic)"
echo - Scope: repo (complet)
echo - Collez le token quand demandé (ne pas coller votre mot de passe)
echo.
echo ========================================
echo.

git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  Push terminé avec succès!
    echo ========================================
    echo.
    echo Visualisez votre dépôt: %REPO_URL%
) else (
    echo.
    echo ERREUR lors du push!
    echo Vérifiez:
    echo - Votre connexion Internet
    echo - L'URL du dépôt GitHub
    echo - Votre authentification (username/token)
)

echo.
pause
