# -*- coding: utf-8 -*-
"""
Tests unitaires pour scripts/check_termux_requirements.py (Lot 2).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from scripts.check_termux_requirements import (
    is_termux_environment,
    check_command,
    check_lib_with_pkg_config,
    run_requirements_check,
    main,
)


def test_is_termux_environment_detection():
    """Vérifie la détection de l'environnement Termux (var TERMUX_VERSION et PREFIX)."""
    with patch.dict(os.environ, {}, clear=True):
        assert is_termux_environment() is False

    with patch.dict(os.environ, {"TERMUX_VERSION": "0.118.0"}):
        assert is_termux_environment() is True

    with patch.dict(os.environ, {"FORCE_TERMUX_CHECK": "1"}):
        assert is_termux_environment() is True

    with patch.dict(os.environ, {"PREFIX": "/data/data/com.termux/files/usr"}):
        assert is_termux_environment() is True


def test_check_command_present_and_missing():
    """Vérifie que check_command détecte les exécutables présents/manquants."""
    assert check_command("python") is True or check_command("python3") is True
    assert check_command("non_existent_binary_xyz_12345") is False


def test_check_lib_with_pkg_config():
    """Vérifie le comportement de la fonction d'inspection des libs C."""
    with patch("scripts.check_termux_requirements.check_command", return_value=False):
        with patch("os.path.exists", return_value=False):
            assert check_lib_with_pkg_config("libffi") is False

    with patch("scripts.check_termux_requirements.check_command", return_value=True):
        mock_run = MagicMock()
        mock_run.returncode = 0
        with patch("subprocess.run", return_value=mock_run):
            assert check_lib_with_pkg_config("openssl") is True


def test_run_requirements_check_all_present():
    """Vérifie que run_requirements_check réussit si toutes les commandes et libs sont trouvées."""
    with patch("scripts.check_termux_requirements.check_command", return_value=True):
        with patch("scripts.check_termux_requirements.check_lib_with_pkg_config", return_value=True):
            success, missing = run_requirements_check(verbose=False)
            assert success is True
            assert missing == []


def test_run_requirements_check_missing_packages():
    """Vérifie la détection des paquets manquants."""
    def fake_check_cmd(cmd):
        return cmd == "clang"

    def fake_check_lib(lib):
        return lib == "openssl"

    with patch("scripts.check_termux_requirements.check_command", side_effect=fake_check_cmd):
        with patch("scripts.check_termux_requirements.check_lib_with_pkg_config", side_effect=fake_check_lib):
            success, missing = run_requirements_check(verbose=False)
            assert success is False
            assert "make" in missing
            assert "pkg-config" in missing
            assert "rust" in missing
            assert "libffi" in missing


def test_main_cli_non_termux():
    """Vérifie que main() retourne 0 hors de Termux."""
    with patch("scripts.check_termux_requirements.is_termux_environment", return_value=False):
        with patch.object(sys, "argv", ["check_termux_requirements.py"]):
            assert main() == 0


def test_main_cli_termux_success():
    """Vérifie que main() retourne 0 sous Termux quand tout est présent."""
    with patch("scripts.check_termux_requirements.is_termux_environment", return_value=True):
        with patch("scripts.check_termux_requirements.run_requirements_check", return_value=(True, [])):
            with patch.object(sys, "argv", ["check_termux_requirements.py", "--quiet"]):
                assert main() == 0


def test_main_cli_termux_failure():
    """Vérifie que main() retourne 1 sous Termux quand des paquets manquent."""
    with patch("scripts.check_termux_requirements.is_termux_environment", return_value=True):
        with patch("scripts.check_termux_requirements.run_requirements_check", return_value=(False, ["clang", "rust"])):
            with patch.object(sys, "argv", ["check_termux_requirements.py"]):
                assert main() == 1
