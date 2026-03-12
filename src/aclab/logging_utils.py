from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """A compact JSON-lines formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in ("event", "command", "playbook", "path", "status", "attempt", "elapsed_ms", "exit_code"):
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value
        extras = getattr(record, "extras", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True, default=str)


def _build_handler(stream: Any | None = None, log_path: Path | None = None) -> logging.Handler:
    handler: logging.Handler
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
    else:
        handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    return handler


def configure_json_logger(name: str, log_path: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(_build_handler())
    if log_path is not None:
        logger.addHandler(_build_handler(log_path=log_path))
    return logger

