"""Tests unitaires automatisés pour la validation des scripts Batch (.bat) et Shell (.sh)."""
from __future__ import annotations

from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_shell_scripts_validity():
    sh_files = list(BASE_DIR.glob("**/*.sh"))
    assert len(sh_files) >= 1, "Au moins un script shell .sh doit exister"

    for spath in sh_files:
        if ".venv" in str(spath) or "node_modules" in str(spath):
            continue
        content = spath.read_text(encoding="utf-8", errors="ignore")
        assert len(content) > 0, f"Le script {spath.name} est vide"
        assert "#!" in content or "echo" in content or "cd" in content or "apt" in content or "pkg" in content, f"Structure shell invalide dans {spath.name}"


def test_batch_scripts_validity():
    bat_files = list(BASE_DIR.glob("**/*.bat"))
    assert len(bat_files) >= 1, "Au moins un script batch .bat doit exister"

    for bpath in bat_files:
        if ".venv" in str(bpath) or "node_modules" in str(bpath):
            continue
        content = bpath.read_text(encoding="utf-8", errors="ignore")
        assert len(content) > 0, f"Le script batch {bpath.name} est vide"
        # Check standard batch commands
        lines = [line.strip().lower() for line in content.splitlines() if line.strip()]
        has_valid_command = any(
            l.startswith("@echo") or l.startswith("echo") or l.startswith("set ") or l.startswith("cd ") or l.startswith("python") or l.startswith("pause") or l.startswith("if ") or l.startswith("call ") or l.startswith("chcp ") or l.startswith("goto ") or l.startswith("rem") or l.startswith("::")
            for l in lines
        )
        assert has_valid_command, f"Structure batch invalide dans {bpath.name}"
