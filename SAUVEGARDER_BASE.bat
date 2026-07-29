@echo off
title FABOuanes - Sauvegarde de la Base de Donnees
cd /d "%~dp0"
echo.
echo ===========================================================
echo     FABOUANES ERP - SAUVEGARDE DE LA BASE DE DONNEES
echo ===========================================================
echo.

set PY_CMD=python
py -3 --version >nul 2>&1
if not errorlevel 1 set PY_CMD=py -3

%PY_CMD% -c "
import os, subprocess, shutil
from datetime import datetime
from pathlib import Path
from app.core.config import settings
from urllib.parse import urlparse

db_url = settings.database_url
parsed = urlparse(db_url)
user = parsed.username or 'postgres'
host = parsed.hostname or '127.0.0.1'
port = parsed.port or 5432
dbname = (parsed.path or '/fabouanes').lstrip('/')

backup_dir = settings.base_dir / 'backups'
backup_dir.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
out_file = backup_dir / f'fabouanes_backup_{timestamp}.sql'

pg_dump = shutil.which('pg_dump')
if not pg_dump:
    for ver in range(20, 10, -1):
        candidate = f'C:\\Program Files\\PostgreSQL\\{ver}\\bin\\pg_dump.exe'
        if Path(candidate).exists():
            pg_dump = candidate
            break

if not pg_dump or not Path(pg_dump).exists():
    pg_dump = 'pg_dump'

env = dict(os.environ)
if parsed.password:
    env['PGPASSWORD'] = parsed.password

cmd = [str(pg_dump), '-h', host, '-p', str(port), '-U', user, '-F', 'p', '-f', str(out_file), dbname]
try:
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode == 0:
        print(f'  [OK] Sauvegarde creee avec succes :')
        print(f'       {out_file}')
    else:
        print('  [ERR] Erreur sauvegarde :', res.stderr.strip())
except Exception as e:
    print('  [ERR] Erreur execution pg_dump :', e)
"

echo.
pause
