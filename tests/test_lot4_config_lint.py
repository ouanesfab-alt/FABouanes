# -*- coding: utf-8 -*-
"""
Tests unitaires et d'intégration pour le Lot 4 (Nettoyage Config / Lint).
"""
from __future__ import annotations

import subprocess
from app.core.config import settings


def test_ruff_lint_app_core():
    """Vérifie que ruff check app/core ne signale aucune erreur/warning."""
    res = subprocess.run(
        ["python", "-m", "ruff", "check", "app/core/", "--select", "E,F,W", "--ignore", "E501"],
        cwd=str(settings.base_dir),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Ruff lint failures found in app/core:\n{res.stdout}\n{res.stderr}"
    assert "All checks passed!" in res.stdout


def test_batch_files_location_and_structure():
    """Vérifie le positionnement propre des fichiers .bat."""
    base_dir = settings.base_dir
    root_lancer = base_dir / "LANCER.bat"
    root_diagnostic = base_dir / "DIAGNOSTIC.bat"
    installer_dir = base_dir / "installer" / "windows"
    installer_builder = installer_dir / "CREER_INSTALLATEUR_WINDOWS.bat"
    installer_push = installer_dir / "PUSH_GITHUB.bat"

    # Vérification des raccourcis à la racine
    assert root_lancer.exists(), "LANCER.bat doit rester à la racine"
    assert root_diagnostic.exists(), "DIAGNOSTIC.bat doit rester à la racine"

    # Vérification que les batchs secondaires sont dans installer/windows/
    assert installer_builder.exists(), "CREER_INSTALLATEUR_WINDOWS.bat doit se trouver dans installer/windows/"
    assert installer_push.exists(), "PUSH_GITHUB.bat doit se trouver dans installer/windows/"

    # Vérification que les anciens batchs à la racine ont été supprimés
    assert not (base_dir / "CREER_INSTALLATEUR_WINDOWS.bat").exists()
    assert not (base_dir / "PUSH_GITHUB.bat").exists()
