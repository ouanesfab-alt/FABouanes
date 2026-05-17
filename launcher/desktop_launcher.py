from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_root_launcher():
    launcher_path = Path(__file__).resolve().parents[1] / "launcher.py"
    spec = importlib.util.spec_from_file_location("fabouanes_root_launcher", launcher_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load launcher from {launcher_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    _load_root_launcher().main()


if __name__ == "__main__":
    main()
