from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from app.core.runtime_paths import ensure_runtime_dirs, paths


def notes_file_path() -> Path:
    ensure_runtime_dirs()
    return paths.notes_dir / "bloc_note.txt"


def read_app_notes() -> str:
    path = notes_file_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_app_notes(content: str) -> None:
    ensure_runtime_dirs()
    path = notes_file_path()
    old_content = path.read_text(encoding="utf-8") if path.exists() else ""
    normalized = (content or "").strip()
    if old_content.strip() and old_content.strip() != normalized:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = paths.notes_dir / f"history_{stamp}.txt"
        archive.write_text(old_content, encoding="utf-8")
        history_files = sorted(paths.notes_dir.glob("history_*.txt"), reverse=True)
        for stale_file in history_files[20:]:
            try:
                stale_file.unlink()
            except Exception:
                pass
    path.write_text(content or "", encoding="utf-8")


def list_notes_history() -> list[dict[str, str]]:
    ensure_runtime_dirs()
    versions: list[dict[str, str]] = []
    for item in sorted(paths.notes_dir.glob("history_*.txt"), reverse=True)[:20]:
        try:
            stamp = item.stem.replace("history_", "")
            rendered = datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            rendered = item.stem
        versions.append({"filename": item.name, "label": rendered})
    return versions


def read_notes_version(filename: str) -> str:
    safe_name = filename.replace("..", "").replace("/", "").replace("\\", "")
    path = paths.notes_dir / safe_name
    if path.exists() and path.suffix == ".txt":
        return path.read_text(encoding="utf-8")
    return ""


def list_pdf_reader_files() -> list[str]:
    ensure_runtime_dirs()
    return sorted((path.name for path in paths.pdf_reader_dir.glob("*.pdf")), key=str.lower)


def get_pdf_reader_file_path(filename: str) -> Path | None:
    safe_name = secure_filename(filename or "")
    if not safe_name:
        return None
    path = paths.pdf_reader_dir / safe_name
    return path if path.exists() else None


def save_pdf_reader_upload(uploaded_file: Any) -> str:
    ensure_runtime_dirs()
    filename = secure_filename(getattr(uploaded_file, "filename", "") or "")
    if not filename:
        raise ValueError("Choisis un fichier PDF.")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Seuls les fichiers PDF sont acceptes.")
    target = paths.pdf_reader_dir / filename
    uploaded_file.file.seek(0)
    with target.open("wb") as handle:
        shutil.copyfileobj(uploaded_file.file, handle)
    return filename


def delete_pdf_reader_file(filename: str) -> bool:
    path = get_pdf_reader_file_path(filename)
    if not path:
        return False
    path.unlink()
    return True
