"""Unit tests for DialStorageService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_storage import DialStorageService


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(DIAL_URL="http://dial.test")


@pytest.fixture
def service(settings: AppSettings) -> DialStorageService:
    return DialStorageService(settings)


async def test_get_storage_home_uses_appdata_when_present(
    service: DialStorageService,
) -> None:
    """When appdata is present (DIAL service key), storage home uses appdata path."""
    from aidial_client.types.bucket import BucketResponse

    mock_bucket = AsyncMock()
    mock_bucket.get_raw = AsyncMock(
        return_value=BucketResponse(
            bucket="svc-bucket", appdata="user-abc/appdata/ai-dial-memory"
        )
    )
    mock_client = MagicMock()
    mock_client.bucket = mock_bucket

    with patch.object(
        service, "_make_client", return_value=mock_client
    ) as mock_factory:
        result = await service.get_storage_home("test-key")

    mock_factory.assert_called_once_with("test-key")
    assert result == "files/user-abc/appdata/ai-dial-memory"


async def test_get_storage_home_raises_when_appdata_absent(
    service: DialStorageService,
) -> None:
    """When appdata is absent we cannot guarantee user isolation — must raise."""
    from aidial_client.types.bucket import BucketResponse

    from src.app.dial.dial_storage import DialStorageError

    mock_bucket = AsyncMock()
    mock_bucket.get_raw = AsyncMock(
        return_value=BucketResponse(bucket="svc-bucket", appdata=None)
    )
    mock_client = MagicMock()
    mock_client.bucket = mock_bucket

    with patch.object(service, "_make_client", return_value=mock_client):
        with pytest.raises(DialStorageError, match="appdata is missing"):
            await service.get_storage_home("test-key")


async def test_download_writes_to_local_path(
    service: DialStorageService,
    tmp_path: Path,
) -> None:
    mock_result = AsyncMock()
    mock_client = MagicMock()
    mock_client.files.download = AsyncMock(return_value=mock_result)

    with patch.object(service, "_make_client", return_value=mock_client):
        await service.download("key", "files/bucket/memory.lance", tmp_path / "out")

    mock_client.files.download.assert_called_once_with(url="files/bucket/memory.lance")
    mock_result.awrite_to.assert_called_once_with(str(tmp_path / "out"))


async def test_upload_reads_local_file(
    service: DialStorageService,
    tmp_path: Path,
) -> None:
    local = tmp_path / "data.bin"
    local.write_bytes(b"hello")

    mock_client = AsyncMock()
    mock_client.files.upload = AsyncMock()

    with patch.object(service, "_make_client", return_value=mock_client):
        await service.upload("key", local, "files/bucket/memory.lance")

    mock_client.files.upload.assert_called_once()
    call_kwargs = mock_client.files.upload.call_args
    assert call_kwargs.kwargs.get("url") == "files/bucket/memory.lance"


@patch("src.app.dial.dial_storage.AsyncDial")
def test_make_client_builds_async_dial_with_key_and_base_url(
    mock_async_dial: MagicMock,
    settings: AppSettings,
) -> None:
    """DialStorageService delegates to AsyncDial with forwarded api_key and dial_url."""
    mock_async_dial.return_value = MagicMock()
    service = DialStorageService(settings)
    client = service._make_client("api-key-xyz")
    mock_async_dial.assert_called_once_with(
        api_key="api-key-xyz",
        base_url="http://dial.test",
    )
    assert client is mock_async_dial.return_value
