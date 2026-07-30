"""Lanceur desktop FABOuanes."""
import os
os.environ["FAB_DESKTOP"] = "1"
# Ecoute sur toutes les interfaces (LAN + localhost) par defaut
# Peut etre remplace par FAB_HOST=127.0.0.1 dans .env pour revenir en mode local uniquement
if not os.environ.get("FAB_HOST", "").strip():
    os.environ["FAB_HOST"] = "0.0.0.0"

import json
import shutil
import sys
import time
import socket
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _old_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost
        def _call_connection_lost_patched(self, exc):
            try:
                _old_call_connection_lost(self, exc)
            except (ConnectionResetError, AttributeError, OSError):
                pass
        _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost_patched
    except Exception:
        pass

APP_NAME = "FABOuanes"
SERVER_MODE_ARGS = {"--server", "--server-only", "--network-server"}
LAUNCH_ARGS = {arg.strip().lower() for arg in sys.argv[1:] if arg.strip()}
try:
    from app.version import VERSION_LABEL as APP_VERSION
except Exception:
    APP_VERSION = "v1.0.0"


if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local" if os.name == "nt" else Path.home())) / APP_NAME
WEBVIEW_STORAGE_DIR = DATA_DIR / "webview"
BACKUP_DIR = DATA_DIR / "backups"
LOCAL_BACKUP_DIR = BACKUP_DIR / "local"
LOG_DIR = DATA_DIR / "logs"
STATE_FILE = DATA_DIR / "desktop_install_state.json"
DESKTOP_ICON_PATH = STATIC_DIR / "FABOuanes_desktop.ico"
FALLBACK_ICON_PATH = STATIC_DIR / "FABOuanes.ico"
SPLASH_LOGO_PATH = STATIC_DIR / "desktop_logo_shield.png"
os.chdir(BASE_DIR)

try:
    from dotenv import load_dotenv

    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        example_file = BASE_DIR / ".env.example"
        if example_file.exists():
            shutil.copy(example_file, env_file)
        else:
            env_file.write_text(
                "DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/fabouanes\n"
                "FAB_HOST=0.0.0.0\n"
                "FAB_PORT=5000\n",
                encoding="utf-8",
            )

    load_dotenv(BASE_DIR / ".env")
    load_dotenv(DATA_DIR / ".env", override=False)
except Exception:
    pass
os.environ["FAB_BASE_DIR"] = str(BASE_DIR)
os.environ["FAB_DATA_DIR"] = str(DATA_DIR)
def ensure_desktop_paths() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEBVIEW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for folder_name in ("imports", "notes", "pdf_reader", "reports_generated"):
        (DATA_DIR / folder_name).mkdir(parents=True, exist_ok=True)


def clear_webview_http_cache() -> None:
    """Supprime le cache HTTP de WebView2 (CSS, JS, images) sans toucher aux données.
    Cela force le rechargement des fichiers statiques modifiés entre deux versions.
    """
    # WebView2 stocke son cache HTTP dans EBWebView/Default/Cache
    cache_dirs = [
        WEBVIEW_STORAGE_DIR / "EBWebView" / "Default" / "Cache",
        WEBVIEW_STORAGE_DIR / "EBWebView" / "Default" / "Code Cache",
    ]
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception:
                pass


def write_bootstrap_log(message: str) -> None:
    ensure_desktop_paths()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with (LOG_DIR / "desktop_setup.log").open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def read_install_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_install_state(payload: dict) -> None:
    ensure_desktop_paths()
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _find_pg_bin_dir() -> Path | None:
    """Locate the PostgreSQL bin directory on Windows."""
    pg_base = Path(os.environ.get("PG_HOME", "")) / "bin"
    if pg_base.exists():
        return pg_base
    for root in [Path(r"C:\Program Files\PostgreSQL"), Path(r"C:\Program Files (x86)\PostgreSQL")]:
        if not root.exists():
            continue
        versions = sorted(root.iterdir(), key=lambda p: p.name, reverse=True)
        for ver_dir in versions:
            candidate = ver_dir / "bin"
            if candidate.exists() and (candidate / "pg_isready.exe").exists():
                return candidate
    # Check PATH
    pg_isready = shutil.which("pg_isready")
    if pg_isready:
        return Path(pg_isready).parent
    return None


def _pg_is_ready(pg_bin: Path, host: str = "127.0.0.1", port: int = 5432) -> bool:
    """Check if PostgreSQL is accepting connections."""
    import subprocess
    try:
        result = subprocess.run(
            [str(pg_bin / "pg_isready"), "-h", host, "-p", str(port)],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def ensure_postgres_running() -> None:
    """Auto-detect PostgreSQL, start the service if stopped, and create the DB if needed.

    Designed for desktop/zero-config deployments on Windows where PostgreSQL is
    installed but the service may not be running after a fresh install or reboot.
    """
    import subprocess
    from urllib.parse import urlparse

    if os.name != "nt":
        return

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url or not db_url.lower().startswith(("postgres://", "postgresql://")):
        return

    parsed = urlparse(db_url)
    pg_host = parsed.hostname or "127.0.0.1"
    pg_port = parsed.port or 5432
    pg_user = parsed.username or "postgres"
    pg_password = parsed.password or ""
    pg_database = (parsed.path or "/fabouanes").lstrip("/")

    pg_bin = _find_pg_bin_dir()
    if not pg_bin:
        print("  [WARN] Impossible de trouver l'installation PostgreSQL.", flush=True)
        return

    # 1. Check if PostgreSQL is already running
    if _pg_is_ready(pg_bin, pg_host, pg_port):
        _ensure_database_exists(pg_bin, pg_host, pg_port, pg_user, pg_password, pg_database)
        return

    # 2. Try to start the service
    print("  PostgreSQL n'est pas demarre. Tentative de demarrage...", flush=True)

    # Detect the service name
    service_name = None
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Service -Name 'postgresql*' | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines():
            svc = line.strip()
            if svc:
                service_name = svc
                break
    except Exception:
        pass

    if not service_name:
        print("  [WARN] Service PostgreSQL introuvable.", flush=True)
        return

    # Try net start (works if running as admin or if service allows it)
    started = False
    try:
        result = subprocess.run(
            ["net", "start", service_name],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            started = True
    except Exception:
        pass

    if not started:
        # Elevate via PowerShell UAC prompt, stripping -w to prevent Error 1053 timeout
        try:
            cmd_args = (
                f"/c sc config \"{service_name}\" binPath= \"\\\"{pg_bin}\\pg_ctl.exe\\\" runservice -N \\\"{service_name}\\\" -D \\\"{pg_bin.parent}\\data\\\"\" "
                f"& net start \"{service_name}\""
            )
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    f"Start-Process cmd.exe -ArgumentList '{cmd_args}' -Verb RunAs -Wait",
                ],
                capture_output=True,
                timeout=30,
            )
            if _pg_is_ready(pg_bin, pg_host, pg_port):
                started = True
        except Exception:
            pass

    if not started:
        print(
            f"  [WARN] Impossible de demarrer PostgreSQL automatiquement.\n"
            f"         Lancez manuellement en tant qu'administrateur :\n"
            f"           net start {service_name}\n"
            f"         Ou demarrez le service '{service_name}' dans services.msc",
            flush=True,
        )
        return

    # 3. Wait for PostgreSQL to become ready
    print("  Attente que PostgreSQL soit pret...", flush=True)
    for _ in range(30):
        if _pg_is_ready(pg_bin, pg_host, pg_port):
            break
        time.sleep(1)
    else:
        print("  [WARN] PostgreSQL demarre mais ne repond pas encore.", flush=True)
        return

    print("  PostgreSQL est pret.", flush=True)

    # 4. Create the database if it doesn't exist
    _ensure_database_exists(pg_bin, pg_host, pg_port, pg_user, pg_password, pg_database)


def _ensure_database_exists(
    pg_bin: Path, host: str, port: int, user: str, password: str, database: str
) -> None:
    """Create the application database if it does not yet exist."""
    import subprocess

    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password

    # Check if database exists
    try:
        result = subprocess.run(
            [str(pg_bin / "psql"), "-h", host, "-p", str(port), "-U", user,
             "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{database}'"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        if result.stdout.strip() == "1":
            return  # Database already exists
    except Exception:
        pass

    # Create the database
    print(f"  Creation de la base de donnees '{database}'...", flush=True)
    try:
        result = subprocess.run(
            [str(pg_bin / "createdb"), "-h", host, "-p", str(port), "-U", user, database],
            capture_output=True, text=True, timeout=15, env=env,
        )
        if result.returncode == 0:
            print(f"  Base de donnees '{database}' creee avec succes.", flush=True)
        else:
            stderr = result.stderr.strip()
            if "already exists" in stderr or "existe deja" in stderr.lower():
                pass  # Already exists, ignore
            else:
                print(f"  [WARN] Erreur creation base: {stderr}", flush=True)
    except Exception as e:
        print(f"  [WARN] Erreur creation base: {e}", flush=True)



def bootstrap_desktop_install(reason: str = "desktop_startup") -> dict:
    ensure_desktop_paths()
    ensure_postgres_running()
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL est manquante. PostgreSQL est requis.")
    if not db_url.lower().startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Seul PostgreSQL est supporte.")

    from app.core.database import bootstrap_and_migrate
    from app.core.runtime_paths import ensure_runtime_dirs

    ensure_runtime_dirs()
    bootstrap_and_migrate()

    summary = {
        "app_version": APP_VERSION,
        "bootstrap_reason": reason,
        "bootstrapped_at": datetime.now().isoformat(timespec="seconds"),
        "database_path": db_url,
        "seeded_from_bundle": False,
        "migration_backup": "",
    }
    write_install_state(summary)
    write_bootstrap_log(f"Bootstrap termine ({reason}).")
    return summary


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        # On tente sur 127.0.0.1 car c'est toujours accessible meme en mode 0.0.0.0
        return sock.connect_ex(("127.0.0.1", port)) != 0


def port_bindable(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def get_bind_host() -> str:
    return os.environ.get("FAB_HOST", "0.0.0.0").strip() or "0.0.0.0"


def get_local_ip() -> str:
    """Discovers the best physical LAN IP address for local network/mobile access."""
    candidates = []
    
    # Method 1: Hostname resolution candidates
    try:
        hostname = socket.gethostname()
        _, _, ip_list = socket.gethostbyname_ex(hostname)
        for ip in ip_list:
            if not ip.startswith(("127.", "169.254.")):
                candidates.append(ip)
    except Exception:
        pass

    # Method 2: UDP probe candidate
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        probed_ip = probe.getsockname()[0]
        if probed_ip and not probed_ip.startswith(("127.", "169.254.")):
            candidates.insert(0, probed_ip)
    except OSError:
        pass
    finally:
        probe.close()

    # Prioritize: 192.168.x.x first, then 10.x.x.x, then 172.16-31.x.x
    def score_ip(ip: str) -> int:
        if ip.startswith("192.168."):
            return 100
        if ip.startswith("10."):
            return 80
        parts = ip.split(".")
        if len(parts) == 4 and parts[0] == "172" and 16 <= int(parts[1]) <= 31:
            return 60
        return 10

    if candidates:
        candidates.sort(key=score_ip, reverse=True)
        return candidates[0]

    return "127.0.0.1"


def show_system_notification(title: str, message: str, url: str | None = None) -> None:
    """Displays native OS notification on Windows and Termux (Android)."""
    def _notify():
        try:
            # 1. Termux Android Notification
            if shutil.which("termux-notification"):
                cmd = ["termux-notification", "--title", title, "--content", message]
                if url:
                    cmd.extend(["--action", f"termux-open-url {url}"])
                subprocess.run(cmd, check=False)
                return
        except Exception:
            pass

        # 2. Windows PowerShell Toast Notification
        if os.name == "nt":
            try:
                ps_script = f"""
                [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipTitle = "{title}"
                $notification.BalloonTipText = "{message}"
                $notification.Visible = $True
                $notification.ShowBalloonTip(5000)
                """
                subprocess.run(
                    ["powershell", "-Command", ps_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

    threading.Thread(target=_notify, daemon=True).start()


def free_stale_port(port: int = 5000) -> bool:
    """Frees stale/zombie python processes listening on target port if occupied before launch."""
    if port_bindable("0.0.0.0", port):
        return True

    try:
        if os.name == "nt":
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
            for line in output.strip().splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid and pid != "0":
                        proc_info = subprocess.check_output(f"tasklist /fi \"PID eq {pid}\"", shell=True, text=True)
                        if "python" in proc_info.lower():
                            subprocess.run(f"taskkill /f /pid {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            time.sleep(1)
                            print(f"  [OK] Processus orphelin sur port {port} (PID {pid}) libéré.", flush=True)
                            return port_bindable("0.0.0.0", port)
        else:
            # POSIX / Termux / Linux port cleanup
            try:
                subprocess.run(f"fuser -k {port}/tcp", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(0.5)
            except Exception:
                pass
            return port_bindable("0.0.0.0", port)
    except Exception:
        pass
    return False


def monitor_network_changes(port: int) -> None:
    """Monitors physical network IP changes (e.g. Wi-Fi switch) and updates access banner & QR code."""
    def _monitor():
        last_ip = get_local_ip()
        while True:
            time.sleep(10)
            current_ip = get_local_ip()
            if current_ip != last_ip and current_ip != "127.0.0.1":
                last_ip = current_ip
                ssl_certfile = os.environ.get("FAB_SSL_CERT", "").strip() or None
                use_https = bool(ssl_certfile or ((BASE_DIR / "cert.pem").exists() and (BASE_DIR / "key.pem").exists()))
                proto = "https" if use_https else "http"
                new_url = f"{proto}://{current_ip}:{port}"

                print("\n" + "=" * 59, flush=True)
                print(" 📡 DECTECTION DE CHANGEMENT DE RESEAU WI-FI !", flush=True)
                print(f" Nouveau lien mobile : {new_url}", flush=True)
                print("=" * 59, flush=True)
                print_qr_code(new_url)
                show_system_notification("FABOuanes - Nouveau Wi-Fi", f"Adresse IP Wi-Fi mise à jour : {new_url}", new_url)

    threading.Thread(target=_monitor, daemon=True).start()


def find_port(start: int = 5000, host: str | None = None) -> int:
    bind_host = host or get_bind_host()
    free_stale_port(start)
    for port in range(start, start + 1000):
        if port_bindable(bind_host, port):
            return port
    raise RuntimeError(f"Aucun port disponible entre {start} et {start + 999}.")


def server_access_lines(host: str, port: int, lan_ip: str | None = None) -> list[str]:
    client_host = lan_ip or (get_local_ip() if host == "0.0.0.0" else host)
    lines = [
        f"Localhost / cette machine : http://127.0.0.1:{port}",
        f"Mobile / Réseau local     : http://{client_host}:{port}",
        f"Mode serveur / écoute     : {host}:{port}",
    ]
    if host == "0.0.0.0":
        lines.append("Note: Si le mobile ne se connecte pas, autorisez le port 5000 dans le pare-feu Windows.")
    return lines


def print_qr_code(target_url: str) -> None:
    """Print an ASCII QR code to console for quick smartphone scanning."""
    try:
        import qrcode
        import sys
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
        qr = qrcode.QRCode(border=1)
        qr.add_data(target_url)
        print("\n  [+] Scannez ce QR Code avec votre mobile / tablette :", flush=True)
        qr.print_ascii(invert=True)
        print("", flush=True)
    except Exception:
        pass


def print_server_access(host: str, port: int, lan_ip: str | None = None) -> None:
    client_host = lan_ip or (get_local_ip() if host == "0.0.0.0" else host)
    ssl_certfile = os.environ.get("FAB_SSL_CERT", "").strip() or None
    ssl_keyfile = os.environ.get("FAB_SSL_KEY", "").strip() or None
    if not ssl_certfile and (BASE_DIR / "cert.pem").exists() and (BASE_DIR / "key.pem").exists():
        ssl_certfile = str(BASE_DIR / "cert.pem")
        ssl_keyfile = str(BASE_DIR / "key.pem")
    use_https = bool(ssl_certfile and ssl_keyfile)
    proto = "https" if use_https else "http"
    target_url = f"{proto}://{client_host}:{port}"
    banner = [
        "===========================================================",
        "           FABOUANES — ACCES RESEAU & MOBILE               ",
        "===========================================================",
        f"  PC Local : {proto}://127.0.0.1:{port}",
        f"  Mobile   : {target_url}",
        "-----------------------------------------------------------",
        "  Connectez vos smartphones/tablettes au meme réseau WiFi  ",
        "===========================================================",
    ]
    print("\n".join(banner), flush=True)
    print_qr_code(target_url)


def ensure_ssl_certificates(force: bool = False) -> tuple[str | None, str | None]:
    """Generate self-signed SSL cert.pem and key.pem if HTTPS is enabled or requested."""
    cert_path = BASE_DIR / "cert.pem"
    key_path = BASE_DIR / "key.pem"

    if cert_path.exists() and key_path.exists() and not force:
        return str(cert_path), str(key_path)

    enable_https = (
        force
        or os.environ.get("FAB_HTTPS", "0").strip().lower() in ("1", "true", "yes", "on")
        or os.environ.get("FAB_ENABLE_HTTPS", "0").strip().lower() in ("1", "true", "yes", "on")
        or "--https" in sys.argv
    )
    if not enable_https and not force:
        return None, None

    try:
        from datetime import datetime, timedelta, timezone
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import ipaddress

        print("  Génération automatique d'un certificat SSL auto-signé pour HTTPS...", flush=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        lan_ip = get_local_ip()
        san_list: list[x509.GeneralName] = [
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        if lan_ip and lan_ip != "127.0.0.1":
            try:
                san_list.append(x509.IPAddress(ipaddress.IPv4Address(lan_ip)))
            except Exception:
                pass

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FABOuanes ERP"),
            x509.NameAttribute(NameOID.COMMON_NAME, "FABOuanes Local Server"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .sign(key, hashes.SHA256())
        )

        key_path.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        print("  Certificat SSL généré avec succès (cert.pem et key.pem).", flush=True)
        return str(cert_path), str(key_path)
    except Exception as e:
        print(f"  [WARN] Impossible de générer le certificat SSL : {e}", flush=True)
        return None, None


def auto_open_browser(target_url: str, delay: float = 1.0) -> None:
    """Auto-opens default browser on Windows, macOS, Linux, and Termux (Android)."""
    if os.environ.get("FAB_NO_BROWSER", "0").strip() == "1":
        return

    def _open():
        time.sleep(delay)
        try:
            import urllib.request
            # Active HTTP poll to wait until server is accepting connections
            for _ in range(30):
                try:
                    with urllib.request.urlopen(f"{target_url}/health", timeout=1.0) as resp:
                        if resp.status in (200, 503):
                            break
                except Exception:
                    time.sleep(0.3)
        except Exception:
            pass

        print(f"  [+] Ouverture automatique du navigateur sur {target_url}...", flush=True)

        is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")

        if is_termux:
            # Multi-strategy launcher for Termux Android
            termux_cmds = [
                ["termux-open-url", target_url],
                ["termux-open", target_url],
                ["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", target_url],
                ["/system/bin/am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", target_url],
                ["am", "start", "-a", "android.intent.action.VIEW", "-d", target_url],
                ["xdg-open", target_url],
                ["/data/data/com.termux/files/usr/bin/termux-open-url", target_url],
                ["/data/data/com.termux/files/usr/bin/termux-open", target_url],
                ["/data/data/com.termux/files/usr/bin/xdg-open", target_url],
            ]
            for cmd_list in termux_cmds:
                executable = cmd_list[0]
                if os.path.exists(executable) or shutil.which(executable):
                    try:
                        subprocess.run(
                            cmd_list,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=3,
                            check=False
                        )
                    except Exception:
                        pass

        # Windows / Desktop standard browser fallback
        try:
            webbrowser.open(target_url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


def run_server(host: str, port: int) -> None:
    import uvicorn

    from app.core.database import bootstrap_and_migrate
    from app.core.logging import log_server_start
    from app.core.runtime_paths import ensure_runtime_dirs

    ensure_desktop_paths()
    ensure_postgres_running()
    ensure_runtime_dirs()
    server_mode = bool(LAUNCH_ARGS & SERVER_MODE_ARGS)
    if server_mode:
        print("Initialisation de la base de donnees...", flush=True)
    bootstrap_and_migrate()
    log_server_start()

    # --- Détection SSL automatique ---
    enable_https = (
        os.environ.get("FAB_HTTPS", "0").strip().lower() in ("1", "true", "yes", "on")
        or os.environ.get("FAB_ENABLE_HTTPS", "0").strip().lower() in ("1", "true", "yes", "on")
        or bool(os.environ.get("FAB_SSL_CERT", "").strip())
        or "--https" in sys.argv
    )
    ssl_certfile = None
    ssl_keyfile = None
    if enable_https:
        ssl_certfile = os.environ.get("FAB_SSL_CERT", "").strip() or None
        ssl_keyfile = os.environ.get("FAB_SSL_KEY", "").strip() or None
        if not ssl_certfile:
            auto_cert, auto_key = ensure_ssl_certificates(force=True)
            if auto_cert and auto_key:
                ssl_certfile = auto_cert
                ssl_keyfile = auto_key
            else:
                candidate_cert = BASE_DIR / "cert.pem"
                candidate_key = BASE_DIR / "key.pem"
                if candidate_cert.exists() and candidate_key.exists():
                    ssl_certfile = str(candidate_cert)
                    ssl_keyfile = str(candidate_key)
    use_https = bool(enable_https and ssl_certfile and ssl_keyfile)
    proto = "https" if use_https else "http"
    local_url = f"{proto}://127.0.0.1:{port}"

    if server_mode:
        lan_ip = os.environ.get("FAB_LAN_IP") or (get_local_ip() if host == "0.0.0.0" else host)
        client_host = lan_ip if host == "0.0.0.0" else host
        target_url = f"{proto}://{client_host}:{port}"
        print("Base OK.", flush=True)
        banner = [
            "===========================================================",
            "           FABOUANES — ACCES RESEAU & MOBILE               ",
            "===========================================================",
            f"  PC Local : {local_url}",
            f"  Mobile   : {target_url}",
        ]
        if use_https:
            banner.append("  Mode     : HTTPS (certificat SSL actif)")
        else:
            banner.append("  Mode     : HTTP (aucun certificat SSL détecté)")
        banner.append("===========================================================")
        print("\n".join(banner), flush=True)
        print_qr_code(target_url)
        show_system_notification("FABOuanes ERP", f"Serveur en ligne sur {target_url}", target_url)
        monitor_network_changes(port)
        print("La fenetre reste ouverte: c'est le mode serveur. Ctrl+C pour l'arreter.", flush=True)

    # Déclencher l'ouverture automatique du navigateur
    auto_open_browser(local_url)

    ws_protocol = "auto"
    try:
        import websockets  # noqa: F401
    except ImportError:
        try:
            import wsproto  # noqa: F401
        except ImportError:
            ws_protocol = "none"

    is_termux = "com.termux" in os.environ.get("PREFIX", "") or "com.termux" in sys.prefix or Path("/data/data/com.termux").exists()
    log_level = os.environ.get("FAB_UVICORN_LOG_LEVEL") or "warning"
    limit_concurrency = int(os.environ.get("FAB_UVICORN_CONCURRENCY", "100" if is_termux else "250"))
    timeout_keep_alive = int(os.environ.get("FAB_UVICORN_KEEP_ALIVE", "30"))

    config_kwargs: dict = dict(
        app="app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
        access_log=False,
        use_colors=False,
        ws=ws_protocol,
        limit_concurrency=limit_concurrency,
        timeout_keep_alive=timeout_keep_alive,
        backlog=128,
    )
    if is_termux:
        print("  Mode Termux/Mobile détecté — optimisations mémoire et réactivité actives.", flush=True)
    if use_https:
        config_kwargs["ssl_certfile"] = ssl_certfile
        config_kwargs["ssl_keyfile"] = ssl_keyfile
        print(f"  SSL activé — cert: {ssl_certfile}", flush=True)
    config = uvicorn.Config(**config_kwargs)
    server = uvicorn.Server(config)
    server.run()


def wait_server(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if not port_free(port):
            return True
        time.sleep(0.2)
    return False


def get_window_icon() -> Path | None:
    if DESKTOP_ICON_PATH.exists():
        return DESKTOP_ICON_PATH
    if FALLBACK_ICON_PATH.exists():
        return FALLBACK_ICON_PATH
    return None


def show_startup_splash(port: int, timeout: float = 45.0) -> bool:
    try:
        import tkinter as tk
    except Exception:
        return wait_server(port, timeout=timeout)

    ready = False
    deadline = time.time() + timeout
    root = tk.Tk()
    root.title(APP_NAME)
    root.configure(bg="#F5F7FB")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.resizable(False, False)

    icon_path = get_window_icon()
    if icon_path is not None and icon_path.exists():
        try:
            root.iconbitmap(default=str(icon_path))
        except Exception:
            pass

    frame = tk.Frame(root, bg="#F5F7FB", bd=1, relief="solid", padx=28, pady=26)
    frame.pack(fill="both", expand=True)

    logo_image = None
    if SPLASH_LOGO_PATH.exists():
        try:
            logo_image = tk.PhotoImage(file=str(SPLASH_LOGO_PATH))
            if logo_image.width() > 260:
                scale = max(1, round(logo_image.width() / 220))
                logo_image = logo_image.subsample(scale, scale)
        except Exception:
            logo_image = None

    if logo_image is not None:
        logo_label = tk.Label(frame, image=logo_image, bg="#F5F7FB")
        logo_label.image = logo_image
        logo_label.pack(pady=(0, 12))

    tk.Label(
        frame,
        text=APP_NAME,
        bg="#F5F7FB",
        fg="#16253F",
        font=("Segoe UI", 22, "bold"),
    ).pack()
    tk.Label(
        frame,
        text="Application desktop",
        bg="#F5F7FB",
        fg="#4F5E73",
        font=("Segoe UI", 11),
    ).pack(pady=(4, 14))

    status_var = tk.StringVar(value="Demarrage du serveur reseau...")
    tk.Label(
        frame,
        textvariable=status_var,
        bg="#F5F7FB",
        fg="#5F6C7E",
        font=("Segoe UI", 10),
    ).pack()

    footer_text = f"{APP_VERSION}   |   Donnees locales: {DATA_DIR}"
    tk.Label(
        frame,
        text=footer_text,
        bg="#F5F7FB",
        fg="#7A8596",
        font=("Segoe UI", 8),
        wraplength=420,
        justify="center",
    ).pack(pady=(14, 0))

    root.update_idletasks()
    width = max(420, frame.winfo_reqwidth())
    height = max(350, frame.winfo_reqheight())
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    pos_x = int((screen_width - width) / 2)
    pos_y = int((screen_height - height) / 2)
    root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    try:
        while time.time() < deadline:
            remaining = int(max(0, deadline - time.time()))
            status_var.set(f"Demarrage du serveur reseau... {remaining}s")
            root.update_idletasks()
            root.update()
            if not port_free(port):
                ready = True
                break
            time.sleep(0.15)
    except Exception:
        ready = not port_free(port)
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    return ready


def open_ui(url: str) -> None:
    try:
        import webview

        # Autoriser le téléchargement de fichiers dans l'application de bureau
        webview.settings['ALLOW_DOWNLOADS'] = True

        # Vider le cache HTTP de WebView2 pour charger les CSS/JS les plus récents
        clear_webview_http_cache()

        window = webview.create_window(
            APP_NAME,
            url,
            width=1360,
            height=860,
            min_size=(1024, 640),
            resizable=True,
            maximized=True,
            confirm_close=True,
            text_select=True,
            background_color="#F5F7FB",
        )
        icon_path = get_window_icon()

        def setup_webview_permissions(win):
            import time
            import threading

            def configure():
                try:
                    # Wait for window.native to become available
                    for _ in range(50):
                        if win.native is not None:
                            break
                        time.sleep(0.1)
                    if win.native is None:
                        return

                    # Wait for webview attribute
                    for _ in range(50):
                        if hasattr(win.native, "webview"):
                            break
                        time.sleep(0.1)
                    if not hasattr(win.native, "webview"):
                        return

                    webview_ctrl = win.native.webview

                    def on_init_completed(sender, args):
                        try:
                            core_wv2 = sender.CoreWebView2
                            if core_wv2 is not None:
                                def on_permission_requested(s, e):
                                    try:
                                        # Allow all permissions (Microphone, Camera, Clipboard, etc.)
                                        e.State = 1  # CoreWebView2PermissionState.Allow
                                        e.Handled = True
                                    except Exception:
                                        pass
                                core_wv2.PermissionRequested += on_permission_requested
                        except Exception:
                            pass

                    webview_ctrl.CoreWebView2InitializationCompleted += on_init_completed
                    if webview_ctrl.CoreWebView2 is not None:
                        on_init_completed(webview_ctrl, None)
                except Exception:
                    pass

            t = threading.Thread(target=configure, daemon=True)
            t.start()

        webview.start(
            setup_webview_permissions,
            window,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(WEBVIEW_STORAGE_DIR),
            icon=str(icon_path) if icon_path is not None else None,
        )
    except Exception:
        webbrowser.open(url)
        print(f"{APP_NAME} demarre sur {url}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def main() -> None:
    args = LAUNCH_ARGS
    if "--bootstrap-only" in args:
        try:
            reason = "installer_post_install" if "--post-install" in args else "bootstrap_only"
            summary = bootstrap_desktop_install(reason=reason)
            print(f"Bootstrap OK: {summary['database_path']}")
            sys.exit(0)
        except Exception as exc:
            write_bootstrap_log(f"Bootstrap echec: {exc}")
            print(f"Bootstrap failed: {exc}")
            sys.exit(1)

    if args & SERVER_MODE_ARGS:
        host = get_bind_host()
        start_port = int(os.environ.get("FAB_PORT", "5000") or "5000")
        port = find_port(start_port, host)
        os.environ["FAB_HOST"] = host
        os.environ["FAB_PORT"] = str(port)
        lan_ip = get_local_ip() if host == "0.0.0.0" else host
        if host == "0.0.0.0":
            os.environ["FAB_LAN_IP"] = lan_ip
        print(f"{APP_NAME} demarre en mode serveur reseau.", flush=True)
        print(f"Dossier de donnees: {DATA_DIR}", flush=True)
        run_server(host, port)
        return

    bootstrap_desktop_install(reason="desktop_launch")
    host = get_bind_host()
    start_port = int(os.environ.get("FAB_PORT", "5000") or "5000")
    port = find_port(start_port, host)
    os.environ["FAB_HOST"] = host
    os.environ["FAB_PORT"] = str(port)
    if host == "0.0.0.0":
        os.environ["FAB_LAN_IP"] = get_local_ip()
    else:
        os.environ.pop("FAB_LAN_IP", None)
    thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    thread.start()

    print(f"Demarrage de {APP_NAME}...")
    print(f"Dossier de donnees: {DATA_DIR}")
    if not show_startup_splash(port):
        print("Erreur: le serveur n'a pas demarre. Verifie que les dependances de requirements.txt sont installees.")
        sys.exit(1)

    lan_ip = os.environ.get("FAB_LAN_IP") or (get_local_ip() if host == "0.0.0.0" else host)
    print_server_access(host, port, lan_ip)
    if host == "0.0.0.0":
        print(f"\n  Acces mobile / reseau local : http://{lan_ip}:{port}\n", flush=True)
    print("Garde cette application ouverte pour laisser les autres machines connectees.", flush=True)

    open_ui(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    main()
