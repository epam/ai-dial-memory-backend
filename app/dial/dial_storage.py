from __future__ import annotations

import logging
from pathlib import Path

from aidial_client import AsyncDial
from injector import inject

from app.config.app_settings import AppSettings

logger = logging.getLogger(__name__)


class DialStorageError(Exception):
    """Wraps any SDK or I/O failure from DIAL file storage."""


@inject
class DialStorageService:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def _make_client(self, api_key: str) -> AsyncDial:
        return AsyncDial(api_key=api_key, base_url=self._settings.dial_url)

    async def get_storage_home(self, api_key: str) -> str:
        client = self._make_client(api_key)
        try:
            return await client.my_files_home()
        except Exception as exc:
            raise DialStorageError(f"Failed to resolve storage home: {exc}") from exc

    async def download(self, api_key: str, remote_url: str, local_path: Path) -> None:
        client = self._make_client(api_key)
        try:
            result = client.files.download(url=remote_url)
            await result.awrite_to(str(local_path))
        except Exception as exc:
            raise DialStorageError(f"Download failed {remote_url}: {exc}") from exc

    async def upload(self, api_key: str, local_path: Path, remote_url: str) -> None:
        client = self._make_client(api_key)
        try:
            with open(local_path, "rb") as f:
                await client.files.upload(url=remote_url, file=f)
        except Exception as exc:
            raise DialStorageError(f"Upload failed {remote_url}: {exc}") from exc
