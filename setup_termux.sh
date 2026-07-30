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

# Créer la base de données si elle n'existe pas
createdb fabouanes >/dev/null 2>&1 || true

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
FAB_HTTPS=0
SESSION_COOKIE_SECURE=0
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=7508
FAB_PASSWORD_MODE=pin
EOF

echo "🐍 7. Installation optimisée des bibliothèques Python..."
pip install --upgrade setuptools wheel --quiet
if [ -f "requirements-termux.txt" ]; then
    pip install --find-links=wheels --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements.txt
else
    pip install --find-links=wheels --prefer-binary -r requirements.txt
fi

echo "⚙️ 8. Initialisation des tables de la base de données..."
python launcher.py --bootstrap-only

echo "⚡ 9. Création des raccourcis système et scripts de démarrage..."

# Script de démarrage et gestionnaire de service start_fab.sh
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash

# Détection de Wakelock (Empeche Android de mettre le CPU en veille)
enable_wakelock() {
    if [ -x "$(command -v termux-wake-lock)" ]; then
        termux-wake-lock >/dev/null 2>&1 || true
    fi
}

disable_wakelock() {
    if [ -x "$(command -v termux-wake-unlock)" ]; then
        termux-wake-unlock >/dev/null 2>&1 || true
    fi
}

# Notification Android via Termux API
send_android_notification() {
    local title="$1"
    local msg="$2"
    if [ -x "$(command -v termux-notification)" ]; then
        termux-notification --title "$title" --content "$msg" --id "fabouanes_server" --priority low 2>/dev/null || true
    fi
}

start_postgres() {
    echo "⚡ Vérification du service PostgreSQL..."

    # Configurer postgresql.conf pour Android / Termux
    PG_CONF="$PREFIX/var/lib/postgresql/postgresql.conf"
    if [ -f "$PG_CONF" ]; then
        sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
        sed -i "s/listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
        if ! grep -q "listen_addresses = '*'" "$PG_CONF" 2>/dev/null; then
            echo "listen_addresses = '*'" >> "$PG_CONF"
        fi
        if ! grep -q "max_parallel_workers = 0" "$PG_CONF" 2>/dev/null; then
            echo "max_parallel_workers = 0" >> "$PG_CONF"
            echo "max_parallel_maintenance_workers = 0" >> "$PG_CONF"
        fi
    fi

    # 1. Attendre jusqu'à 4 secondes si le processus tourne déjà mais est en cours d'initialisation
    for i in 1 2 3 4; do
        if pg_isready -h 127.0.0.1 -p 5432 -d postgres >/dev/null 2>&1; then
            echo "🟢 PostgreSQL est actif et prêt sur 127.0.0.1:5432."
            createdb fabouanes >/dev/null 2>&1 || true
            return 0
        fi
        if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
            sleep 1
        else
            break
        fi
    done

    # 2. Si le processus tourne toujours sans répondre sur TCP 5432, on relance proprement
    if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
        echo "⚡ Redémarrage de PostgreSQL..."
        pg_ctl -D $PREFIX/var/lib/postgresql stop -m fast >/dev/null 2>&1 || pkill -9 -f "postgres" 2>/dev/null || true
        sleep 2
    fi

    # 3. Nettoyage des verrous et sockets obsolètes
    pkill -9 -f "postgres" 2>/dev/null || true
    sleep 1
    rm -f $PREFIX/var/lib/postgresql/postmaster.pid
    rm -f $PREFIX/var/lib/postgresql/postmaster.opts
    rm -f $PREFIX/tmp/.s.PGSQL.* 2>/dev/null || true
    rm -f /tmp/.s.PGSQL.* 2>/dev/null || true
    rm -f $PREFIX/var/run/postgresql/.s.PGSQL.* 2>/dev/null || true

    # 4. Démarrage de PostgreSQL sur port 5432
    echo "⚡ Démarrage de PostgreSQL..."
    pg_ctl -D $PREFIX/var/lib/postgresql -o "-c listen_addresses='*' -c port=5432 -c max_parallel_workers=0" -l ~/postgres_server.log start || true
    sleep 2

    # 5. Attente de disponibilité
    for i in 1 2 3 4 5; do
        if pg_isready -h 127.0.0.1 -p 5432 -d postgres >/dev/null 2>&1; then
            echo "🟢 PostgreSQL a démarré avec succès."
            break
        fi
        sleep 1
    done

    # 6. S'assurer que la base fabouanes existe
    createdb fabouanes >/dev/null 2>&1 || true
}

get_local_ip() {
    local ip=$(ifconfig 2>/dev/null | grep -E "inet (192\.168|10\.|172\.)" | awk '{print $2}' | head -n 1)
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
}

case "$1" in
    stop)
        echo "🛑 Arrêt des services FABOuanes..."
        pkill -f "launcher.py" 2>/dev/null || true
        pg_ctl -D $PREFIX/var/lib/postgresql stop 2>/dev/null || true
        disable_wakelock
        echo "✅ Serveur et base de données arrêtés avec succès."
        exit 0
        ;;
    status)
        echo "=================================================="
        echo "📊 STATUT DU SERVEUR FABOUANES"
        echo "=================================================="
        if pgrep -f "launcher.py" >/dev/null; then
            PID=$(pgrep -f "launcher.py" | head -n 1)
            echo "🟢 Serveur FastAPI : EN COURS (PID: $PID)"
        else
            echo "🔴 Serveur FastAPI : ARRETE"
        fi
        if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
            echo "🟢 PostgreSQL      : EN COURS"
        else
            echo "🔴 PostgreSQL      : ARRETE"
        fi
        LOCAL_IP=$(get_local_ip)
        PROTO="http"
        if [ "$FAB_HTTPS" = "1" ] || [[ "$*" == *"--https"* ]]; then
            PROTO="https"
        fi
        echo "  ► Accès Local  : ${PROTO}://127.0.0.1:5000"
        if [ "$LOCAL_IP" != "127.0.0.1" ]; then
            echo "  ► Accès Wi-Fi  : ${PROTO}://${LOCAL_IP}:5000"
        fi
        echo "=================================================="
        exit 0
        ;;
    logs)
        echo "📜 Affichage des journaux en direct (Ctrl+C pour quitter)..."
        tail -f ~/fab_server.log 2>/dev/null || echo "Aucun journal disponible pour l'instant."
        exit 0
        ;;
    update)
        echo "🔄 Mise à jour de FABOuanes depuis GitHub..."
        cd ~/FABouanes
        git pull
        pip install --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements.txt
        python launcher.py --bootstrap-only
        echo "✅ Mise à jour terminée ! Redémarrage du serveur..."
        exec $0 start
        ;;
    *)
        # Libérer le port 5000 s'il était occupé par une ancienne instance
        fuser -k 5000/tcp >/dev/null 2>&1 || true
        pkill -f "launcher.py" 2>/dev/null || true
        sleep 1

        enable_wakelock
        start_postgres
        LOCAL_IP=$(get_local_ip)
        PROTO="http"
        if [ "$FAB_HTTPS" = "1" ] || [[ "$*" == *"--https"* ]]; then
            PROTO="https"
        fi
        echo "=================================================="
        echo "🚀 Lancement de FABOuanes (Wakelock actif)..."
        echo "  ► Accès Local  : ${PROTO}://127.0.0.1:5000"
        if [ "$LOCAL_IP" != "127.0.0.1" ]; then
            echo "  ► Accès Wi-Fi  : ${PROTO}://${LOCAL_IP}:5000"
        fi
        echo "=================================================="
        send_android_notification "FABOuanes Serveur Actif" "Disponible sur ${PROTO}://${LOCAL_IP}:5000"

        # Ouverture automatique du navigateur Android dans 2s (multi-stratégie)
        (
            sleep 2
            termux-open-url "${PROTO}://127.0.0.1:5000" >/dev/null 2>&1 || true
            termux-open "${PROTO}://127.0.0.1:5000" >/dev/null 2>&1 || true
            am start --user 0 -a android.intent.action.VIEW -d "${PROTO}://127.0.0.1:5000" >/dev/null 2>&1 || true
            am start -a android.intent.action.VIEW -d "${PROTO}://127.0.0.1:5000" >/dev/null 2>&1 || true
            xdg-open "${PROTO}://127.0.0.1:5000" >/dev/null 2>&1 || true
        ) &

        cd ~/FABouanes
        python launcher.py --server-only "$@" 2>&1 | tee -a ~/fab_server.log
        ;;
esac
EOF

chmod +x ~/start_fab.sh

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
~/start_fab.sh start > ~/fab_server.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start_fab_boot.sh

echo "=================================================="
echo "🎉 CONFIGURATION TERMINEE AVEC SUCCES !"
echo "=================================================="
echo "Compte administrateur initial créé :"
echo "  Utilisateur : admin"
echo "  Code PIN    : 7508"
echo "--------------------------------------------------"
echo "Commandes de gestion rapides dans Termux :"
echo "  • fab          : Démarrer le serveur"
echo "  • fab stop     : Arrêter le serveur"
echo "  • fab status   : Vérifier l'état du serveur"
echo "  • fab logs     : Consulter les logs en direct"
echo "  • fab update   : Mettre à jour l'application"
echo "=================================================="
