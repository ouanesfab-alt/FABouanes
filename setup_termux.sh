#!/data/data/com.termux/files/usr/bin/bash

# ===================================================
# Script Unifié & Sécurisé d'Installation Termux
# FABOuanes — Mode Auto (En-Ligne / Hors-Ligne)
# ===================================================

set -e

echo "🚀 Démarrage de l'installation de FABOuanes sur Termux..."

# 1. Export des variables critiques Android (Évite le crash pydantic-core / maturin)
export ANDROID_API_LEVEL=24
export CFLAGS="-Wno-implicit-function-declaration $CFLAGS"

# 2. Mise à jour et paquets système
echo "🔄 1. Mise à jour des dépôts Termux..."
pkg update && pkg upgrade -y

echo "📦 2. Installation des dépendances système & compilation..."
pkg install git python postgresql make clang rust libffi openssl libjpeg-turbo -y

# 3. Initialisation & Démarrage de PostgreSQL
echo "🗄️ 3. Configuration de PostgreSQL..."
if [ ! -d "$PREFIX/var/lib/postgresql" ]; then
    initdb -D $PREFIX/var/lib/postgresql
fi

# Démarrage de PostgreSQL
pg_ctl -D $PREFIX/var/lib/postgresql start || true
sleep 2

# Création de la base de données
createdb fabouanes 2>/dev/null || echo "Info: La base 'fabouanes' existe déjà."

# 4. Positionnement dans le dossier du projet
TARGET_DIR="$HOME/FABouanes"
if [ "$PWD" != "$TARGET_DIR" ]; then
    if [ -d "$TARGET_DIR" ]; then
        echo "📂 Répertoire $TARGET_DIR déjà existant."
        cd "$TARGET_DIR"
    elif [ -f "./launcher.py" ]; then
        echo "📂 Exécution depuis le dossier courant de FABOuanes."
    else
        echo "📥 Clonage du projet depuis GitHub..."
        git clone https://github.com/ouanesfab-alt/FABouanes.git "$TARGET_DIR"
        cd "$TARGET_DIR"
    fi
fi

# 5. Installation des dépendances Python (Détection Hors-Ligne / En-Ligne)
echo "🐍 5. Installation des paquets Python..."
pip install --upgrade pip setuptools wheel 2>/dev/null || true

if [ -d "./wheels" ] && [ "$(ls -A ./wheels 2>/dev/null)" ]; then
    echo "📦 Mode Hors-Ligne détecté : Installation depuis le dossier ./wheels..."
    pip install --no-index --find-links=./wheels -r requirements.txt
else
    echo "🌐 Mode En-Ligne : Installation depuis PyPI avec ANDROID_API_LEVEL=24..."
    pip install -r requirements.txt
fi

# 6. Génération sécurisée et complète du fichier .env
echo "🔒 6. Configuration de l'environnement (.env)..."
if [ ! -f ".env" ]; then
    PIN_CODE=$(python -c "import secrets; print(f'{secrets.randbelow(10000):04d}')")
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    CURRENT_USER=$(whoami)
    
    cat << EOF > .env
FASTAPI_ENV=production
DATABASE_URL=postgresql://${CURRENT_USER}@localhost:5432/fabouanes
SECRET_KEY=${SECRET_KEY}
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=${PIN_CODE}
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
FAB_PASSWORD_MODE=pin
EOF
    echo "✅ Fichier .env créé. Code PIN Administrateur généré : ${PIN_CODE}"
else
    echo "ℹ️ Fichier .env existant conservé."
fi

# 7. Initialisation de la base de données
echo "⚙️ 7. Initialisation des schémas de la base de données..."
python launcher.py --bootstrap-only

# 8. Création du script de lancement rapide ~/start_fab.sh
echo "⚡ 8. Création du lanceur rapide ~/start_fab.sh..."
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
export ANDROID_API_LEVEL=24
echo "⚡ Démarrage de PostgreSQL..."
pg_ctl -D $PREFIX/var/lib/postgresql start 2>/dev/null || true
sleep 1

echo "🚀 Lancement du serveur FABOuanes..."
if [ -d "$HOME/FABouanes" ]; then
    cd "$HOME/FABouanes"
fi
python launcher.py --server-only
EOF

chmod +x ~/start_fab.sh

echo "==================================================="
echo "🎉 INSTALLATION TERMINEE AVEC SUCCES !"
echo "==================================================="
echo "Pour démarrer FABOuanes sur votre téléphone à l'avenir :"
echo "  ~/start_fab.sh"
echo ""
echo "Accès depuis votre navigateur mobile :"
echo "  http://localhost:5000"
echo "==================================================="
