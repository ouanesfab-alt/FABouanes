@echo off
setlocal EnableExtensions
title FABOuanes - Installateur Windows
cd /d "%~dp0"
color 0A

echo.
echo  ===========================================================
echo         FABOUANES ERP - CREATION INSTALLATEUR WINDOWS
echo  ===========================================================
echo.

set "PY_CMD=python"
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

REM 1. Autocreation du raccourci Bureau Windows
echo  [1/2] Creation du raccourci officiel sur le Bureau Windows...
powershell -Command "`$w = New-Object -ComObject WScript.Shell; `$s = `$w.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'FABOuanes.lnk')); `$s.TargetPath = '%~dp0LANCER.bat'; `$s.WorkingDirectory = '%~dp0'; `$s.IconLocation = '%~dp0static\FABOuanes_desktop.ico'; `$s.Save()"
if not errorlevel 1 (
    echo        [OK] Raccourci 'FABOuanes' cree sur votre Bureau.
) else (
    echo        [WARN] Impossible de creer le raccourci Bureau.
)

echo.
echo  [2/2] Compilation du package executable / installateur...
set "FAB_NO_PAUSE=1"
call "%~dp0installer\windows\BUILD_INSTALLATEUR_DESKTOP.bat"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo  ===========================================================
    echo    SUCCES COMPLET : Package et Raccourci Windows crees !
    echo  ===========================================================
) else (
    echo  ===========================================================
    echo    [INFO] Raccourci Bureau actif. (Pour fabriquer le .exe
    echo           standalone, installez Inno Setup 6).
    echo  ===========================================================
)

echo.
pause
endlocal
