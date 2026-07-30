#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Script d'installation automatique Termux
# pour FABOuanes (Optimisé & Auto-réparateur)
# ==========================================

set -e

echo "📱 1. Verification des autorisations et stockage Termux..."
if [ -x "$(command -v termux-setup-storage)" ]; then
    termux-setup-storage || true
fi

# Autoriser les applications tierces (comme FABOuanes.apk) à lancer des commandes en arrière-plan
mkdir -p ~/.termux
if ! grep -q "allow-external-apps" ~/.termux/termux.properties 2>/dev/null; then
    echo "allow-external-apps = true" >> ~/.termux/termux.properties
fi

echo "🔄 2. Mise à jour des paquets et dépôts Termux..."
pkg update -y || pkg update -y --fix-missing || true
pkg upgrade -y || true

echo "📦 3. Installation des dépendances système (Python, PostgreSQL, C headers, Rust, Termux API)..."
pkg install git python postgresql make clang rust binutils libffi libjpeg-turbo libpng zlib freetype python-cryptography termux-api termux-tools net-tools -y

echo "🗄️ 4. Configuration et nettoyage de PostgreSQL..."
mkdir -p $PREFIX/var/lib/postgresql
if [ ! -f "$PREFIX/var/lib/postgresql/PG_VERSION" ]; then
    initdb -D $PREFIX/var/lib/postgresql
fi

# Nettoyage des verrous obsolètes si le téléphone s'est éteint brutalement
rm -f $PREFIX/var/lib/postgresql/postmaster.pid $PREFIX/var/lib/postgresql/postmaster.opts

# Démarrer PostgreSQL s'il n'est pas déjà lancé
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start || true
sleep 2

# Créer le rôle 'postgres' avec mot de passe '0000' et la base 'fabouanes'
psql -d postgres -c "CREATE ROLE postgres WITH SUPERUSER LOGIN PASSWORD '0000';" 2>/dev/null || psql -d postgres -c "ALTER ROLE postgres WITH SUPERUSER LOGIN PASSWORD '0000';" 2>/dev/null || true
createdb -O postgres fabouanes 2>/dev/null || createdb fabouanes 2>/dev/null || echo "Base de données fabouanes prête."

echo "📂 5. Préparation du répertoire de l'application..."
if [ -d "$HOME/FABouanes" ]; then
    echo "Mise à jour du code local dans $HOME/FABouanes..."
    cd "$HOME/FABouanes"
    git pull || true
else
    echo "Clonage du dépôt FABouanes..."
    cd "$HOME"
    git clone https://github.com/ouanesfab-alt/FABouanes.git
    cd "$HOME/FABouanes"
fi

echo "🔒 6. Configuration des variables d'environnement (.env)..."
TERMUX_USER=$(whoami 2>/dev/null || echo "postgres")
SECRET_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "default-secret-key-termux-123456789")

cat << EOF > .env
FASTAPI_ENV=production
DATABASE_URL=postgresql://${TERMUX_USER}@127.0.0.1:5432/fabouanes
SECRET_KEY=${SECRET_TOKEN}
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
FAB_HTTPS=1
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=7508
FAB_PASSWORD_MODE=pin
EOF

echo "🐍 7. Installation optimisée des bibliothèques Python..."
pip install --upgrade setuptools wheel --quiet
if [ -f "requirements-termux.txt" ]; then
    pip install --find-links=wheels --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements-termux.txt
else
    pip install --find-links=wheels --prefer-binary -r requirements.txt
fi

echo "⚙️ 8. Initialisation des tables de la base de données..."
python launcher.py --bootstrap-only

echo "⚡ 9. Création des raccourcis système et scripts de démarrage..."

# Script de démarrage start_fab.sh
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
# Nettoyage des verrous PostgreSQL obsolètes
rm -f $PREFIX/var/lib/postgresql/postmaster.pid
echo "⚡ Démarrage du moteur PostgreSQL..."
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 2

# Détection de l'IP Wi-Fi locale pour partage sur le réseau
LOCAL_IP=$(ifconfig 2>/dev/null | grep -E "inet (192\.168|10\.|172\.)" | awk '{print $2}' | head -n 1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

echo "=================================================="
echo "🚀 Lancement de FABOuanes en mode HTTPS..."
echo "  ► Accès sur ce téléphone : https://127.0.0.1:5000"
if [ "$LOCAL_IP" != "127.0.0.1" ]; then
    echo "  ► Accès Réseau Wi-Fi   : https://${LOCAL_IP}:5000"
fi
echo "=================================================="

cd ~/FABouanes
python launcher.py --server-only --https
EOF

chmod +x ~/start_fab.sh

# Configuration Termux:Widget (Raccourci 1-Clic sur l'écran d'accueil Android)
mkdir -p ~/.shortcuts
cp ~/start_fab.sh ~/.shortcuts/FABOuanes_ERP.sh
chmod +x ~/.shortcuts/FABOuanes_ERP.sh

# Raccourci binaire global 'fab' dans $PREFIX/bin
cat << 'EOF' > $PREFIX/bin/fab
#!/data/data/com.termux/files/usr/bin/bash
exec ~/start_fab.sh "$@"
EOF
chmod +x $PREFIX/bin/fab

# Alias 'fab' dans .bashrc
if ! grep -q "alias fab=" ~/.bashrc 2>/dev/null; then
    echo "alias fab='~/start_fab.sh'" >> ~/.bashrc
fi

# Configuration Démarrage Automatique Termux-Boot
mkdir -p ~/.termux/boot
cat << 'EOF' > ~/.termux/boot/start_fab_boot.sh
#!/data/data/com.termux/files/usr/bin/bash
rm -f $PREFIX/var/lib/postgresql/postmaster.pid
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 3
cd ~/FABouanes
python launcher.py --server-only --https >/dev/null 2>&1 &
EOF
chmod +x ~/.termux/boot/start_fab_boot.sh

echo "=================================================="
echo "🎉 CONFIGURATION TERMINEE AVEC SUCCES !"
echo "=================================================="
echo "Compte administrateur initial créé :"
echo "  Utilisateur : admin"
echo "  Code PIN    : 7508"
echo "--------------------------------------------------"
echo "Pour lancer FABOuanes à tout moment dans Termux,"
echo "tapez simplement la commande :"
echo "  fab"
echo "=================================================="
