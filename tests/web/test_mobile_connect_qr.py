from __future__ import annotations

from starlette.requests import Request

from app.utils import mobile_connect


def _request(host: str = "127.0.0.1:5000") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/dashboard",
            "query_string": b"",
            "headers": [(b"host", host.encode("ascii"))],
            "server": ("127.0.0.1", 5000),
            "client": ("127.0.0.1", 50000),
        }
    )


def test_mobile_connect_uses_lan_ip_when_opened_from_localhost(monkeypatch):
    monkeypatch.delenv("FAB_MOBILE_URL", raising=False)
    monkeypatch.delenv("FAB_PUBLIC_URL", raising=False)
    monkeypatch.delenv("FAB_HOST", raising=False)
    monkeypatch.setattr(mobile_connect, "_get_all_ips", lambda: ["192.168.1.44"])

    urls = mobile_connect.resolve_mobile_connect_urls(_request())
    assert len(urls) > 0
    assert any(u["url"] == "http://192.168.1.44:5000" for u in urls)


def test_mobile_connect_context_builds_qr_for_lan_url(monkeypatch):
    monkeypatch.delenv("FAB_MOBILE_URL", raising=False)
    monkeypatch.delenv("FAB_PUBLIC_URL", raising=False)
    monkeypatch.setattr(mobile_connect, "_get_all_ips", lambda: ["192.168.1.44"])
    mobile_connect.build_mobile_connect_qr_data_uri.cache_clear()

    context = mobile_connect.build_mobile_connect_context(_request())

    assert context["mobile_connect_available"] is True
    assert len(context["mobile_networks"]) > 0
    
    found = False
    for net in context["mobile_networks"]:
        if net["url"] == "http://192.168.1.44:5000":
            found = True
            assert str(net["qr_uri"]).startswith("data:image/png;base64,")
    assert found
