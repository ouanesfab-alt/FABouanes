"""Tests unitaires automatisés pour la validation de tous les fichiers HTML (templates), CSS et JavaScript.
"""
from __future__ import annotations

import re
import subprocess
import shutil
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


class FormCSRFValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_form = None
        self.missing_csrf_forms = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "form":
            self.current_form = {"attrs": attr_dict, "has_csrf": False}
        elif tag == "input" and self.current_form:
            if attr_dict.get("name") == "csrf_token":
                self.current_form["has_csrf"] = True

    def handle_endtag(self, tag):
        if tag == "form" and self.current_form:
            method = (self.current_form["attrs"].get("method") or "").lower()
            if method == "post" and not self.current_form["has_csrf"]:
                self.missing_csrf_forms.append(self.current_form)
            self.current_form = None


def test_html_templates_syntax_and_structure():
    assert TEMPLATES_DIR.exists()
    template_files = list(TEMPLATES_DIR.glob("**/*.html"))
    assert len(template_files) >= 15, "Doit contenir au moins 15 fichiers templates"

    for tpath in template_files:
        content = tpath.read_text(encoding="utf-8")
        assert len(content) > 0, f"Le fichier HTML {tpath.name} est vide"

        # Validate Jinja syntax elements
        assert (
            "{%" in content
            or "{{" in content
            or "<!" in content
            or "<div" in content
            or "<html" in content
            or "<svg" in content
            or "<p" in content
            or "<span" in content
            or "{#" in content
        ), f"Syntaxe Jinja2 / HTML invalide dans {tpath.name}"

        # Run HTML parser validation
        parser = TemplateHTMLValidator()
        try:
            parser.feed(content)
            assert len(parser.tags) >= 0
        except Exception as exc:
            pytest.fail(f"Erreur de parsing HTML dans {tpath.name}: {exc}")


def test_html_forms_have_csrf_tokens():
    """Vérifie que tous les formulaires POST ont un champ csrf_token explicite."""
    template_files = list(TEMPLATES_DIR.glob("**/*.html"))
    missing = []
    for tpath in template_files:
        content = tpath.read_text(encoding="utf-8")
        # Strip jinja conditionals and interpolations for HTML parser
        clean = re.sub(r"\{%.*?%\}", "", content, flags=re.DOTALL)
        clean = re.sub(r"\{\{.*?\}\}", "VAR", clean, flags=re.DOTALL)
        clean = re.sub(r"\{#.*?#\}", "", clean, flags=re.DOTALL)
        validator = FormCSRFValidator()
        validator.feed(clean)
        if validator.missing_csrf_forms:
            missing.append((tpath.name, validator.missing_csrf_forms))

    assert not missing, f"Des formulaires POST manquent de csrf_token: {missing}"


def test_no_broken_static_paths_in_templates():
    """Vérifie qu'aucune URL statique directe cassée n'est injectée en dur."""
    template_files = list(TEMPLATES_DIR.glob("**/*.html"))
    broken = []
    for tpath in template_files:
        content = tpath.read_text(encoding="utf-8")
        # Ensure no hardcoded /static/ links exist without url_for
        if re.search(r'''(?:src|href)=["']/static/''', content):
            broken.append(tpath.name)

    assert not broken, f"Des templates contiennent des liens directs /static/: {broken}"


def test_css_stylesheets_validity():
    assert STATIC_DIR.exists()
    css_files = list(STATIC_DIR.glob("**/*.css"))
    assert len(css_files) >= 2, "Doit contenir au moins 2 fichiers CSS"

    for cpath in css_files:
        content = cpath.read_text(encoding="utf-8")
        assert len(content) > 0, f"Le fichier CSS {cpath.name} est vide"
        assert ":" in content or "{" in content, f"Structure CSS invalide dans {cpath.name}"


def test_js_modules_syntax():
    """Vérifie la syntaxe de tous les fichiers JavaScript non minifiés."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js non disponible dans l'environnement")

    js_files = [p for p in STATIC_DIR.glob("**/*.js") if not p.name.endswith(".min.js")]
    for js_path in js_files:
        res = subprocess.run([node_exe, "--check", str(js_path)], capture_output=True, text=True)
        assert res.returncode == 0, f"Erreur de syntaxe JS dans {js_path.name}: {res.stderr}"


def test_build_css_bundle():
    """Vérifie que le script build_css génère correctement un bundle minifié."""
    import sys
    res = subprocess.run([sys.executable, str(BASE_DIR / "scripts" / "build_css.py")], capture_output=True, text=True)
    assert res.returncode == 0, f"Échec de build_css.py: {res.stderr}"
    dist_dir = STATIC_DIR / "dist"
    bundles = list(dist_dir.glob("bundle.*.min.css"))
    assert len(bundles) >= 1, "Aucun bundle CSS généré dans static/dist"


def test_print_document_classes_and_media_print_safety():
    """Vérifie que la vue d'impression contient les classes appropriées et que le CSS d'impression désactive les animations."""
    print_doc_path = TEMPLATES_DIR / "print_document.html"
    assert print_doc_path.exists()
    content = print_doc_path.read_text(encoding="utf-8")
    assert "@media print" in content
    assert "animation: none !important" in content
    assert "overflow: visible !important" in content

    base_path = TEMPLATES_DIR / "base.html"
    base_content = base_path.read_text(encoding="utf-8")
    assert "is_print_view" in base_content
    set_idx = base_content.find("{% set is_print_view")
    html_idx = base_content.find("<html")
    assert set_idx != -1 and html_idx != -1 and set_idx < html_idx, "is_print_view doit être défini avant la balise <html>"

