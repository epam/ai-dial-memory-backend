"""Unit tests for DialStorageService."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.app_settings import AppSettings
from app.dial.dial_storage import DialStorageService


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(DIAL_URL="http://dial.test")


@pytest.fixture
def service(settings: AppSettings) -> DialStorageService:
    return DialStorageService(settings)


async def test_get_storage_home_calls_my_files_home(service: DialStorageService) -> None:
    """_make_client is called with correct api_key; my_files_home result is returned."""
    mock_client = AsyncMock()
    mock_client.my_files_home = AsyncMock(return_value="files/bucket-abc")

    with patch.object(service, "_make_client", return_value=mock_client) as mock_factory:
        result = await service.get_storage_home("test-key")

    mock_factory.assert_called_once_with("test-key")
    mock_client.my_files_home.assert_called_once()
    assert result == "files/bucket-abc"


async def test_download_writes_to_local_path(service: DialStorageService, tmp_path: Path) -> None:
    mock_result = AsyncMock()
    mock_client = MagicMock()
    mock_client.files.download.return_value = mock_result

    with patch.object(service, "_make_client", return_value=mock_client):
        await service.download("key", "files/bucket/memory.lance", tmp_path / "out")

    mock_client.files.download.assert_called_once_with(url="files/bucket/memory.lance")
    mock_result.awrite_to.assert_called_once_with(str(tmp_path / "out"))


async def test_upload_reads_local_file(service: DialStorageService, tmp_path: Path) -> None:
    local = tmp_path / "data.bin"
    local.write_bytes(b"hello")

    mock_client = AsyncMock()
    mock_client.files.upload = AsyncMock()

    with patch.object(service, "_make_client", return_value=mock_client):
        await service.upload("key", local, "files/bucket/memory.lance")

    mock_client.files.upload.assert_called_once()
    call_kwargs = mock_client.files.upload.call_args
    assert call_kwargs.kwargs.get("url") == "files/bucket/memory.lance"
