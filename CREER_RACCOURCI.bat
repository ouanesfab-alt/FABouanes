@echo off
setlocal EnableExtensions
title FABOuanes - Creation du raccourci Bureau
cd /d "%~dp0"
color 0A

echo.
echo  ======================================================
echo    Creation du raccourci FABOuanes sur votre Bureau
echo  ======================================================
echo.

powershell -Command "`$w = New-Object -ComObject WScript.Shell; `$s = `$w.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'FABOuanes.lnk')); `$s.TargetPath = '%~dp0LANCER.bat'; `$s.WorkingDirectory = '%~dp0'; `$s.IconLocation = '%~dp0static\FABOuanes_desktop.ico'; `$s.Save()"

if not errorlevel 1 (
    echo  [OK] Raccourci 'FABOuanes' cree sur le Bureau avec succes !
) else (
    echo  [ERR] Impossible de creer le raccourci.
)

echo.
pause
endlocal
