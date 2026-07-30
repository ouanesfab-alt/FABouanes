#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Script d'installation automatique Termux
# pour FABOuanes
# ==========================================

set -e

echo "🔄 1. Mise à jour des paquets Termux..."
pkg update && pkg upgrade -y

echo "📦 2. Installation des dépendances système (compilateur Rust, C headers, JPEG, PNG, PostgreSQL, Cryptography, Termux API)..."
pkg install git python postgresql make clang rust binutils libffi libjpeg-turbo libpng zlib freetype python-cryptography termux-api termux-tools -y

echo "🗄️ 3. Configuration de PostgreSQL..."
if [ ! -d "$PREFIX/var/lib/postgresql" ]; then
    initdb -D $PREFIX/var/lib/postgresql
fi

# Démarrer PostgreSQL s'il n'est pas déjà lancé
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start || true
sleep 3

# Créer la base de données si elle n'existe pas
createdb fabouanes 2>/dev/null || echo "La base fabouanes existe déjà."

echo "📂 4. Préparation du répertoire de l'application..."
if [ -d "$HOME/FABouanes" ]; then
    echo "Le dossier $HOME/FABouanes existe déjà, mise à jour..."
    cd "$HOME/FABouanes"
    git pull || true
else
    echo "Clonage du projet dans le dossier local Termux..."
    cd "$HOME"
    git clone https://github.com/ouanesfab-alt/FABouanes.git
    cd "$HOME/FABouanes"
fi

echo "🔒 5. Génération automatique du fichier de configuration .env..."
TERMUX_USER=$(whoami 2>/dev/null || echo "postgres")
SECRET_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "default-secret-key-termux-123456789")
RANDOM_PIN=$(python -c "import secrets; print(secrets.randbelow(9000) + 1000)" 2>/dev/null || echo "8492")

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

echo "🐍 6. Installation des bibliothèques Python..."
pip install --upgrade setuptools wheel
if [ -f "requirements-termux.txt" ]; then
    pip install --find-links=wheels --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements-termux.txt
else
    pip install --find-links=wheels --prefer-binary -r requirements.txt
fi

echo "⚙️ 7. Initialisation des tables de la base de données..."
python launcher.py --bootstrap-only

echo "⚡ 8. Création du script de démarrage rapide..."
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
echo "⚡ Démarrage de PostgreSQL..."
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 2
echo "🚀 Lancement de FABOuanes en mode HTTPS..."
cd ~/FABouanes
python launcher.py --server-only --https
EOF

chmod +x ~/start_fab.sh

# Alias ultra-court 'fab' dans .bashrc
if ! grep -q "alias fab=" ~/.bashrc 2>/dev/null; then
    echo "alias fab='~/start_fab.sh'" >> ~/.bashrc
fi

# Support Termux-Boot (Démarrage automatique à l'allumage du smartphone/tablette)
mkdir -p ~/.termux/boot
cat << 'EOF' > ~/.termux/boot/start_fab_boot.sh
#!/data/data/com.termux/files/usr/bin/bash
pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1 || pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 3
cd ~/FABouanes
python launcher.py --server-only --https >/dev/null 2>&1 &
EOF
chmod +x ~/.termux/boot/start_fab_boot.sh

echo "==========================================="
echo "🎉 CONFIGURATION TERMINEE AVEC SUCCES !"
echo "==========================================="
echo "Compte administrateur initial créé :"
echo "  Utilisateur : admin"
echo "  Code PIN    : 7508"
echo "-------------------------------------------"
echo "Pour lancer le serveur FABOuanes à l'avenir,"
echo "ouvrez Termux et tapez simplement :"
echo "  ~/start_fab.sh"
echo "==========================================="
