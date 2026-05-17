from __future__ import annotations

from tests.conftest import extract_csrf


def test_notes_page_renders(logged_client):
    response = logged_client.get("/notes")
    assert response.status_code == 200
    assert "Bloc-note" in response.text


def test_notes_page_can_save_content(logged_client):
    response = logged_client.get("/notes")
    csrf_token = extract_csrf(response.text)
    post = logged_client.post(
        "/notes",
        data={"csrf_token": csrf_token, "action": "save", "content": "Note FastAPI"},
        follow_redirects=False,
    )
    assert post.status_code == 303
    rendered = logged_client.get("/notes")
    assert "Note FastAPI" in rendered.text


def test_pdf_reader_page_renders(logged_client):
    response = logged_client.get("/pdf-reader")
    assert response.status_code == 200
    assert "Espace bons" in response.text
    assert "Achats" in response.text


def test_bons_space_alias_renders(logged_client):
    response = logged_client.get("/bons")
    assert response.status_code == 200
    assert "Historique client" in response.text
    assert 'class="bons-table"' in response.text
    assert 'data-bon-sort="document"' in response.text
    assert "embed=1" in response.text


def test_bons_missing_document_stays_in_bons_space(logged_client):
    response = logged_client.get("/bons?doc=missing:999999")
    assert response.status_code == 200
    assert "Bon introuvable" in response.text
    assert "Espace bons" in response.text


def test_print_missing_document_returns_404_without_redirect(logged_client):
    response = logged_client.get("/print/sale_finished/999999", follow_redirects=False)
    assert response.status_code == 404
    assert "Document introuvable" in response.text


def test_missing_client_history_print_returns_404_without_redirect(logged_client):
    response = logged_client.get("/contacts/clients/999999/print-history", follow_redirects=False)
    assert response.status_code == 404
    assert "Historique client introuvable" in response.text


def test_theme_script_uses_delegated_buttons(client):
    response = client.get("/static/js/theme.js")
    assert response.status_code == 200
    assert "document.addEventListener('click'" in response.text
    assert "closest('.js-theme')" in response.text


def test_service_worker_route_serves_javascript(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
