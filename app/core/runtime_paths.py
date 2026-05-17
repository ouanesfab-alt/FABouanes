from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass(slots=True)
class RuntimePaths:
    app_data_dir: Path
    backup_dir: Path
    local_backup_dir: Path
    log_dir: Path
    report_dir: Path
    notes_dir: Path
    pdf_reader_dir: Path
    import_dir: Path
    templates_dir: Path
    static_dir: Path


paths = RuntimePaths(
    app_data_dir=settings.app_data_dir,
    backup_dir=settings.app_data_dir / "backups",
    local_backup_dir=settings.app_data_dir / "backups" / "local",
    log_dir=settings.app_data_dir / "logs",
    report_dir=settings.app_data_dir / "reports_generated",
    notes_dir=settings.app_data_dir / "notes",
    pdf_reader_dir=settings.app_data_dir / "pdf_reader",
    import_dir=settings.app_data_dir / "imports",
    templates_dir=settings.base_dir / "templates",
    static_dir=settings.base_dir / "static",
)


def ensure_runtime_dirs() -> None:
    for path in (
        paths.app_data_dir,
        paths.local_backup_dir,
        paths.log_dir,
        paths.report_dir,
        paths.notes_dir,
        paths.pdf_reader_dir,
        paths.import_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
