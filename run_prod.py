import os
import socket
import uvicorn

from fabouanes.app_factory import create_app
from fabouanes.logging_setup import configure_logging
from fabouanes.runtime_app import log_server_start

app = create_app()


def _best_lan_ip() -> str:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        ip = str(value or "").strip()
        if not ip or ip in seen or ip.startswith("127.") or ip.startswith("169.254.") or ip in {"0.0.0.0", "::1"} or ":" in ip:
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
        for entry in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            add_candidate(entry[4][0])
    except OSError:
        pass

    private_priority = ("192.168.", "10.", "172.")
    for prefix in private_priority:
        for candidate in candidates:
            if candidate.startswith(prefix):
                return candidate

    return candidates[0] if candidates else ""


if __name__ == "__main__":
    configure_logging()
    host = os.environ.get("FAB_HOST") or os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("FAB_PORT") or os.environ.get("PORT", "5000"))
    os.environ["FAB_HOST"] = host
    os.environ["FAB_PORT"] = str(port)
    os.environ["HOST"] = host
    os.environ["PORT"] = str(port)
    if host == "0.0.0.0" and not os.environ.get("FAB_LAN_IP"):
        lan_ip = _best_lan_ip()
        if lan_ip:
            os.environ["FAB_LAN_IP"] = lan_ip
    log_server_start()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
        access_log=True,
    )
