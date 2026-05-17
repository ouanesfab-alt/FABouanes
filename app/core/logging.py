from __future__ import annotations

import os
import json
import logging
import datetime
import traceback
from pathlib import Path

from app.core.runtime_paths import ensure_runtime_dirs, paths


class JSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for production logging and centralized ingestion.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_data, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger("fabouanes")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    # Check if structured JSON logging is enabled via environment variable
    if os.environ.get("FAB_LOG_JSON", "0").strip() == "1":
        formatter = JSONFormatter()
    else:
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
