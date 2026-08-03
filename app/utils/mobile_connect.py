from __future__ import annotations

import base64
import io
import os
import socket
from functools import lru_cache
from urllib.parse import urlparse

from starlette.requests import Request

try:
    import qrcode
except Exception:  # pragma: no cover - optional desktop dependency
    qrcode = None


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _is_local_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    return not normalized or normalized in _LOCAL_HOSTS or normalized == "0.0.0.0"


def _get_tailscale_ips() -> list[str]:
    """Détecte les adresses IPv4 Tailscale (gamme 100.64.0.0/10)."""
    ts_ips = []
    for k in ("TAILSCALE_IP", "FAB_TAILSCALE_IP"):
        val = str(os.environ.get(k, "")).strip()
        if val and val.startswith("100.") and val not in ts_ips:
            ts_ips.append(val)

    try:
        import subprocess
        proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=1.2)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                ip = line.strip()
                if ip and ip.startswith("100.") and ip not in ts_ips:
                    ts_ips.append(ip)
    except Exception:
        pass

    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            if "tailscale" in iface.lower() or "ts" in iface.lower():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address.startswith("100.") and addr.address not in ts_ips:
                        ts_ips.append(addr.address)
    except Exception:
        pass

    return ts_ips


def _get_all_ips() -> list[str]:
    ips = []
    env_ip = str(os.environ.get("FAB_LAN_IP", "")).strip()
    if env_ip and not _is_local_host(env_ip):
        ips.append(env_ip)

    # 1. Tailscale VPN IPs en priorité
    for ts_ip in _get_tailscale_ips():
        if ts_ip not in ips:
            ips.append(ts_ip)

    # 2. Utilisation de la table de routage (la plus fiable pour le LAN principal)
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        if ip and not _is_local_host(ip) and ip not in ips:
            ips.append(ip)
    except OSError:
        pass
    finally:
        probe.close()

    # 3. Ajout des interfaces virtuelles & socket
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = str(info[4][0] or "").strip()
            if ip and not _is_local_host(ip) and not ip.startswith("169.254.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass

    return ips


def _request_host(request: Request) -> str:
    return str(request.headers.get("host") or "").strip()


def _request_scheme(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-Proto")
    return str(forwarded or request.url.scheme or "http").strip() or "http"


def _port_from_request(request: Request) -> str:
    if request.url.port:
        return str(request.url.port)
    host = _request_host(request)
    if ":" in host and not host.startswith("["):
        return host.rsplit(":", 1)[1]
    return str(os.environ.get("FAB_PORT", "")).strip()


def _compose_url(scheme: str, host: str, port: str) -> str:
    scheme_name = (scheme or "http").strip() or "http"
    port_value = str(port or "").strip()
    if not port_value or (scheme_name == "http" and port_value == "80") or (scheme_name == "https" and port_value == "443"):
        return f"{scheme_name}://{host}"
    return f"{scheme_name}://{host}:{port_value}"


def _configured_mobile_url() -> str:
    for name in ("FAB_MOBILE_URL", "FAB_PUBLIC_URL"):
        raw = str(os.environ.get(name, "")).strip().rstrip("/")
        if not raw:
            continue
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return raw
    return ""


def resolve_mobile_connect_urls(request: Request) -> list[dict[str, Any]]:
    configured_url = _configured_mobile_url()
    if configured_url:
        return [{"name": "Réseau configuré", "url": configured_url, "is_tailscale": "100." in configured_url or "ts.net" in configured_url}]

    scheme = _request_scheme(request)
    request_host = _request_host(request)
    current_host = request.url.hostname or (request_host.rsplit(":", 1)[0] if request_host and not request_host.startswith("[") else request_host)
    port = _port_from_request(request)
    env_host = str(os.environ.get("FAB_HOST", "")).strip()

    networks = []

    # Check if the current Host header is public/remote
    if current_host and not _is_local_host(current_host):
        is_ts = current_host.startswith("100.") or "ts.net" in current_host
        networks.append({
            "name": "Accès Distant (Tailscale)" if is_ts else "Domaine actuel",
            "url": _compose_url(scheme, current_host, port),
            "is_tailscale": is_ts
        })

    if env_host and not _is_local_host(env_host) and env_host != current_host:
        is_ts = env_host.startswith("100.") or "ts.net" in env_host
        networks.append({
            "name": "Accès Distant (Tailscale)" if is_ts else "IP Serveur",
            "url": _compose_url(scheme, env_host, port),
            "is_tailscale": is_ts
        })

    ips = _get_all_ips()
    for ip in ips:
        url = _compose_url(scheme, ip, port)
        if any(n["url"] == url for n in networks):
            continue

        is_ts = ip.startswith("100.")
        name = "Réseau Distant VPN (Tailscale)" if is_ts else "Réseau Local (LAN / Wi-Fi)"
        if not is_ts and not (ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168.")):
            name = "Réseau Externe"

        networks.append({
            "name": name,
            "url": url,
            "is_tailscale": is_ts
        })

    # Sort so Tailscale VPN is featured first for remote access
    networks.sort(key=lambda n: 0 if n.get("is_tailscale") else 1)
    return networks


@lru_cache(maxsize=16)
def build_mobile_connect_qr_data_uri(url: str) -> str:
    if not url or qrcode is None:
        return ""

    try:
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
    except Exception:
        return ""


def build_mobile_connect_context(request: Request) -> dict:
    networks_info = resolve_mobile_connect_urls(request)

    networks = []
    for net in networks_info:
        qr = build_mobile_connect_qr_data_uri(net["url"])
        if qr:
            networks.append({
                "name": net["name"],
                "url": net["url"],
                "qr_uri": qr
            })

    if not networks:
        return {
            "mobile_connect_available": False,
            "mobile_connect_url": "",
            "mobile_connect_qr_uri": "",
            "mobile_connect_status": "Mode reseau requis",
            "mobile_networks": [],
        }

    # Backward compatibility with existing template structure if needed
    return {
        "mobile_connect_available": True,
        "mobile_connect_url": networks[0]["url"],
        "mobile_connect_qr_uri": networks[0]["qr_uri"],
        "mobile_connect_status": "Connexion mobile",
        "mobile_networks": networks,
    }
