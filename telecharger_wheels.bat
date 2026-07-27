@echo off
title FABOuanes - Telechargement des paquets Hors-Ligne (Wheels)
cd /d "%~dp0"

echo ===========================================================
echo  FABOuanes - Preparation du Mode 100%% Hors-Ligne (Termux)
echo ===========================================================
echo.
echo Telechargement des wheels Python pour installation sans internet...
echo.

if not exist "wheels" mkdir wheels

pip download --prefer-binary -r requirements.txt -d wheels/

echo.
echo ===========================================================
echo  SUCCES : Le dossier ./wheels est pret !
echo ===========================================================
echo Vous pouvez copier le dossier complet FABOuanes sur votre
echo telephone et lancer setup_termux.sh 100%% HORS-LIGNE.
echo ===========================================================
pause
