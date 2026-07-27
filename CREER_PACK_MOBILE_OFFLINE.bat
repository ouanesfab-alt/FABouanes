@echo off
title FABOuanes - Creation du Pack 100%% Automatise
cd /d "%~dp0"

echo ===========================================================
echo  FABOuanes - Automatisation Complete du Pack Mobile
echo ===========================================================
echo.
echo 1. Telechargement automatique des wheels Python (Hors-Ligne)...
if not exist "wheels" mkdir wheels
pip download --prefer-binary -r requirements.txt -d wheels/

echo.
echo 2. Generation du script d'installation directe...
echo #!/data/data/com.termux/files/usr/bin/bash > installer.sh
echo cd "$(dirname "$0")" >> installer.sh
echo bash setup_termux.sh >> installer.sh
chmod +x installer.sh 2>nul

echo.
echo ===========================================================
echo  SUCCES : Pack Mobile 100%% Automatise Pret !
echo ===========================================================
echo  Il vous suffit de copier ce dossier sur votre telephone.
echo  Dans Termux, lancez simplement :
echo    bash setup_termux.sh
echo ===========================================================
pause
