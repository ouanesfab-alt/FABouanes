from __future__ import annotations

import base64
import io
import os
import socket
from functools import lru_cache

from fabouanes.fastapi_compat import Request

try:
    import qrcode
except Exception:  # pragma: no cover - graceful fallback when dependency is missing
    qrcode = None


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "testserver", "testserver.local"}


def _is_local_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    return not normalized or normalized in _LOCAL_HOSTS or normalized == "0.0.0.0"


def _iter_local_ip_candidates() -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        ip = str(value or "").strip()
        if not ip or ip in seen or _is_local_host(ip):
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

    return candidates


def _get_local_ip() -> str:
    env_ip = str(os.environ.get("FAB_LAN_IP", "")).strip()
    if env_ip and not _is_local_host(env_ip):
        return env_ip

    candidates = _iter_local_ip_candidates()
    return candidates[0] if candidates else ""


def _port_from_request(request: Request) -> str:
    host = str(request.host or "").strip()
    if ":" in host:
        return host.rsplit(":", 1)[1]
    return str(os.environ.get("FAB_PORT", "")).strip()


def _compose_url(scheme: str, host: str, port: str) -> str:
    scheme_name = (scheme or "http").strip() or "http"
    port_value = str(port or "").strip()
    if not port_value or (scheme_name == "http" and port_value == "80") or (scheme_name == "https" and port_value == "443"):
        return f"{scheme_name}://{host}"
    return f"{scheme_name}://{host}:{port_value}"


def resolve_mobile_connect_url(request: Request) -> str:
    scheme = str(request.headers.get("X-Forwarded-Proto") or request.scheme or "http").strip() or "http"
    request_host = str(request.host or "").strip()
    current_host = request_host.rsplit(":", 1)[0] if request_host else ""
    port = _port_from_request(request)
    env_host = str(os.environ.get("FAB_HOST", "")).strip()

    if current_host and not _is_local_host(current_host):
        return _compose_url(scheme, current_host, port)

    if env_host and not _is_local_host(env_host):
        return _compose_url(scheme, env_host, port)

    if env_host == "0.0.0.0":
        lan_ip = _get_local_ip()
        if lan_ip:
            return _compose_url(scheme, lan_ip, port)

    if not env_host:
        lan_ip = _get_local_ip()
        if lan_ip:
            return _compose_url(scheme, lan_ip, port)

    return ""


@lru_cache(maxsize=16)
def build_mobile_connect_qr_data_uri(url: str) -> str:
    if not url or qrcode is None:
        return ""

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0f172a", back_color="white").convert("RGB")

    payload = io.BytesIO()
    image.save(payload, format="PNG", optimize=True)
    encoded = base64.b64encode(payload.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_mobile_connect_context(request: Request) -> dict[str, str | bool]:
    url = resolve_mobile_connect_url(request)
    if not url:
        return {
            "mobile_connect_available": False,
            "mobile_connect_url": "",
            "mobile_connect_qr_uri": "",
            "mobile_connect_status": "Mode reseau requis",
        }

    qr_uri = build_mobile_connect_qr_data_uri(url)
    if qr_uri:
        return {
            "mobile_connect_available": True,
            "mobile_connect_url": url,
            "mobile_connect_qr_uri": qr_uri,
            "mobile_connect_status": "Connexion mobile",
        }

    return {
        "mobile_connect_available": False,
        "mobile_connect_url": url,
        "mobile_connect_qr_uri": "",
        "mobile_connect_status": "QR indisponible",
    }
