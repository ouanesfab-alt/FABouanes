from __future__ import annotations

import logging
from pathlib import Path

from app.core.runtime_paths import ensure_runtime_dirs, paths


def configure_logging() -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger("fabouanes")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    file_handler = logging.FileHandler(Path(paths.log_dir) / "server.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def log_server_start() -> None:
    logger = configure_logging()
    logger.info("FABOuanes server starting")
