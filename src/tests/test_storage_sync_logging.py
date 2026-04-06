"""Tests for structured JSON log lines in StorageSync.open()."""
from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pythonjsonlogger.json import JsonFormatter

from src.app.config.app_settings import AppSettings
from src.app.storage.sync import StorageSync


def _capture_logs() -> tuple[logging.Logger, StringIO]:
    """Return a logger and StringIO buffer capturing JSON log lines."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter("%(name)s %(levelname)s %(message)s"))
    logger = logging.getLogger("src.app.storage.sync")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger, buf


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(DIAL_URL="http://dial.test", TMP_DIR=tmp_path)


@pytest.fixture
def dial() -> AsyncMock:
    d = AsyncMock()
    d.get_storage_home = AsyncMock(return_value="files/user-bucket")

    async def _mkdir(api_key: str, remote: str, local_path: Path) -> None:
        local_path.mkdir(parents=True, exist_ok=True)

    d.download = AsyncMock(side_effect=_mkdir)
    d.upload = AsyncMock()
    return d


@pytest.mark.asyncio
async def test_sync_down_start_logged_with_bucket_field(
    dial: AsyncMock, settings: AppSettings
) -> None:
    logger, buf = _capture_logs()
    try:
        sync = StorageSync(dial, settings)
        async with sync.open("key", write=False):
            pass
    finally:
        logger.handlers.clear()

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    assert any("sync-down" in l.get("message", "") and "bucket" in l for l in lines), \
        f"Expected sync-down log with bucket field, got: {lines}"


@pytest.mark.asyncio
async def test_sync_up_logged_with_bucket_field(
    dial: AsyncMock, settings: AppSettings
) -> None:
    logger, buf = _capture_logs()
    try:
        sync = StorageSync(dial, settings)
        async with sync.open("key", write=True):
            pass
    finally:
        logger.handlers.clear()

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    assert any("sync-up" in l.get("message", "") and "bucket" in l for l in lines), \
        f"Expected sync-up log with bucket field, got: {lines}"


@pytest.mark.asyncio
async def test_all_log_lines_include_bucket_field(
    dial: AsyncMock, settings: AppSettings
) -> None:
    logger, buf = _capture_logs()
    try:
        sync = StorageSync(dial, settings)
        async with sync.open("key", write=True):
            pass
    finally:
        logger.handlers.clear()

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    assert lines, "No log lines emitted"
    for line in lines:
        assert "bucket" in line, f"Log line missing bucket field: {line}"
