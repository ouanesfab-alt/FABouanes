#!/data/data/com.termux/files/usr/bin/bash

# ==============================================================================
# Script d'installation & de supervision automatique Termux
# pour FABOuanes (Optimisé ARM / Mobile & Résilience Anti-Kill Android)
#
# INSTALLATION EN UNE COMMANDE :
#   curl -fsSL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh | bash
# ==============================================================================

# Compatible curl | bash : ne pas quitter sur erreurs non critiques
set +e

# Couleurs ANSI
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}🚀 INSTALLATION DU SERVEUR MOBILE FABOUANES SUR ANDROID/TERMUX ${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"

echo "📱 1. Verification des autorisations et stockage partagé Android..."
if [ -x "$(command -v termux-setup-storage)" ]; then
    termux-setup-storage || true
fi

echo "🔄 2. Mise à jour des paquets et dépôts Termux..."
pkg update -y || pkg update -y --fix-missing || true
pkg upgrade -y || true

echo "📦 3. Installation des dépendances système (Python, PostgreSQL, C headers, Rust, Termux API, QR Code)..."
pkg install git python postgresql make clang rust binutils libffi libjpeg-turbo libpng zlib freetype python-cryptography termux-api termux-tools net-tools qrencode -y

echo "🗄️ 4. Configuration et optimisation mémoire de PostgreSQL pour mobile..."
mkdir -p $PREFIX/var/lib/postgresql
if [ ! -f "$PREFIX/var/lib/postgresql/PG_VERSION" ]; then
    initdb -D $PREFIX/var/lib/postgresql
fi

# Profil mémoire allégé pour Android (évite que le Low Memory Killer d'Android ne tue PostgreSQL)
PG_CONF="$PREFIX/var/lib/postgresql/postgresql.conf"
if [ -f "$PG_CONF" ]; then
    sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
    sed -i "s/listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
    for opt in \
        "shared_buffers = 32MB" \
        "work_mem = 2MB" \
        "maintenance_work_mem = 16MB" \
        "effective_cache_size = 64MB" \
        "max_connections = 20" \
        "wal_buffers = 1MB" \
        "min_wal_size = 32MB" \
        "max_wal_size = 128MB" \
        "max_parallel_workers = 0" \
        "max_parallel_maintenance_workers = 0"; do
        key=$(echo "$opt" | cut -d= -f1 | xargs)
        if ! grep -q "^${key}" "$PG_CONF" 2>/dev/null; then
            echo "$opt" >> "$PG_CONF"
        fi
    done
fi

# Nettoyage des verrous obsolètes si le smartphone s'est éteint brutalement
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
if [ ! -f .env ]; then
    TERMUX_USER=$(whoami 2>/dev/null || echo "postgres")
    SECRET_TOKEN=$(python -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "default-secret-key-termux-123456789")
    ADMIN_PIN=$(python -c "import random; print(f'{random.randint(1000,9999):04d}')" 2>/dev/null || echo "7508")

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
DEFAULT_ADMIN_PASSWORD=${ADMIN_PIN}
FAB_PASSWORD_MODE=pin
EOF
    echo -e "${GREEN}🔑 Nouveau compte admin initial généré — Code PIN: ${ADMIN_PIN}${RESET}"
else
    echo "Fichier .env existant détecté — configuration et identifiants préservés."
fi

echo "🔍 6b. Verification des prerequis de compilation C/Rust pour Termux..."
if [ -f "scripts/check_termux_requirements.py" ]; then
    python scripts/check_termux_requirements.py || {
        echo "⚠️ Des prérequis système manquent pour la compilation native. Tentative d'installation automatique via pkg..."
        pkg install clang make pkg-config libffi openssl rust -y || true
    }
fi

echo "🐍 7. Installation optimisée des bibliothèques Python..."
pip install --upgrade setuptools wheel --quiet
if [ -f "requirements-termux.txt" ]; then
    pip install --find-links=wheels --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements.txt
else
    pip install --find-links=wheels --prefer-binary -r requirements.txt
fi

echo "⚙️ 8. Initialisation des tables de la base de données..."
FAB_DESKTOP=0 FAB_HTTPS=0 SESSION_COOKIE_SECURE=0 python launcher.py --bootstrap-only

echo "⚡ 9. Création du gestionnaire de service et des raccourcis système..."

# ─── Script start_fab.sh enrichi ──────────────────────────────────────────────
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash

# ─── Couleurs ANSI ───────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# Détection de Wakelock (Empêche Android de suspendre le CPU en veille)
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

# Notification Android persistante dans la barre d'état
update_android_notification() {
    local status="$1"
    local url="$2"
    if [ -x "$(command -v termux-notification)" ]; then
        termux-notification \
            --id "fabouanes_server" \
            --title "FABOuanes ERP ($status)" \
            --content "$url" \
            --ongoing \
            --priority high \
            --button1 "Arrêter" \
            --button1-action "fab stop" \
            2>/dev/null || true
    fi
}

clear_android_notification() {
    if [ -x "$(command -v termux-notification-remove)" ]; then
        termux-notification-remove "fabouanes_server" 2>/dev/null || true
    fi
}

# Synchronisation miroir des sauvegardes vers le stockage partagé Android
sync_backups_to_sdcard() {
    local source_dir="$HOME/FABouanes/app_data/backups/local"
    local dest_dir="$HOME/storage/shared/Documents/FABouanes_Backups"
    
    if [ -d "$HOME/storage/shared" ]; then
        mkdir -p "$dest_dir" 2>/dev/null || true
        if [ -d "$source_dir" ] && [ -d "$dest_dir" ]; then
            local count=0
            for backup in "$source_dir"/*; do
                if [ -f "$backup" ]; then
                    local base_name=$(basename "$backup")
                    if [ ! -f "$dest_dir/$base_name" ]; then
                        cp "$backup" "$dest_dir/" 2>/dev/null && ((count++)) || true
                    fi
                fi
            done
            if [ "$count" -gt 0 ]; then
                echo -e "${GREEN}💾 $count sauvegarde(s) synchronisée(s) vers Documents/FABouanes_Backups/ (Stockage Android)${RESET}"
            fi
        fi
    fi
}

start_postgres() {
    echo -e "${CYAN}⚡ Vérification du service PostgreSQL...${RESET}"

    PG_CONF="$PREFIX/var/lib/postgresql/postgresql.conf"
    if [ -f "$PG_CONF" ]; then
        sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
        sed -i "s/listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF" 2>/dev/null || true
        for opt in \
            "shared_buffers = 32MB" \
            "work_mem = 2MB" \
            "maintenance_work_mem = 16MB" \
            "effective_cache_size = 64MB" \
            "max_connections = 20" \
            "wal_buffers = 1MB" \
            "min_wal_size = 32MB" \
            "max_wal_size = 128MB" \
            "max_parallel_workers = 0" \
            "max_parallel_maintenance_workers = 0"; do
            key=$(echo "$opt" | cut -d= -f1 | xargs)
            if ! grep -q "^${key}" "$PG_CONF" 2>/dev/null; then
                echo "$opt" >> "$PG_CONF"
            fi
        done
    fi

    for i in 1 2 3 4; do
        if pg_isready -h 127.0.0.1 -p 5432 -d postgres >/dev/null 2>&1; then
            echo -e "${GREEN}🟢 PostgreSQL est actif et prêt sur 127.0.0.1:5432.${RESET}"
            createdb fabouanes >/dev/null 2>&1 || true
            return 0
        fi
        if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
            sleep 1
        else
            break
        fi
    done

    if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
        echo -e "${YELLOW}⚡ Redémarrage de PostgreSQL...${RESET}"
        pg_ctl -D $PREFIX/var/lib/postgresql stop -m fast >/dev/null 2>&1 || pkill -9 -f "postgres" 2>/dev/null || true
        sleep 2
    fi

    pkill -9 -f "postgres" 2>/dev/null || true
    sleep 1
    rm -f $PREFIX/var/lib/postgresql/postmaster.pid
    rm -f $PREFIX/var/lib/postgresql/postmaster.opts
    rm -f $PREFIX/tmp/.s.PGSQL.* 2>/dev/null || true
    rm -f /tmp/.s.PGSQL.* 2>/dev/null || true
    rm -f $PREFIX/var/run/postgresql/.s.PGSQL.* 2>/dev/null || true

    echo -e "${CYAN}⚡ Démarrage de PostgreSQL...${RESET}"
    pg_ctl -D $PREFIX/var/lib/postgresql -o "-c listen_addresses='*' -c port=5432 -c shared_buffers=32MB -c max_connections=20 -c max_parallel_workers=0" -l ~/postgres_server.log start || true
    sleep 2

    for i in 1 2 3 4 5; do
        if pg_isready -h 127.0.0.1 -p 5432 -d postgres >/dev/null 2>&1; then
            echo -e "${GREEN}🟢 PostgreSQL a démarré avec succès.${RESET}"
            break
        fi
        sleep 1
    done

    createdb fabouanes >/dev/null 2>&1 || true
}

get_network_ips() {
    local ips=$(ifconfig 2>/dev/null | grep -E "inet (192\.168|10\.|172\.)" | awk '{print $2}' | sort -u)
    if [ -z "$ips" ]; then
        ips=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | sort -u)
    fi
    echo "$ips"
}

# Rotation des journaux (> 2 Mo)
rotate_logs() {
    LOG_FILE="$HOME/fab_server.log"
    if [ -f "$LOG_FILE" ]; then
        SIZE=$(wc -c <"$LOG_FILE" 2>/dev/null || echo "0")
        if [ "$SIZE" -gt 2097152 ]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            echo -e "${YELLOW}🔄 Journal archivé (taille > 2 Mo)${RESET}"
        fi
    fi
}

case "$1" in
    stop)
        echo -e "${YELLOW}🛑 Arrêt des services FABOuanes...${RESET}"
        fuser -k 5000/tcp >/dev/null 2>&1 || true
        pkill -f "uvicorn app.main:app" 2>/dev/null || true
        pkill -f "launcher.py" 2>/dev/null || true
        pg_ctl -D $PREFIX/var/lib/postgresql stop 2>/dev/null || true
        disable_wakelock
        clear_android_notification
        sync_backups_to_sdcard
        echo -e "${GREEN}✅ Serveur et base de données arrêtés avec succès.${RESET}"
        exit 0
        ;;
    status)
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        echo -e "${BOLD}${CYAN}📊 STATUT DU SERVEUR FABOUANES${RESET}"
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        
        # Statut du processus Uvicorn
        UVI_PID=$(pgrep -f "uvicorn app.main:app" | head -n 1)
        if [ -n "$UVI_PID" ]; then
            echo -e "  • Processus Uvicorn : ${GREEN}🟢 ACTIF (PID: $UVI_PID)${RESET}"
        else
            echo -e "  • Processus Uvicorn : ${RED}🔴 ARRETÉ${RESET}"
        fi

        # Statut PostgreSQL
        if pg_ctl -D $PREFIX/var/lib/postgresql status >/dev/null 2>&1; then
            echo -e "  • PostgreSQL        : ${GREEN}🟢 ACTIF${RESET}"
        else
            echo -e "  • PostgreSQL        : ${RED}🔴 ARRETÉ${RESET}"
        fi

        # Statut HTTP
        HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:5000/health" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "  • Endpoint /health  : ${GREEN}🟢 REPOND (HTTP 200 OK)${RESET}"
        else
            echo -e "  • Endpoint /health  : ${RED}🔴 INDISPONIBLE (Code HTTP: $HTTP_CODE)${RESET}"
        fi

        echo -e "\n${BOLD}  ► Accès Local  : http://127.0.0.1:5000${RESET}"
        NET_IPS=$(get_network_ips)
        for net_ip in $NET_IPS; do
            if [ "$net_ip" = "192.168.43.1" ]; then
                echo -e "  ► ${CYAN}Point d'accès Hotspot : ${BOLD}http://${net_ip}:5000${RESET}"
            else
                echo -e "  ► Réseau Wi-Fi local  : ${BOLD}http://${net_ip}:5000${RESET}"
            fi
        done
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        exit 0
        ;;
    logs)
        echo -e "${CYAN}📜 Affichage des 50 derniers journaux en direct (Ctrl+C pour quitter)...${RESET}"
        tail -n 50 -f ~/fab_server.log 2>/dev/null || echo "Aucun journal disponible pour l'instant."
        exit 0
        ;;
    battery)
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        echo -e "${BOLD}${CYAN}🔋 GUIDE ANTI-VEILLE ANDROID (Wakelock & Batterie)${RESET}"
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        echo -e "Pour empêcher Android de couper le serveur quand l'écran s'éteint :"
        echo -e "1. Paramètres Android > Applications > Termux > Batterie"
        echo -e "   -> Sélectionner : ${GREEN}Non restreinte${RESET} (ou Pas d'optimisation)"
        echo -e "2. Paramètres Android > Applications > Termux"
        echo -e "   -> Autoriser l'activité en arrière-plan"
        echo -e "3. Sur Xiaomi (MIUI/HyperOS) :"
        echo -e "   -> Activer 'Démarrage automatique' pour Termux"
        echo -e "4. Sur Samsung (OneUI) :"
        echo -e "   -> Ajouter Termux à 'Applis jamais en veille'"
        echo -e "5. Référence détaillée par constructeur : https://dontkillmyapp.com"
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        exit 0
        ;;
    backup-sync)
        echo -e "${CYAN}💾 Synchronisation manuelle des sauvegardes vers Android...${RESET}"
        sync_backups_to_sdcard
        echo -e "${GREEN}✅ Synchronisation terminée.${RESET}"
        exit 0
        ;;
    update)
        echo -e "${YELLOW}🔄 Mise à jour complète de FABOuanes depuis GitHub...${RESET}"
        cd ~/FABouanes
        git pull
        pip install --find-links=wheels --prefer-binary -r requirements-termux.txt || pip install --prefer-binary -r requirements.txt
        exec bash setup_termux.sh
        ;;
    *)
        # ─── Tuer toute instance orpheline précédente ───────────────────
        fuser -k 5000/tcp >/dev/null 2>&1 || true
        pkill -f "uvicorn app.main:app" 2>/dev/null || true
        pkill -f "launcher.py"          2>/dev/null || true
        sleep 1

        enable_wakelock
        start_postgres
        rotate_logs
        cd ~/FABouanes

        # Synchroniser les sauvegardes au démarrage
        sync_backups_to_sdcard

        # ─── Initialiser .env uniquement s'il est manquant ─────────────
        if [ ! -f .env ]; then
            TERMUX_USER_RUN=$(whoami 2>/dev/null || echo "postgres")
            SECRET_TOKEN_RUN=$(python -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "default-secret-key-termux")
            ADMIN_PIN_RUN=$(python -c "import random; print(f'{random.randint(1000,9999):04d}')" 2>/dev/null || echo "7508")
            cat > .env << ENVEOF
FASTAPI_ENV=production
DATABASE_URL=postgresql://${TERMUX_USER_RUN}@127.0.0.1:5432/fabouanes
SECRET_KEY=${SECRET_TOKEN_RUN}
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
FAB_HTTPS=0
SESSION_COOKIE_SECURE=0
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=${ADMIN_PIN_RUN}
FAB_PASSWORD_MODE=pin
ENVEOF
        fi

        export FAB_DESKTOP=0
        export FAB_HOST=0.0.0.0
        export FAB_PORT=5000
        export FAB_HTTPS=0
        export SESSION_COOKIE_SECURE=0
        export FASTAPI_ENV=production

        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        echo -e "${BOLD}${GREEN}🚀 Démarrage du serveur FABOuanes...${RESET}"
        echo -e "  ► Local : ${BOLD}http://127.0.0.1:5000${RESET}"

        NET_IPS=$(get_network_ips)
        PRIMARY_URL="http://127.0.0.1:5000"
        for net_ip in $NET_IPS; do
            if [ "$net_ip" = "192.168.43.1" ]; then
                echo -e "  ► ${CYAN}Hotspot Mobile : ${BOLD}http://${net_ip}:5000${RESET}"
                PRIMARY_URL="http://${net_ip}:5000"
            else
                echo -e "  ► Wi-Fi Réseau  : ${BOLD}http://${net_ip}:5000${RESET}"
                PRIMARY_URL="http://${net_ip}:5000"
            fi
        done
        echo -e "${BOLD}${CYAN}==================================================${RESET}"

        # ─── Lancer Uvicorn en HTTP pur (1 worker optimisé mobile) ─────
        python -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port 5000 \
            --timeout-keep-alive 30 \
            --limit-concurrency 100 \
            --no-access-log \
            --log-level info \
            2>&1 | tee -a ~/fab_server.log &
        SERVER_PID=$!

        # ─── Attendre que le serveur réponde ────────────────────────────
        echo -e "${CYAN}⏳ Attente de la disponibilité HTTP (max 60s)...${RESET}"
        READY=0
        for i in $(seq 1 60); do
            if ! kill -0 "$SERVER_PID" 2>/dev/null; then
                echo ""
                echo -e "${RED}❌ ERREUR : uvicorn s'est arrêté pendant le démarrage !${RESET}"
                echo "══════════════ LOGS (20 dernières lignes) ══════════════"
                tail -n 20 ~/fab_server.log
                echo "════════════════════════════════════════════════════════"
                clear_android_notification
                exit 1
            fi
            HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:5000/health" 2>/dev/null || echo "000")
            if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "503" ]; then
                READY=1
                break
            fi
            printf "."
            sleep 1
        done
        echo ""

        if [ "$READY" = "1" ]; then
            echo ""
            echo -e "${BOLD}${GREEN}=============================================="
            echo -e "✅  Serveur FABOuanes opérationnel !"
            echo -e "==============================================${RESET}"
            echo -e "  Local : ${BOLD}http://127.0.0.1:5000${RESET}"

            for net_ip in $NET_IPS; do
                if [ "$net_ip" = "192.168.43.1" ]; then
                    echo -e "  Hotspot Mobile : ${BOLD}http://${net_ip}:5000${RESET}"
                else
                    echo -e "  Wi-Fi Réseau   : ${BOLD}http://${net_ip}:5000${RESET}"
                fi
                if command -v qrencode >/dev/null 2>&1; then
                    echo -e "\n${CYAN}📱 QR Code pour se connecter à http://${net_ip}:5000 :${RESET}"
                    qrencode -t ANSI256 "http://${net_ip}:5000" 2>/dev/null || qrencode -t UTF8 "http://${net_ip}:5000" 2>/dev/null || true
                fi
            done

            echo ""
            echo -e "  ${CYAN}Commandes utiles :${RESET}"
            echo -e "  • ${BOLD}fab status${RESET}      : Vérifier la santé du serveur"
            echo -e "  • ${BOLD}fab logs${RESET}        : Voir les logs en direct"
            echo -e "  • ${BOLD}fab stop${RESET}        : Arrêter le serveur"
            echo -e "  • ${BOLD}fab backup-sync${RESET} : Synchroniser vers stockage Android"
            echo -e "  • ${BOLD}fab battery${RESET}     : Guide anti-veille Android"
            echo -e "${BOLD}${GREEN}==============================================${RESET}"
            update_android_notification "En ligne" "$PRIMARY_URL"
        else
            echo -e "${RED}❌ TIMEOUT : le serveur n'a pas répondu en 60 secondes.${RESET}"
            echo "══════════════ LOGS (30 dernières lignes) ══════════════"
            tail -n 30 ~/fab_server.log
            echo "════════════════════════════════════════════════════════"
        fi

        # Garder le terminal ouvert et écouter jusqu'à l'arrêt
        wait $SERVER_PID
        clear_android_notification
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

# ─── Configuration Démarrage Automatique Termux-Boot ─────────────────────────
mkdir -p ~/.termux/boot
cat << 'EOF' > ~/.termux/boot/start_fab_boot.sh
#!/data/data/com.termux/files/usr/bin/bash
~/start_fab.sh start > ~/fab_server.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start_fab_boot.sh

# ─── Configuration Termux:Widget (Raccourcis 1-clic écran d'accueil) ──────────
SHORTCUTS_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS_DIR"

cat << 'EOF' > "$SHORTCUTS_DIR/Demarrer_FAB.sh"
#!/data/data/com.termux/files/usr/bin/bash
~/start_fab.sh
EOF

cat << 'EOF' > "$SHORTCUTS_DIR/Arreter_FAB.sh"
#!/data/data/com.termux/files/usr/bin/bash
~/start_fab.sh stop
EOF

cat << 'EOF' > "$SHORTCUTS_DIR/Statut_FAB.sh"
#!/data/data/com.termux/files/usr/bin/bash
~/start_fab.sh status
echo ""
read -p "Appuyez sur Entrée pour fermer..."
EOF

cat << 'EOF' > "$SHORTCUTS_DIR/Sauvegarde_Android.sh"
#!/data/data/com.termux/files/usr/bin/bash
~/start_fab.sh backup-sync
echo ""
read -p "Appuyez sur Entrée pour fermer..."
EOF

chmod +x "$SHORTCUTS_DIR"/*.sh 2>/dev/null || true

echo -e "\n${BOLD}${GREEN}================================================================${RESET}"
echo -e "${BOLD}${GREEN}🎉 CONFIGURATION MOBILE TERMUX TERMINEE AVEC SUCCES !${RESET}"
echo -e "${BOLD}${GREEN}================================================================${RESET}"
echo "Améliorations activées :"
echo "  ✓ Profil PostgreSQL ultra-léger (RAM optimisée pour mobile)"
echo "  ✓ Wakelock CPU + Notification permanente Android avec bouton Arrêt"
echo "  ✓ Sauvegardes miroir automatiques vers Documents/FABouanes_Backups/ (Stockage interne)"
echo "  ✓ Détection Point d'accès Hotspot mobile & Wi-Fi avec QR Code"
echo "  ✓ Raccourcis 1-clic pour l'application Termux:Widget (~/.shortcuts/)"
echo "----------------------------------------------------------------"
echo "Commandes rapides dans Termux :"
echo "  • fab             : Démarrer le serveur FABOuanes"
echo "  • fab stop        : Arrêter proprement tous les services"
echo "  • fab status      : Consulter l'état en direct et les adresses IP"
echo "  • fab backup-sync : Synchroniser les sauvegardes vers le stockage Android"
echo "  • fab battery     : Guide pour désactiver l'optimisation de batterie"
echo "  • fab logs        : Consulter les logs en temps réel"
echo "  • fab update      : Mettre à jour l'application depuis GitHub"
echo -e "${BOLD}${GREEN}================================================================${RESET}\n"
