from __future__ import annotations

import logging
from pathlib import Path

from aidial_client import AsyncDial
from injector import inject

from src.app.config.app_settings import AppSettings

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
            raw = await client.bucket.get_raw()
            if not raw.appdata:
                raise DialStorageError(
                    "Cannot determine user storage: appdata is missing from bucket response. "
                    "Ensure the request is routed through DIAL with a valid user context."
                )
            home = f"files/{raw.appdata}"
            logger.info("resolved storage home: %s", home)
            return home
        except DialStorageError:
            raise
        except Exception as exc:
            raise DialStorageError(f"Failed to resolve storage home: {exc}") from exc

    async def download(self, api_key: str, remote_url: str, local_path: Path) -> None:
        client = self._make_client(api_key)
        logger.debug("download start: %s → %s", remote_url, local_path)
        try:
            result = await client.files.download(url=remote_url)
            await result.awrite_to(str(local_path))
            logger.debug("download done: %s", remote_url)
        except Exception as exc:
            logger.error("download failed: %s — %s", remote_url, exc)
            raise DialStorageError(f"Download failed {remote_url}: {exc}") from exc

    async def upload(self, api_key: str, local_path: Path, remote_url: str) -> None:
        client = self._make_client(api_key)
        logger.debug("upload start: %s → %s", local_path, remote_url)
        try:
            with open(local_path, "rb") as f:
                await client.files.upload(url=remote_url, file=f)
            logger.debug("upload done: %s", remote_url)
        except Exception as exc:
            logger.error("upload failed: %s — %s", remote_url, exc)
            raise DialStorageError(f"Upload failed {remote_url}: {exc}") from exc
