"""Sync-down / sync-up gateway between DIAL BLOB and local LanceDB paths."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import tarfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from injector import inject

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_storage import DialStorageError, DialStorageService
from src.app.storage.common.errors import StorageSyncError

logger = logging.getLogger(__name__)


def _bucket_id(storage_home: str) -> str:
    """Stable filesystem-safe id for this user's storage root."""
    return hashlib.sha256(storage_home.encode("utf-8")).hexdigest()


@inject
class StorageSync:
    def __init__(
        self,
        dial_storage_service: DialStorageService,
        settings: AppSettings,
    ) -> None:
        self._dial = dial_storage_service
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, bucket_id: str) -> asyncio.Lock:
        if bucket_id not in self._locks:
            self._locks[bucket_id] = asyncio.Lock()
        return self._locks[bucket_id]

    def _remote_memory_prefix(self, storage_home: str) -> str:
        return f"{storage_home.rstrip('/')}/memory/memory.tar.gz"

    async def _sync_down(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        """Pull remote memory.tar.gz and extract it as the local lance directory."""
        remote = self._remote_memory_prefix(storage_home)
        local_lance.parent.mkdir(parents=True, exist_ok=True)
        if local_lance.exists():
            shutil.rmtree(local_lance)
        tar_path = local_lance.parent / "memory.tar.gz"
        try:
            await self._dial.download(api_key, remote, tar_path)
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(local_lance.parent, filter="data")
        except DialStorageError as exc:
            if _is_not_found(exc):
                logger.info("No remote memory dataset at %s; starting fresh", remote)
                local_lance.mkdir(parents=True, exist_ok=True)
            else:
                raise StorageSyncError(f"sync-down failed: {exc}") from exc
        finally:
            if tar_path.exists():
                tar_path.unlink()

    async def _sync_up(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        """Pack the local lance directory as a tar.gz and upload it."""
        remote = self._remote_memory_prefix(storage_home)
        tar_path = local_lance.parent / "memory.tar.gz"
        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(local_lance, arcname=local_lance.name)
            await self._dial.upload(api_key, tar_path, remote)
        except DialStorageError as exc:
            raise StorageSyncError(f"sync-up failed: {exc}") from exc
        finally:
            if tar_path.exists():
                tar_path.unlink()

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
