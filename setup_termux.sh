#!/data/data/com.termux/files/usr/bin/bash

# ===================================================
# Script Unifié & Sécurisé d'Installation Termux
# FABOuanes — Mode Auto Turbo (En-Ligne / Hors-Ligne)
# ===================================================

set -e

echo "🚀 Démarrage de l'installation ultra-rapide de FABOuanes sur Termux..."

# 1. Export des variables critiques Android (Évite les compilations Rust et crashs pydantic-core)
export ANDROID_API_LEVEL=24
export CFLAGS="-Wno-implicit-function-declaration $CFLAGS"

# 2. Paquets système (Tolérance réseau pour mode 100% Hors-Ligne)
echo "🔄 1. Vérification des dépôts et paquets Termux..."
pkg update -y 2>/dev/null || true

echo "📦 2. Installation des paquets système de base..."
pkg install git python postgresql make clang rust libffi openssl libjpeg-turbo -y 2>/dev/null || true

# Paquets pré-compilés Optionnels Termux
pkg install python-cryptography python-pillow python-numpy python-pandas -y 2>/dev/null || true

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

# 5. Installation des dépendances Python (Détection Hors-Ligne / En-Ligne rapide)
echo "🐍 5. Installation des paquets Python (Mode Turbo --prefer-binary)..."
pip install --prefer-binary --upgrade pip setuptools wheel 2>/dev/null || true

if [ -d "./wheels" ] && [ "$(ls -A ./wheels 2>/dev/null)" ]; then
    echo "📦 Mode Hors-Ligne (100% Roues .whl Pré-compilées) : Installation instantanée..."
    pip install --no-index --find-links=./wheels -r requirements.txt
else
    echo "🌐 Mode En-Ligne : Installation rapide PyPI..."
    pip install --prefer-binary -r requirements.txt
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

# Extrait du PIN pour l'affichage final
ADMIN_PIN=$(grep "DEFAULT_ADMIN_PASSWORD" .env 2>/dev/null | cut -d'=' -f2 || echo "7508")

echo "==================================================="
echo "🎉 INSTALLATION AUTOMATISEE TERMINEE AVEC SUCCES !"
echo "==================================================="
echo " Connexion Administrateur :"
echo "   Utilisateur : admin"
echo "   Code PIN    : ${ADMIN_PIN}"
echo "---------------------------------------------------"
echo " Accès depuis votre navigateur mobile :"
echo "   http://localhost:5000"
echo "==================================================="
echo ""
echo "🚀 Démarrage automatique du serveur FABOuanes..."
sleep 2

# Démarrage automatique du serveur
python launcher.py --server-only
