@echo off
REM ==========================================
REM  FABOuanes - Lancer les tests
REM ==========================================

REM Activer l'environnement virtuel
call .venv\Scripts\activate.bat

cls
echo.
echo ========================================
echo   Execution des tests...
echo ========================================
echo.

REM Executer les tests (PostgreSQL requis pour les tests d'integration)
python -m unittest discover -s tests -v

pause
