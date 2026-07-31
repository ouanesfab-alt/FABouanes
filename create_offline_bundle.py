"""Générateur de Pack d'Installation Offline FABouanes pour Android."""
import os
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "fabouanes_offline_bundle"
ZIP_FILE = BASE_DIR / "fabouanes_offline.zip"

def build_offline_pack():
    print("[+] Creation du pack autonome Offline FABouanes...", flush=True)
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copie du code source principal
    print("[1] Copie des fichiers source...", flush=True)
    shutil.copytree(BASE_DIR / "app", OUTPUT_DIR / "app", dirs_exist_ok=True)
    shutil.copytree(BASE_DIR / "alembic", OUTPUT_DIR / "alembic", dirs_exist_ok=True)
    shutil.copytree(BASE_DIR / "static", OUTPUT_DIR / "static", dirs_exist_ok=True)
    shutil.copy(BASE_DIR / "alembic.ini", OUTPUT_DIR / "alembic.ini")
    shutil.copy(BASE_DIR / "launcher.py", OUTPUT_DIR / "launcher.py")
    shutil.copy(BASE_DIR / "requirements-termux.txt", OUTPUT_DIR / "requirements-termux.txt")
    shutil.copy(BASE_DIR / "setup_termux.sh", OUTPUT_DIR / "setup_termux.sh")
    if (BASE_DIR / "wheels").exists():
        print("[1b] Copie des 81 wheels précompilées...", flush=True)
        shutil.copytree(BASE_DIR / "wheels", OUTPUT_DIR / "wheels", dirs_exist_ok=True)

    # 2. Script d'installation autonome hors-ligne
    install_script = """#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=================================================="
echo "🚀 INSTALLATION 100% HORS-LIGNE DE FABOUANES"
echo "=================================================="

# Décompression & installation des dépendances
termux-setup-storage || true
echo "📦 Installation des dépendances système..."
pkg install python postgresql make clang rust binutils libffi libjpeg-turbo libpng zlib freetype python-cryptography -y || true

# Setup virtual environment
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate

# Installation des roues Python
if [ -d "wheels" ]; then
    pip install --no-index --find-links=wheels -r requirements-termux.txt || true
fi

# Config PostgreSQL & base
export DATABASE_URL="postgresql://$(whoami)@127.0.0.1:5432/fabouanes"
echo "DATABASE_URL=$DATABASE_URL" > .env
echo "DEFAULT_ADMIN_USERNAME=admin" >> .env
echo "DEFAULT_ADMIN_PASSWORD=7508" >> .env
echo "FAB_HTTPS=1" >> .env

python -c "from app.core.database import bootstrap_and_migrate; bootstrap_and_migrate()"

cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock || true
rm -f $PREFIX/var/lib/postgresql/postmaster.pid
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start
cd ~/FABouanes
source venv/bin/activate
python launcher.py --server
EOF
chmod +x ~/start_fab.sh

echo "=================================================="
echo "🎉 INSTALLATION COMPLÈTE EN MODE HORS-LIGNE !"
echo "Compte administrateur initial :"
echo "  Utilisateur : admin"
echo "  Code PIN    : 7508"
echo "Pour lancer le serveur: ~/start_fab.sh ou 'fab'"
echo "=================================================="
"""
    (OUTPUT_DIR / "install_offline.sh").write_text(install_script, encoding="utf-8")

    # 3. Compression de l'archive ZIP finale
    print("[3] Compression du fichier fabouanes_offline.zip...", flush=True)
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()
        
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zip_handle:
        for root, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(OUTPUT_DIR)
                zip_handle.write(file_path, arcname)

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    print(f"[OK] Pack Offline cree avec succes: {ZIP_FILE} ({ZIP_FILE.stat().st_size / (1024*1024):.2f} MB)", flush=True)

if __name__ == "__main__":
    build_offline_pack()
