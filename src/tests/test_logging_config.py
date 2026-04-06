"""Tests for JSON structured logging setup."""

from __future__ import annotations

import io
import json
import logging

import pytest

from src.app.config.app_settings import AppSettings
from src.app.config.logging_config import setup_logging


@pytest.fixture(autouse=True)
def reset_root_logging() -> None:
    """Avoid leaking handlers/levels between tests."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    yield
    root.handlers.clear()
    root.setLevel(logging.WARNING)


def test_setup_logging_emits_json_line_with_message() -> None:
    buffer = io.StringIO()
    settings = AppSettings(DIAL_URL="http://dial.test", LOG_LEVEL="INFO")
    setup_logging(settings, stream=buffer)

    logging.getLogger("test_logger").info("hello-world")

    line = buffer.getvalue().strip()
    data = json.loads(line)
    assert data.get("message") == "hello-world"
    assert "levelname" in data or "level" in data


def test_setup_logging_respects_log_level() -> None:
    buffer = io.StringIO()
    settings = AppSettings(DIAL_URL="http://dial.test", LOG_LEVEL="WARNING")
    setup_logging(settings, stream=buffer)

    logging.getLogger("quiet").info("nope")
    assert buffer.getvalue() == ""

    logging.getLogger("loud").warning("yes")
    assert "yes" in buffer.getvalue()
