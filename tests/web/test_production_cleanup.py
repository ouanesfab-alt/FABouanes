from __future__ import annotations

from app.main import app


def test_route_names_do_not_expose_old_prefixes():
    route_names = [getattr(route, "name", "") for route in app.routes]
    old_prefix = "leg" + "acy_"
    assert not [name for name in route_names if name.startswith(old_prefix)]


def test_old_contact_and_operation_urls_redirect_to_canonical_routes(logged_client):
    expectations = {
        "/clients/new": "/contacts/clients/new",
        "/suppliers/new": "/contacts/suppliers/new",
        "/sales/new": "/operations/sales/new",
        "/purchases/new": "/operations/purchases/new",
        "/payments/new?mode=avance": "/operations/payments/new?mode=avance",
    }
    for source, target in expectations.items():
        response = logged_client.get(source, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == target
