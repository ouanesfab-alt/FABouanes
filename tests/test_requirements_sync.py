from __future__ import annotations

import re
from pathlib import Path

def test_requirements_termux_sync():
    """
    Ensure that requirements-termux.txt contains all core backend dependencies
    from requirements.txt except explicitly documented desktop-only packages.
    """
    base_dir = Path(__file__).resolve().parent.parent
    req_file = base_dir / "requirements.txt"
    termux_req_file = base_dir / "requirements-termux.txt"

    assert req_file.exists(), "requirements.txt not found"
    assert termux_req_file.exists(), "requirements-termux.txt not found"

    def parse_pkg_name(line: str) -> str | None:
        l = line.strip()
        if not l or l.startswith("#"):
            return None
        match = re.split(r"[<>=!]", l)
        return match[0].strip().lower()

    req_pkgs = {parse_pkg_name(line) for line in req_file.read_text(encoding="utf-8").splitlines() if parse_pkg_name(line)}
    termux_pkgs = {parse_pkg_name(line) for line in termux_req_file.read_text(encoding="utf-8").splitlines() if parse_pkg_name(line)}

    # Packages allowed to be missing on Termux/ARM due to heavy C/Rust compilation or desktop-only nature
    ALLOWED_MISSING_ON_TERMUX = {"pywebview", "pywin32", "pandas", "pillow", "qrcode[pil]"}

    missing_in_termux = (req_pkgs - termux_pkgs) - ALLOWED_MISSING_ON_TERMUX

    assert not missing_in_termux, (
        f"The following dependencies are in requirements.txt but missing in requirements-termux.txt: {missing_in_termux}. "
        f"If intended, add them to ALLOWED_MISSING_ON_TERMUX in tests/test_requirements_sync.py with documentation."
    )
