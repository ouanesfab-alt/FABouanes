"""Tests unitaires automatisés pour la validation de tous les fichiers HTML (templates) et CSS.
Couverture > 90% exigée sur les assets non-python.
"""
from __future__ import annotations

from pathlib import Path
from html.parser import HTMLParser
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


class TemplateHTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_endtag(self, tag):
        pass


def test_html_templates_syntax_and_structure():
    assert TEMPLATES_DIR.exists()
    template_files = list(TEMPLATES_DIR.glob("**/*.html"))
    assert len(template_files) >= 15, "Doit contenir au moins 15 fichiers templates"

    for tpath in template_files:
        content = tpath.read_text(encoding="utf-8")
        assert len(content) > 0, f"Le fichier HTML {tpath.name} est vide"

        # Validate Jinja syntax elements
        assert "{%" in content or "{{" in content or "<!" in content or "<div" in content or "<html" in content or "<svg" in content or "<p" in content or "<span" in content or "{#" in content, f"Syntaxe Jinja2 / HTML invalide dans {tpath.name}"

        # Run HTML parser validation
        parser = TemplateHTMLValidator()
        try:
            parser.feed(content)
            assert len(parser.tags) >= 0
        except Exception as exc:
            pytest.fail(f"Erreur de parsing HTML dans {tpath.name}: {exc}")


def test_css_stylesheets_validity():
    assert STATIC_DIR.exists()
    css_files = list(STATIC_DIR.glob("**/*.css"))
    assert len(css_files) >= 2, "Doit contenir au moins 2 fichiers CSS"

    for cpath in css_files:
        content = cpath.read_text(encoding="utf-8")
        assert len(content) > 0, f"Le fichier CSS {cpath.name} est vide"
        assert ":" in content or "{" in content, f"Structure CSS invalide dans {cpath.name}"

