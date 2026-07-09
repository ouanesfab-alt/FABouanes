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
    Includes request_id for request-level correlation.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        # Add request_id for correlation if available
        request_id = getattr(record, "request_id", None)
        if not request_id:
            try:
                from app.core.request_state import get_state_value
                request_id = get_state_value("request_id")
            except Exception:
                pass
        if request_id:
            log_data["request_id"] = request_id
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))

        # Add custom extra fields to the JSON log dict
        standard_attrs = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName"
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

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
