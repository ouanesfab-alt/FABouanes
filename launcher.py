"""Lanceur desktop FABOuanes."""
import json
import os
import shutil
import sys
import time
import socket
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

APP_NAME = "FABOuanes"
APP_VERSION = "Desktop 1.2"


if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
WEBVIEW_STORAGE_DIR = DATA_DIR / "webview"
BACKUP_DIR = DATA_DIR / "backups"
LOCAL_BACKUP_DIR = BACKUP_DIR / "local"
LOG_DIR = DATA_DIR / "logs"
STATE_FILE = DATA_DIR / "desktop_install_state.json"
DESKTOP_ICON_PATH = STATIC_DIR / "FABOuanes_desktop.ico"
FALLBACK_ICON_PATH = STATIC_DIR / "FABOuanes.ico"
SPLASH_LOGO_PATH = STATIC_DIR / "desktop_logo_shield.png"
os.chdir(BASE_DIR)
os.environ["FAB_BASE_DIR"] = str(BASE_DIR)
os.environ["FAB_DATA_DIR"] = str(DATA_DIR)
os.environ["FAB_DESKTOP"] = "1"

SRC_DB_PATH = BASE_DIR / "database.db"
DST_DB_PATH = DATA_DIR / "database.db"


def ensure_desktop_paths() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEBVIEW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for folder_name in ("imports", "notes", "pdf_reader", "reports_generated"):
        (DATA_DIR / folder_name).mkdir(parents=True, exist_ok=True)


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


def seed_database_if_missing() -> bool:
    if DST_DB_PATH.exists() or not SRC_DB_PATH.exists():
        return False
    shutil.copy2(SRC_DB_PATH, DST_DB_PATH)
    write_bootstrap_log(f"Base initiale copiee depuis {SRC_DB_PATH.name}.")
    return True


def create_pre_migration_backup(reason: str) -> Path | None:
    if not DST_DB_PATH.exists():
        return None
    ensure_desktop_paths()
    safe_reason = "".join(ch if ch.isalnum() else "_" for ch in reason.lower()).strip("_") or "migration"
    safe_version = "".join(ch if ch.isalnum() else "_" for ch in APP_VERSION.lower()).strip("_") or "desktop"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = LOCAL_BACKUP_DIR / f"database_{stamp}_{safe_reason}_{safe_version}.db"
    shutil.copy2(DST_DB_PATH, target)
    write_bootstrap_log(f"Sauvegarde pre-migration creee: {target.name}")
    return target


def bootstrap_desktop_install(reason: str = "desktop_startup") -> dict:
    ensure_desktop_paths()
    install_state = read_install_state()
    preexisting_db = DST_DB_PATH.exists()
    seeded_from_bundle = seed_database_if_missing()
    migration_backup = None
    if preexisting_db and install_state.get("app_version") != APP_VERSION:
        migration_backup = create_pre_migration_backup(reason)

    from app import ensure_runtime_dirs, init_db

    ensure_runtime_dirs()
    init_db()

    summary = {
        "app_version": APP_VERSION,
        "bootstrap_reason": reason,
        "bootstrapped_at": datetime.now().isoformat(timespec="seconds"),
        "database_path": str(DST_DB_PATH),
        "seeded_from_bundle": bool(seeded_from_bundle),
        "migration_backup": str(migration_backup) if migration_backup is not None else "",
    }
    write_install_state(summary)
    write_bootstrap_log(f"Bootstrap termine ({reason}).")
    return summary


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def get_bind_host() -> str:
    return os.environ.get("FAB_HOST", "0.0.0.0").strip() or "0.0.0.0"


def get_local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def find_port(start: int = 5000) -> int:
    for port in range(start, start + 20):
        if port_free(port):
            return port
    return start


def run_server(host: str, port: int) -> None:
    from waitress import serve
    from app import app, ensure_runtime_dirs, init_db, log_server_start

    ensure_desktop_paths()
    ensure_runtime_dirs()
    init_db()
    log_server_start()
    default_threads = "4" if os.environ.get("FAB_DESKTOP") == "1" else "8"
    threads = max(2, int(os.environ.get("FAB_SERVER_THREADS", default_threads) or default_threads))
    serve(app, host=host, port=port, threads=threads)


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


def show_startup_splash(port: int, timeout: float = 15.0) -> bool:
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

        webview.create_window(
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
        webview.start(
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
    args = {arg.strip().lower() for arg in sys.argv[1:] if arg.strip()}
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

    bootstrap_desktop_install(reason="desktop_launch")
    host = get_bind_host()
    port = find_port(5000)
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

    if host == "0.0.0.0":
        lan_ip = os.environ.get("FAB_LAN_IP", get_local_ip())
        print(f"Acces local : http://127.0.0.1:{port}")
        print(f"Acces Android / reseau : http://{lan_ip}:{port}")

    open_ui(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    main()
