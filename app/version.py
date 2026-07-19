from pathlib import Path

def _get_version() -> str:
    # 1. Try importlib.metadata first (standard if installed)
    try:
        import importlib.metadata
        return importlib.metadata.version("fabouanes")
    except Exception:
        pass

    # 2. Fall back to parsing pyproject.toml in base directory using tomllib
    try:
        import tomllib
        base_dir = Path(__file__).resolve().parents[1]
        toml_path = base_dir / "pyproject.toml"
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "2.0.0")
    except Exception:
        pass

    return "2.0.0"  # absolute fallback

APP_VERSION = _get_version()
VERSION_LABEL = f"v{APP_VERSION}"
