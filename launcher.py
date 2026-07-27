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





def bootstrap_desktop_install(reason: str = "desktop_startup") -> dict:
    ensure_desktop_paths()
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


def find_port(start: int = 5000, host: str | None = None) -> int:
    bind_host = host or get_bind_host()
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


def print_server_access(host: str, port: int, lan_ip: str | None = None) -> None:
    client_host = lan_ip or (get_local_ip() if host == "0.0.0.0" else host)
    banner = [
        "===========================================================",
        "           FABOUANES — ACCES RESEAU & MOBILE               ",
        "===========================================================",
        f"  PC Local : http://127.0.0.1:{port}",
        f"  Mobile   : http://{client_host}:{port}",
        "-----------------------------------------------------------",
        "  Connectez vos smartphones/tablettes au meme réseau WiFi  ",
        "===========================================================",
    ]
    print("\n".join(banner), flush=True)



def run_server(host: str, port: int) -> None:
    import uvicorn

    from app.core.database import bootstrap_and_migrate
    from app.core.logging import log_server_start
    from app.core.runtime_paths import ensure_runtime_dirs

    ensure_desktop_paths()
    ensure_runtime_dirs()
    server_mode = bool(LAUNCH_ARGS & SERVER_MODE_ARGS)
    if server_mode:
        print("Initialisation de la base de donnees...", flush=True)
    bootstrap_and_migrate()
    log_server_start()
    if server_mode:
        lan_ip = os.environ.get("FAB_LAN_IP") or (get_local_ip() if host == "0.0.0.0" else host)
        print("Base OK.", flush=True)
        print_server_access(host, port, lan_ip)
        print("La fenetre reste ouverte: c'est le mode serveur. Ctrl+C pour l'arreter.", flush=True)
    log_level = os.environ.get("FAB_UVICORN_LOG_LEVEL") or "warning"
    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
        access_log=False,
        use_colors=False,
    )
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
