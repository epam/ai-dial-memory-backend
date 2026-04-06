"""Unit tests for StorageSync."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_storage import DialStorageError
from src.app.storage.sync import StorageSync


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(DIAL_URL="http://dial.test", TMP_DIR=tmp_path)


@pytest.fixture
def dial() -> AsyncMock:
    d = AsyncMock()
    d.get_storage_home = AsyncMock(return_value="files/user-bucket")
    return d


async def _mkdir_download(
    _api_key: str,
    _remote: str,
    local_path: Path,
) -> None:
    local_path.mkdir(parents=True, exist_ok=True)


@pytest.mark.asyncio
async def test_sync_down_runs_before_yield(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.download = AsyncMock(side_effect=_mkdir_download)
    sync = StorageSync(dial, settings)
    async with sync.open("api-key", write=False) as (_local, _bid):
        pass
    dial.download.assert_awaited_once()
    call = dial.download.await_args
    assert call.args[0] == "api-key"
    assert str(call.args[1]).endswith("/memory/memory.lance")
    dial.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_up_runs_after_write_true(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.download = AsyncMock(side_effect=_mkdir_download)
    dial.upload = AsyncMock()
    sync = StorageSync(dial, settings)
    async with sync.open("k", write=True) as (_local, _bid):
        pass
    dial.upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_sync_up_when_read_only(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.download = AsyncMock(side_effect=_mkdir_download)
    sync = StorageSync(dial, settings)
    async with sync.open("k", write=False):
        pass
    dial.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_404_creates_empty_memory_dir(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.download = AsyncMock(
        side_effect=DialStorageError("404 not found"),
    )
    sync = StorageSync(dial, settings)
    async with sync.open("k", write=False) as (local_lance, _bid):
        assert local_lance.is_dir()


@pytest.mark.asyncio
async def test_same_bucket_lock_serializes(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.get_storage_home = AsyncMock(return_value="files/same")
    inside_first = asyncio.Event()
    release_download = asyncio.Event()
    marker: list[str] = []

    async def blocking_download(
        _api_key: str,
        _remote: str,
        local_path: Path,
    ) -> None:
        local_path.mkdir(parents=True, exist_ok=True)
        inside_first.set()
        await release_download.wait()

    dial.download = AsyncMock(side_effect=blocking_download)
    sync = StorageSync(dial, settings)

    async def first_session() -> None:
        async with sync.open("k1", write=False):
            marker.append("body-a")

    async def second_session() -> None:
        await inside_first.wait()
        async with sync.open("k2", write=False):
            marker.append("body-b")

    t_a = asyncio.create_task(first_session())
    t_b = asyncio.create_task(second_session())
    await asyncio.wait_for(inside_first.wait(), timeout=1.0)
    await asyncio.sleep(0.02)
    assert "body-b" not in marker
    release_download.set()
    await asyncio.wait_for(asyncio.gather(t_a, t_b), timeout=2.0)
    assert marker.index("body-a") < marker.index("body-b")


@pytest.mark.asyncio
async def test_open_yields_stable_bucket_id(
    dial: AsyncMock,
    settings: AppSettings,
) -> None:
    dial.download = AsyncMock(side_effect=_mkdir_download)
    sync = StorageSync(dial, settings)
    async with sync.open("k", write=False) as (_path, bucket_id):
        assert len(bucket_id) == 64  # sha256 hex
    async with sync.open("k", write=False) as (_p2, bucket_id2):
        assert bucket_id == bucket_id2
