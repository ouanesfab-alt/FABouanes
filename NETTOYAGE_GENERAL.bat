@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Nettoyage general

echo.
echo ========================================
echo   FABOuanes - Nettoyage general
echo ========================================
echo.

if exist "server_stdout.log" del /f /q "server_stdout.log" >nul 2>nul
if exist "server_stderr.log" del /f /q "server_stderr.log" >nul 2>nul

if exist "__pycache__" rd /s /q "__pycache__" >nul 2>nul
if exist ".pytest_cache" rd /s /q ".pytest_cache" >nul 2>nul
if exist "tests\_runtime" rd /s /q "tests\_runtime" >nul 2>nul
if exist "tests\_runtime_debug" rd /s /q "tests\_runtime_debug" >nul 2>nul

for /f "delims=" %%d in ('dir /s /b /ad "__pycache__" 2^>nul') do rd /s /q "%%d" >nul 2>nul

echo Nettoyage termine.
echo.
pause
