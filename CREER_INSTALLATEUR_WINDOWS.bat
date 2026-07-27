@echo off
setlocal EnableExtensions
title FABOuanes - Creer installateur Windows

cd /d "%~dp0"
set "FAB_NO_PAUSE=1"
call "%~dp0installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ERREUR: creation de l'installateur echouee.
    if not "%FAB_NO_PAUSE%"=="1" pause
    exit /b %EXIT_CODE%
)

echo.
echo Installateur cree: installer_output\FABOuanes_Setup.exe
if not "%FAB_NO_PAUSE%"=="1" pause
endlocal
