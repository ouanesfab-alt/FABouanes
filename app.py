from fabouanes.app_factory import create_app
from fabouanes.runtime_app import ensure_runtime_dirs, init_db, log_server_start
import os
import socket

app = create_app()

__all__ = ["app", "ensure_runtime_dirs", "init_db", "log_server_start"]


def _best_lan_ip() -> str:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        ip = str(value or "").strip()
        if not ip or ip in seen or ip.startswith("127.") or ip in {"0.0.0.0", "::1"}:
            return
        seen.add(ip)
        candidates.append(ip)

    for probe_host in ("8.8.8.8", "1.1.1.1"):
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((probe_host, 80))
            add_candidate(probe.getsockname()[0])
        except OSError:
            pass
        finally:
            probe.close()

    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            add_candidate(ip)
    except OSError:
        pass

    return candidates[0] if candidates else ""


if __name__ == "__main__":
    log_server_start()
    host = os.environ.get("FAB_HOST", "0.0.0.0")
    port = int(os.environ.get("FAB_PORT", "5000"))
    os.environ["FAB_HOST"] = host
    os.environ["FAB_PORT"] = str(port)
    if host == "0.0.0.0" and not os.environ.get("FAB_LAN_IP"):
        lan_ip = _best_lan_ip()
        if lan_ip:
            os.environ["FAB_LAN_IP"] = lan_ip
    app.run(host=host, port=port, debug=False)
