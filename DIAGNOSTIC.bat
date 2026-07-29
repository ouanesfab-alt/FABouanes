@echo off
title FABOuanes - Diagnostic Systeme
cd /d "%~dp0"
echo.
echo  ===========================================================
echo         FABOUANES ERP - DIAGNOSTIC SYSTEME ET SANTE
echo  ===========================================================
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

%PY_CMD% -c "
import sys, os, socket
from pathlib import Path

print(' 1. Version Python      :', sys.version.split()[0])

# Verification SSL
cert = Path('cert.pem').exists()
key = Path('key.pem').exists()
print(' 2. Certificat SSL      :', 'ACTIF (HTTPS)' if (cert and key) else 'NON GENERE (HTTP)')

# Verification .env
env_file = Path('.env').exists()
print(' 3. Fichier .env         :', 'PRESENT' if env_file else 'ABSENT')

# Verification PostgreSQL
try:
    from app.core.config import settings
    from app.core.db_helpers.manager import db_manager
    conn = db_manager.connect_database(settings.database_url)
    conn.close()
    print(' 4. Base PostgreSQL     : CONNECTEE AVEC SUCCES (fabouanes)')
except Exception as e:
    print(' 4. Base PostgreSQL     : ERREUR (', e, ')')

# Verification Port 5000
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    res = s.connect_ex(('127.0.0.1', 5000))
    print(' 5. Statut Port 5000    :', 'DISPONIBLE' if res != 0 else 'EN COURS D\'UTILISATION (SERVEUR ACTIF)')

print('===========================================================')
"

echo.
pause
