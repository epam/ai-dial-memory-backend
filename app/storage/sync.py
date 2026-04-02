"""Sync-down / sync-up gateway between DIAL BLOB and local LanceDB paths."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from injector import inject

from app.config.app_settings import AppSettings
from app.dial.dial_storage import DialStorageError, DialStorageService

logger = logging.getLogger(__name__)


class StorageSyncError(Exception):
    """Raised when pulling or pushing the Lance dataset fails."""


def _bucket_id(storage_home: str) -> str:
    """Stable filesystem-safe id for this user's storage root."""
    return hashlib.sha256(storage_home.encode("utf-8")).hexdigest()


@inject
class StorageSync:
    def __init__(
        self,
        dial: DialStorageService,
        settings: AppSettings,
    ) -> None:
        self._dial = dial
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, bucket_id: str) -> asyncio.Lock:
        if bucket_id not in self._locks:
            self._locks[bucket_id] = asyncio.Lock()
        return self._locks[bucket_id]

    def _remote_memory_prefix(self, storage_home: str) -> str:
        return f"{storage_home.rstrip('/')}/memory/memory.lance"

    async def _sync_down(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        """Best-effort pull of remote `memory.lance` tree into ``local_lance``."""
        remote = self._remote_memory_prefix(storage_home)
        local_lance.parent.mkdir(parents=True, exist_ok=True)
        if local_lance.exists():
            shutil.rmtree(local_lance)
        try:
            # DialStorageService currently streams a single object; callers/tests may
            # mock this to populate a directory. Missing remote → empty dataset.
            await self._dial.download(api_key, remote, local_lance)
        except DialStorageError as exc:
            if _is_not_found(exc):
                logger.info("No remote memory dataset at %s; starting fresh", remote)
                local_lance.mkdir(parents=True, exist_ok=True)
            else:
                raise StorageSyncError(f"sync-down failed: {exc}") from exc

    async def _sync_up(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        remote = self._remote_memory_prefix(storage_home)
        try:
            await self._dial.upload(api_key, local_lance, remote)
        except DialStorageError as exc:
            raise StorageSyncError(f"sync-up failed: {exc}") from exc

    @asynccontextmanager
    async def open(
        self,
        api_key: str,
        *,
        write: bool,
    ) -> AsyncGenerator[tuple[Path, str]]:
        """Sync down, yield ``(path_to_memory_lance, bucket_id)``, sync up on write.

        ``bucket_id`` must be passed to ``MemoryRepository`` for this open.
        """
        storage_home = await self._dial.get_storage_home(api_key)
        bucket_id = _bucket_id(storage_home)
        lock = self._lock_for(bucket_id)
        _log = {"bucket": bucket_id}
        async with lock:
            local_lance = self._settings.tmp_dir / bucket_id / "memory.lance"
            logger.debug("sync-down start", extra=_log)
            try:
                await self._sync_down(api_key, storage_home, local_lance)
            except StorageSyncError:
                raise
            logger.debug("sync-down end", extra=_log)
            try:
                yield local_lance, bucket_id
            finally:
                if write:
                    logger.debug("sync-up start", extra=_log)
                    await self._sync_up(api_key, storage_home, local_lance)
                    logger.debug("sync-up end", extra=_log)


def _is_not_found(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "404" in text or "not found" in text
