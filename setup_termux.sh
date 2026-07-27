#!/data/data/com.termux/files/usr/bin/bash

# ===================================================
# Script Unifié & VIP d'Installation Termux
# FABOuanes — Mode Auto Turbo (En-Ligne / Hors-Ligne)
# ===================================================

set -e

# Piège gracieux pour Ctrl+C (KeyboardInterrupt)
trap 'echo -e "\n\n👋 Serveur arrêté avec succès (Ctrl+C). À bientôt !"; exit 0' SIGINT SIGTERM

echo "==================================================="
echo "   🚀  FABOuanes — Installation Mobile Termux"
echo "==================================================="

# 1. Export des variables critiques Android
export ANDROID_API_LEVEL=24
export CFLAGS="-Wno-implicit-function-declaration $CFLAGS"

# 2. Paquets système (Tolérance réseau pour mode 100% Hors-Ligne)
echo "🔄 1. Vérification des dépôts et paquets Termux..."
pkg update -y 2>/dev/null || true

echo "📦 2. Installation des paquets système de base..."
pkg install git python postgresql make clang rust libffi openssl libjpeg-turbo termux-api -y 2>/dev/null || true

# Paquets pré-compilés Optionnels Termux
pkg install python-cryptography python-pillow python-numpy python-pandas -y 2>/dev/null || true

# 3. Initialisation & Démarrage de PostgreSQL
echo "🗄️ 3. Configuration de PostgreSQL..."
PG_DATA="$PREFIX/var/lib/postgresql"
if [ ! -d "$PG_DATA" ]; then
    initdb -D "$PG_DATA"
fi

# Nettoyage si arrêt brutal antérieur (Ctrl+C)
if [ -f "$PG_DATA/postmaster.pid" ]; then
    pg_ctl -D "$PG_DATA" status >/dev/null 2>&1 || rm -f "$PG_DATA/postmaster.pid"
fi

# Démarrage de PostgreSQL
pg_ctl -D "$PG_DATA" start >/dev/null 2>&1 || true
sleep 1

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

# 8. Création du lanceur rapide VIP ~/start_fab.sh
echo "⚡ 8. Création du lanceur rapide VIP (commande 'fab')..."
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
export ANDROID_API_LEVEL=24

# Piège gracieux pour Ctrl+C
trap 'echo -e "\n\n👋 Serveur arrêté proprement. À bientôt !"; exit 0' SIGINT SIGTERM

# Maintien de l'écran éveillé en arrière-plan
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock 2>/dev/null || true
fi

PG_DATA="$PREFIX/var/lib/postgresql"

case "$1" in
    stop)
        echo "🛑 Arrêt du serveur et de PostgreSQL..."
        pg_ctl -D "$PG_DATA" stop 2>/dev/null || true
        pkill -f "launcher.py" 2>/dev/null || true
        echo "✅ Serveur et base de données arrêtés."
        exit 0
        ;;
    status)
        echo "📊 Statut des services FABOuanes :"
        if pg_ctl -D "$PG_DATA" status >/dev/null 2>&1; then
            echo "  - PostgreSQL : 🟢 En ligne"
        else
            echo "  - PostgreSQL : 🔴 Arrêté"
        fi
        exit 0
        ;;
    pin)
        if [ -d "$HOME/FABouanes" ] && [ -f "$HOME/FABouanes/.env" ]; then
            PIN=$(grep "DEFAULT_ADMIN_PASSWORD" "$HOME/FABouanes/.env" | cut -d'=' -f2)
            echo "🔑 Code PIN Admin actuel : ${PIN}"
        fi
        exit 0
        ;;
esac

echo "⚡ Démarrage de PostgreSQL..."
if [ -f "$PG_DATA/postmaster.pid" ]; then
    pg_ctl -D "$PG_DATA" status >/dev/null 2>&1 || rm -f "$PG_DATA/postmaster.pid"
fi
pg_ctl -D "$PG_DATA" start >/dev/null 2>&1 || true
sleep 1

if [ -d "$HOME/FABouanes" ]; then
    cd "$HOME/FABouanes"
fi

ADMIN_PIN=$(grep "DEFAULT_ADMIN_PASSWORD" .env 2>/dev/null | cut -d'=' -f2 || echo "7508")

echo ""
echo "===================================================="
echo " 📱 FABOUANES MOBILE SERVER — EN LIGNE 🟢"
echo "===================================================="
echo " 👤 Identifiant Admin : admin"
echo " 🔑 Code PIN Admin   : ${ADMIN_PIN}"
echo "----------------------------------------------------"
echo " 🌐 Accès Mobile Local : http://localhost:5000"
echo " 💡 Astuce : Tapez 'fab stop' pour tout arrêter."
echo "===================================================="
echo ""

# Lancement du serveur FastAPI
python launcher.py --server-only
EOF

chmod +x ~/start_fab.sh

# 9. Ajout de l'alias 'fab' dans ~/.bashrc
BASHRC="$HOME/.bashrc"
if ! grep -q "alias fab=" "$BASHRC" 2>/dev/null; then
    echo "alias fab='~/start_fab.sh'" >> "$BASHRC"
    echo "alias fab-stop='~/start_fab.sh stop'" >> "$BASHRC"
    echo "alias fab-status='~/start_fab.sh status'" >> "$BASHRC"
fi

ADMIN_PIN=$(grep "DEFAULT_ADMIN_PASSWORD" .env 2>/dev/null | cut -d'=' -f2 || echo "7508")

echo ""
echo "===================================================="
echo "🎉 CONFIGURATION VIP DE TERMUX TERMINEE AVEC SUCCES !"
echo "===================================================="
echo " Vous pouvez désormais utiliser la commande universelle :"
echo "   fab         -> Lancer le serveur"
echo "   fab-stop    -> Arrêter le serveur"
echo "   fab-status  -> Vérifier l'état de la base de données"
echo "----------------------------------------------------"
echo " 👤 Identifiant Admin : admin"
echo " 🔑 Code PIN Admin   : ${ADMIN_PIN}"
echo " 🌐 Accès Mobile     : http://localhost:5000"
echo "===================================================="
echo ""
echo "🚀 Démarrage du serveur dans 2 secondes (Ctrl+C pour annuler)..."
sleep 2

python launcher.py --server-only
