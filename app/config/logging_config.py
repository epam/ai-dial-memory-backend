"""Configure stdlib logging with JSON log lines (startup only, not via injector)."""

from __future__ import annotations

import logging
import sys
from typing import IO

from pythonjsonlogger.json import JsonFormatter

from app.config.app_settings import AppSettings


def setup_logging(
    settings: AppSettings,
    *,
    stream: IO[str] | None = None,
) -> None:
    """Configure the root logger once at process start.

    Uses python-json-logger so each line is a single JSON object suitable for
    log aggregators. Does not use injector (cross-cutting startup hook).
    """
    out: IO[str] = stream if stream is not None else sys.stderr
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(out)
    # fmt drives which LogRecord attributes become JSON keys (not just "message").
    handler.setFormatter(JsonFormatter("%(name)s %(levelname)s %(message)s"))

    root.addHandler(handler)
    root.setLevel(_parse_level(settings.log_level))


def _parse_level(name: str) -> int:
    level = getattr(logging, str(name).upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO
