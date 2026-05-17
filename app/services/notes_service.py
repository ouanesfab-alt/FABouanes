from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.storage import NOTES_DIR, ensure_runtime_dirs


def notes_file_path() -> Path:
    ensure_runtime_dirs()
    return NOTES_DIR / "bloc_note.txt"


def read_app_notes() -> str:
    path = notes_file_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_app_notes(content: str) -> None:
    ensure_runtime_dirs()
    path = notes_file_path()
    old_content = path.read_text(encoding="utf-8") if path.exists() else ""
    if old_content.strip() and old_content.strip() != (content or "").strip():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = NOTES_DIR / f"history_{stamp}.txt"
        archive.write_text(old_content, encoding="utf-8")
        for old_file in sorted(NOTES_DIR.glob("history_*.txt"), reverse=True)[20:]:
            try:
                old_file.unlink()
            except Exception:
                pass
    path.write_text(content or "", encoding="utf-8")


def list_notes_history() -> list[dict]:
    ensure_runtime_dirs()
    versions = []
    for path in sorted(NOTES_DIR.glob("history_*.txt"), reverse=True)[:20]:
        try:
            stamp = path.stem.replace("history_", "")
            label = datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            label = path.stem
        versions.append({"filename": path.name, "label": label})
    return versions


def read_notes_version(filename: str) -> str:
    safe = filename.replace("..", "").replace("/", "").replace("\\", "")
    path = NOTES_DIR / safe
    if path.exists() and path.suffix == ".txt":
        return path.read_text(encoding="utf-8")
    return ""
