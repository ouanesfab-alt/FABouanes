#!/data/data/com.termux/files/usr/bin/bash

# ==========================================
# Script d'installation automatique Termux
# pour FABOuanes (Optimisé & Auto-réparateur)
#
# INSTALLATION EN UNE COMMANDE :
#   curl -fsSL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh | bash
# ==========================================

# Compatible curl | bash : ne pas quitter sur erreurs non critiques
set +e

echo "📱 1. Verification des autorisations et stockage Termux..."
if [ -x "$(command -v termux-setup-storage)" ]; then
    termux-setup-storage || true
fi

echo "🔄 2. Mise à jour des paquets et dépôts Termux..."
pkg update -y || pkg update -y --fix-missing || true
pkg upgrade -y || true

echo "📦 3. Installation des dépendances système (Python, PostgreSQL, C headers, Rust, Termux API, QR Code)..."
pkg install git python postgresql make clang rust binutils libffi libjpeg-turbo libpng zlib freetype python-cryptography termux-api termux-tools net-tools qrencode -y

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

echo "🔐 8b. Génération du certificat SSL auto-signé..."
python -c "
import subprocess, sys
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from datetime import datetime, timezone, timedelta
    import ipaddress
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'FABOuanes')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName('localhost'),
            x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
        ]), critical=False)
        .sign(key, hashes.SHA256())
    )
    open('key.pem','wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    open('cert.pem','wb').write(cert.public_bytes(serialization.Encoding.PEM))
    print('✅ Certificat SSL généré: cert.pem + key.pem')
except Exception as e:
    print('⚠️ SSL non disponible:', e)
"

echo "⚡ 9. Création des raccourcis système et scripts de démarrage..."

# Script de démarrage et gestionnaire de service start_fab.sh
cat << 'EOF' > ~/start_fab.sh
#!/data/data/com.termux/files/usr/bin/bash

# ─── Couleurs ANSI ───────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

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
    echo -e "${CYAN}⚡ Vérification du service PostgreSQL...${RESET}"

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
    pg_ctl -D $PREFIX/var/lib/postgresql -o "-c listen_addresses='*' -c port=5432 -c max_parallel_workers=0" -l ~/postgres_server.log start || true
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

get_local_ip() {
    local ip=$(ifconfig 2>/dev/null | grep -E "inet (192\.168|10\.|172\.)" | awk '{print $2}' | head -n 1)
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
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
            echo -e "  • Endpoint /health  : ${GREEN}🟢 RESPOND (HTTP 200 OK)${RESET}"
        else
            echo -e "  • Endpoint /health  : ${RED}🔴 INDISPONIBLE (Code HTTP: $HTTP_CODE)${RESET}"
        fi

        LOCAL_IP=$(get_local_ip)
        echo -e "\n${BOLD}  ► Accès Local  : http://127.0.0.1:5000${RESET}"
        if [ "$LOCAL_IP" != "127.0.0.1" ]; then
            echo -e "${BOLD}  ► Accès Wi-Fi  : http://${LOCAL_IP}:5000${RESET}"
        fi
        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        exit 0
        ;;
    logs)
        echo -e "${CYAN}📜 Affichage des 50 derniers journaux en direct (Ctrl+C pour quitter)...${RESET}"
        tail -n 50 -f ~/fab_server.log 2>/dev/null || echo "Aucun journal disponible pour l'instant."
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
        # ─── Tuer toute instance précédente ───────────────────────────
        fuser -k 5000/tcp >/dev/null 2>&1 || true
        pkill -f "uvicorn app.main:app" 2>/dev/null || true
        pkill -f "launcher.py"          2>/dev/null || true
        sleep 1

        enable_wakelock
        start_postgres
        rotate_logs
        LOCAL_IP=$(get_local_ip)
        cd ~/FABouanes

        # ─── ÉCRASER .env à chaque démarrage (valeurs HTTP garanties) ──
        TERMUX_USER_RUN=$(whoami 2>/dev/null || echo "postgres")
        SECRET_TOKEN_RUN=$(cat .env 2>/dev/null | grep SECRET_KEY | cut -d= -f2 || python -c "import secrets; print(secrets.token_hex(32))")
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
DEFAULT_ADMIN_PASSWORD=7508
FAB_PASSWORD_MODE=pin
ENVEOF

        export FAB_DESKTOP=0
        export FAB_HOST=0.0.0.0
        export FAB_PORT=5000
        export FAB_HTTPS=0
        export SESSION_COOKIE_SECURE=0
        export FASTAPI_ENV=production

        echo -e "${BOLD}${CYAN}==================================================${RESET}"
        echo -e "${BOLD}${GREEN}🚀 Démarrage de FABOuanes...${RESET}"
        echo -e "  ► Local  : ${BOLD}http://127.0.0.1:5000${RESET}"
        [ "$LOCAL_IP" != "127.0.0.1" ] && echo -e "  ► Wi-Fi  : ${BOLD}http://${LOCAL_IP}:5000${RESET}"
        echo -e "${BOLD}${CYAN}==================================================${RESET}"

        # ─── Lancer uvicorn en HTTP pur (Optimisé réseau multi-appareils) ─
        python -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port 5000 \
            --timeout-keep-alive 30 \
            --limit-concurrency 100 \
            --no-access-log \
            --log-level info \
            2>&1 | tee -a ~/fab_server.log &
        SERVER_PID=$!

        # ─── Attendre que le serveur réponde vraiment en HTTP ─────────
        echo -e "${CYAN}⏳ Attente de la réponse HTTP réelle (max 60s)...${RESET}"
        READY=0
        for i in $(seq 1 60); do
            if ! kill -0 "$SERVER_PID" 2>/dev/null; then
                echo ""
                echo -e "${RED}❌ ERREUR : uvicorn s'est arrêté pendant le démarrage !${RESET}"
                echo "══════════════ LOGS (20 dernières lignes) ══════════════"
                tail -n 20 ~/fab_server.log
                echo "════════════════════════════════════════════════════════"
                echo "Pour voir tous les logs : cat ~/fab_server.log"
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
            if [ "$LOCAL_IP" != "127.0.0.1" ]; then
                echo -e "  Wi-Fi : ${BOLD}http://${LOCAL_IP}:5000${RESET}"
                if command -v qrencode >/dev/null 2>&1; then
                    echo -e "\n${CYAN}📱 Scannez ce QR Code depuis un autre appareil Wi-Fi :${RESET}"
                    qrencode -t ANSI256 "http://${LOCAL_IP}:5000" 2>/dev/null || qrencode -t UTF8 "http://${LOCAL_IP}:5000" 2>/dev/null || true
                fi
            fi
            echo ""
            echo -e "  ${CYAN}Commandes utiles :${RESET}"
            echo -e "  • ${BOLD}fab status${RESET} : Vérifier la santé du serveur"
            echo -e "  • ${BOLD}fab logs${RESET}   : Voir les logs en temps réel"
            echo -e "  • ${BOLD}fab stop${RESET}   : Arrêter le serveur"
            echo -e "${BOLD}${GREEN}==============================================${RESET}"
            send_android_notification "FABOuanes Prêt" "http://127.0.0.1:5000"
        else
            echo -e "${RED}❌ TIMEOUT : le serveur n'a pas répondu en 60 secondes.${RESET}"
            echo "══════════════ LOGS (30 dernières lignes) ══════════════"
            tail -n 30 ~/fab_server.log
            echo "════════════════════════════════════════════════════════"
        fi

        # Garder le shell en vie jusqu'à l'arrêt du serveur
        wait $SERVER_PID
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
