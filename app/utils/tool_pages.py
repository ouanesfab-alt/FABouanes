from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from app.core.runtime_paths import ensure_runtime_dirs, paths


import json
import time

def notes_file_path() -> Path:
    ensure_runtime_dirs()
    return paths.notes_dir / "bloc_note.txt"


def list_user_notes() -> list[dict[str, Any]]:
    ensure_runtime_dirs()

    # Auto-migration of old flat notes file to multi-note JSON
    old_path = notes_file_path()
    main_note_path = paths.notes_dir / "note_main.json"
    if old_path.exists() and not main_note_path.exists():
        try:
            content = old_path.read_text(encoding="utf-8")
            main_note = {
                "id": "main",
                "title": "Mon Bloc-notes",
                "content": content,
                "color": "yellow",
                "pinned": False,
                "updated_at": old_path.stat().st_mtime
            }
            main_note_path.write_text(json.dumps(main_note, ensure_ascii=False, indent=2), encoding="utf-8")
            # Rename legacy file to avoid migrating again
            old_path.rename(paths.notes_dir / "bloc_note.txt.bak")
        except Exception:
            pass

    # Read all notes
    notes = []
    for item in paths.notes_dir.glob("note_*.json"):
        try:
            note = json.loads(item.read_text(encoding="utf-8"))
            # Backwards compatibility fix for fields
            if "id" not in note:
                note["id"] = item.stem.replace("note_", "")
            if "title" not in note:
                note["title"] = "Note sans titre"
            if "content" not in note:
                note["content"] = ""
            if "color" not in note:
                note["color"] = "yellow"
            if "pinned" not in note:
                note["pinned"] = False
            if "updated_at" not in note:
                note["updated_at"] = item.stat().st_mtime
            notes.append(note)
        except Exception:
            pass

    # If no notes exist, create a default welcome note
    if not notes:
        welcome_note = {
            "id": "main",
            "title": "Bienvenue dans votre Bloc-notes 📝",
            "content": "# Bienvenue !\n\nVoici votre nouveau bloc-notes moderne.\n\n### Fonctionnalités :\n- **Multi-notes** : Créez autant de notes que vous le souhaitez dans le panneau latéral.\n- **Épinglage** : Épinglez vos notes importantes en haut de la liste.\n- **Couleurs macOS** : Associez des couleurs à vos notes pour mieux les organiser.\n- **Éditeur Markdown** : Utilisez des balises simples comme `**gras**` ou `*italique*` et visualisez le rendu en temps réel.\n- **Checklists interactives** : Suivez vos tâches avec des cases à cocher `- [ ]` !\n\nProfitez-en !",
            "color": "yellow",
            "pinned": True,
            "updated_at": time.time()
        }
        try:
            main_note_path.write_text(json.dumps(welcome_note, ensure_ascii=False, indent=2), encoding="utf-8")
            notes.append(welcome_note)
        except Exception:
            pass

    # Sort: Pinned first, then by updated_at desc
    notes.sort(key=lambda x: (x.get("pinned", False), x.get("updated_at", 0)), reverse=True)
    return notes


def get_user_note(note_id: str) -> dict[str, Any] | None:
    ensure_runtime_dirs()
    safe_id = secure_filename(note_id or "")
    path = paths.notes_dir / f"note_{safe_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def save_user_note(note_id: str, title: str, content: str, color: str = "yellow", pinned: bool = False) -> dict[str, Any]:
    ensure_runtime_dirs()
    safe_id = secure_filename(note_id or "")
    path = paths.notes_dir / f"note_{safe_id}.json"

    note = {
        "id": safe_id,
        "title": (title or "Sans titre").strip(),
        "content": content or "",
        "color": color or "yellow",
        "pinned": bool(pinned),
        "updated_at": time.time()
    }

    # Save a history version (backup) before overwriting
    if path.exists():
        try:
            old_note = json.loads(path.read_text(encoding="utf-8"))
            if old_note.get("content", "").strip() != note["content"].strip():
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                history_dir = paths.notes_dir / "history"
                history_dir.mkdir(exist_ok=True)
                history_path = history_dir / f"history_{safe_id}_{stamp}.json"
                history_path.write_text(json.dumps(old_note, ensure_ascii=False, indent=2), encoding="utf-8")

                # Keep last 15 history items per note
                hist_files = sorted(history_dir.glob(f"history_{safe_id}_*.json"), reverse=True)
                for stale in hist_files[15:]:
                    try:
                        stale.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    return note


def create_user_note(title: str = "Sans titre", content: str = "", color: str = "yellow") -> dict[str, Any]:
    ensure_runtime_dirs()
    note_id = f"note_{int(time.time() * 1000)}"
    return save_user_note(note_id, title, content, color, False)


def delete_user_note(note_id: str) -> bool:
    ensure_runtime_dirs()
    safe_id = secure_filename(note_id or "")
    path = paths.notes_dir / f"note_{safe_id}.json"
    if path.exists():
        try:
            path.unlink()
            # Clean history
            history_dir = paths.notes_dir / "history"
            if history_dir.exists():
                for item in history_dir.glob(f"history_{safe_id}_*.json"):
                    try:
                        item.unlink()
                    except Exception:
                        pass
            return True
        except Exception:
            pass
    return False


def read_app_notes() -> str:
    # Backwards compatibility fallback: return content of first note
    notes = list_user_notes()
    if notes:
        return notes[0].get("content", "")
    return ""


def write_app_notes(content: str) -> None:
    # Backwards compatibility fallback: update main note
    save_user_note("main", "Mon Bloc-notes", content)


def list_notes_history() -> list[dict[str, str]]:
    # Backwards compatibility fallback
    ensure_runtime_dirs()
    history_dir = paths.notes_dir / "history"
    if not history_dir.exists():
        return []
    versions = []
    for item in sorted(history_dir.glob("history_*.json"), reverse=True)[:20]:
        try:
            parts = item.stem.split("_")
            stamp = parts[-2] + "_" + parts[-1]
            rendered = datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
            versions.append({"filename": item.name, "label": f"{rendered} ({parts[1]})"})
        except Exception:
            versions.append({"filename": item.name, "label": item.stem})
    return versions


def read_notes_version(filename: str) -> str:
    ensure_runtime_dirs()
    safe_name = filename.replace("..", "").replace("/", "").replace("\\", "")
    path = paths.notes_dir / "history" / safe_name
    if path.exists() and path.suffix == ".json":
        try:
            note = json.loads(path.read_text(encoding="utf-8"))
            return note.get("content", "")
        except Exception:
            pass
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
