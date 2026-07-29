@echo off
setlocal enabledelayedexpansion
title FABOuanes (Mode HTTPS)
cd /d %~dp0
echo.
echo  Demarrage de FABOuanes en Mode Securise (HTTPS)...
echo.
set FAB_HTTPS=1
call LANCER.bat
