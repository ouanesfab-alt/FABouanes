#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Script d'installation automatique Termux
# pour FABOuanes
# ==========================================

echo "🔄 1. Mise à jour des paquets Termux..."
pkg update && pkg upgrade -y

echo "📦 2. Installation des dépendances système..."
pkg install git python postgresql make clang -y

echo "🗄️ 3. Configuration de PostgreSQL..."
if [ ! -d "$PREFIX/var/lib/postgresql" ]; then
    initdb -D $PREFIX/var/lib/postgresql
fi

# Démarrer PostgreSQL
pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 3

# Créer la base de données si elle n'existe pas
createdb fabouanes 2>/dev/null || echo "La base fabouanes existe déjà."

echo "📂 4. Préparation du répertoire de l'application..."
# Si le script est exécuté depuis le dossier partagé Android, on copie le code dans le home de Termux
if [ -d "$HOME/FABouanes" ]; then
    echo "Le dossier $HOME/FABouanes existe déjà, mise à jour..."
    cd "$HOME/FABouanes"
    git pull
else
    echo "Clonage du projet dans le dossier local Termux..."
    cd "$HOME"
    git clone https://github.com/ouanesfab-alt/FABouanes.git
    cd "$HOME/FABouanes"
fi

echo "🐍 5. Installation des bibliothèques Python..."
pip install -r requirements.txt

echo "🔒 6. Génération automatique du fichier de configuration .env..."
cat << EOF > .env
FASTAPI_ENV=production
DATABASE_URL=postgresql://$(whoami)@localhost:5432/fabouanes
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
EOF

echo "⚙️ 7. Initialisation des tables de la base de données..."
python launcher.py --bootstrap-only

echo "⚡ 8. Création du script de démarrage rapide..."
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash
echo "⚡ Démarrage de PostgreSQL..."
pg_ctl -D $PREFIX/var/lib/postgresql start
sleep 2
echo "🚀 Lancement de FABOuanes..."
cd ~/FABouanes
python launcher.py --server-only
EOF

chmod +x ~/start_fab.sh

echo "==========================================="
echo "🎉 CONFIGURATION TERMINEE AVEC SUCCES !"
echo "==========================================="
echo "Pour lancer le serveur FABOuanes à l'avenir,"
echo "ouvrez Termux et tapez simplement :"
echo "  ~/start_fab.sh"
echo "==========================================="
